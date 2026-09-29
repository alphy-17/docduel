"""Evaluation CLI (Plan task 5.2).

    uv run python -m docduel.eval --model openai --split dev --prompt extract_v1
    uv run python -m docduel.eval --model openai --split test-v1 --prompt extract_v1 --confirm-test

Runs one model over a split, scores every answer with Section 10 rules, and writes
reports/eval_<model>_<split>_<prompt>.json plus a matching .md summary.

The test set is only used with --confirm-test. That stops accidental prompt tuning on test
documents (rule R4). Spending stops once --max-usd is passed.
"""

import argparse
import asyncio
import dataclasses
import json
import statistics
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv

from docduel.datasets.build import DATASET_VERSION, splits_dir
from docduel.models.client import client_for
from docduel.models.registry import load_models
from docduel.runs.costing import load_pricing
from docduel.runs.orchestrator import ModelOutcome, run_model
from docduel.runs.prompting import VERSION, build_prompt
from docduel.scoring import categorise, extract
from docduel.scoring.bootstrap import bootstrap_ci, fmt_ci
from docduel.settings import BACKEND_DIR, REPO_DIR
from docduel.testset import is_test_document

SPLITS = {
    "dev": "dev.jsonl",
    DATASET_VERSION: "test.jsonl",
    "hard-correct": "hard_correct.jsonl",  # Phase 8: 40 docs the Owner corrects
    "hard-holdout": "hard_holdout.jsonl",  # Phase 8: 20 docs held out to measure round 2
}
SCORED_TASKS = ("extract", "categorise")
WORST_N = 10


def report_dir() -> Path:
    return REPO_DIR / "reports"


def load_docs(split: str, task: str) -> list[dict]:
    path = splits_dir() / SPLITS[split]
    rows = [json.loads(line) for line in path.open(encoding="utf-8")]
    docs = [r for r in rows if r["task"] == task]
    if split == DATASET_VERSION:
        missing = [d["id"] for d in docs if not is_test_document(d["sha256"])]
        if missing:
            sys.exit(f"test manifest mismatch for {len(missing)} docs, e.g. {missing[:3]}")
    else:
        leaked = [d["id"] for d in docs if is_test_document(d["sha256"])]
        if leaked:
            sys.exit(f"LEAK: test documents found in {split}: {leaked[:3]}")
    return docs


def percentile(values: list[float], q: float) -> float | None:
    return round(float(np.percentile(values, q))) if values else None


async def run_all(
    spec, docs: list[dict], task: str, max_usd: float, concurrency: int
) -> list[tuple[dict, ModelOutcome | None]]:
    sem = asyncio.Semaphore(concurrency)
    spent = {"usd": 0.0}

    async def noop(*_: Any) -> None:
        return None

    async def one(doc: dict) -> tuple[dict, ModelOutcome | None]:
        async with sem:
            if spent["usd"] > max_usd:
                return doc, None
            out = await run_model(spec, build_prompt(task, text=doc["text"]), noop, client_for)
            spent["usd"] += out.cost_usd or 0
            status = "ok" if out.schema_valid else out.error_code or "invalid"
            print(f"  {doc['id']}: {status}  ${out.cost_usd or 0:.5f}", flush=True)
            return doc, out

    return await asyncio.gather(*(one(d) for d in docs))


def saved_outcome(out: ModelOutcome) -> dict[str, Any]:
    """Everything needed to re-score later; raw text only when the answer was invalid."""
    data = dataclasses.asdict(out)
    if out.schema_valid:
        data.pop("raw_output")
    return data


def load_saved(
    path: Path, docs: list[dict]
) -> tuple[list[tuple[dict, ModelOutcome]], str, dict | None]:
    if not path.exists():
        sys.exit(f"no saved report at {path}; run without --rescore first")
    report = json.loads(path.read_text(encoding="utf-8"))
    if "outputs" not in report:
        sys.exit("this report has no saved answers; run without --rescore once")
    saved = {o.pop("id"): o for o in report["outputs"]}
    missing = [d["id"] for d in docs if d["id"] not in saved]
    if missing:
        sys.exit(f"saved report lacks {len(missing)} documents, e.g. {missing[:3]}")
    steady = report.get("speed_cost", {}).get("steady_load")
    return [(d, ModelOutcome(**saved[d["id"]])) for d in docs], report["created_at"], steady


def steady_load(spec, wall_seconds: float, docs: int, concurrency: int) -> dict[str, Any] | None:
    """Plan 11: GPU cost at a stated steady load = GPU busy time / documents.

    The eval keeps `concurrency` requests in flight on a warm GPU, so the wall-clock time of
    the run is the time the GPU was busy. Only for our own GPU model (OpenAI bills per token).
    """
    if spec.provider != "vllm" or not docs:
        return None
    per_hour = load_pricing().get("modal", {}).get("gpu_per_hour", {}).get(spec.gpu or "")
    if per_hour is None:
        return None
    return {
        "concurrency": concurrency,
        "wall_seconds": round(wall_seconds, 1),
        "docs": docs,
        "cost_per_1000_docs_usd": round(per_hour / 3600 * wall_seconds / docs * 1000, 4),
    }


def speed_and_cost(outs: list[ModelOutcome]) -> dict[str, Any]:
    warm = [o for o in outs if o.latency_ms is not None and not o.cold_start]
    lat = [o.latency_ms for o in warm]
    ttft = [o.ttft_ms for o in warm if o.ttft_ms is not None]
    costs = [o.cost_usd for o in outs if o.cost_usd is not None]
    # Plan 11: GPU cost per 1,000 docs is the warm, busy cost; cold starts are reported apart.
    warm_costs = [o.cost_usd for o in warm if o.cost_usd is not None]
    return {
        "latency_ms_p50": percentile(lat, 50),
        "latency_ms_p95": percentile(lat, 95),
        "ttft_ms_p50": percentile(ttft, 50),
        "cold_starts": sum(o.cold_start for o in outs),
        "input_tokens_mean": round(statistics.mean(o.input_tokens for o in outs)) if outs else 0,
        "output_tokens_mean": round(statistics.mean(o.output_tokens for o in outs)) if outs else 0,
        "reasoning_tokens_mean": (
            round(statistics.mean(o.reasoning_tokens for o in outs)) if outs else 0
        ),
        "cost_usd_total": round(sum(costs), 6),
        "cost_per_1000_docs_usd": (
            round(1000 * sum(warm_costs) / len(warm_costs), 4) if warm_costs else None
        ),
        "cold_start_ttft_ms": [round(o.ttft_ms) for o in outs if o.cold_start and o.ttft_ms],
        "errors": dict(Counter(o.error_code for o in outs if o.error_code)),
    }


def with_ci(value: float, docs: list, metric) -> dict[str, Any]:
    ci = bootstrap_ci(docs, metric)
    return {
        "value": round(value, 4),
        "ci95": [round(ci[0], 4), round(ci[1], 4)],
        "display": fmt_ci(value, ci),
    }


def score_extract(results: list[tuple[dict, ModelOutcome]]) -> dict[str, Any]:
    scored = []
    for doc, out in results:
        pred = out.parsed if out.schema_valid else None
        scored.append((doc, out, extract.score_extraction(pred, doc["label"])))
    docs = [s for _, _, s in scored]
    agg = extract.aggregate(docs)
    headline = {
        name: with_ci(agg[name], docs, lambda xs, n=name: extract.aggregate(xs)[n])
        for name in ("field_accuracy", "line_item_f1", "perfect_document_rate", "schema_validity")
    }
    by_source: dict[str, Any] = {}
    for source in sorted({d["source"] for d, _, _ in scored}):
        subset = [s for d, _, s in scored if d["source"] == source]
        by_source[source] = {"docs": len(subset)} | {
            k: round(v, 4) for k, v in extract.aggregate(subset).items()
        }
    per_doc = []
    for doc, out, s in scored:
        wrong = [f for f, v in s.fields.items() if not v["fuzzy"]]
        per_doc.append(
            {
                "id": doc["id"],
                "source": doc["source"],
                "valid": s.valid,
                "error_code": out.error_code,
                "fields": f"{s.field_correct}/{s.field_total}",
                "wrong_fields": {
                    f: {
                        "predicted": (out.parsed or {}).get(f) if s.valid else None,
                        "expected": doc["label"].get(f),
                    }
                    for f in wrong
                },
                "items": {"tp": s.items.tp, "pred": s.items.n_pred, "gold": s.items.n_gold},
                "perfect": s.perfect,
                "line_items": None
                if s.perfect
                else {
                    "predicted": (out.parsed or {}).get("line_items") if s.valid else None,
                    "expected": doc["label"].get("line_items"),
                },
                "latency_ms": out.latency_ms,
                "cost_usd": out.cost_usd,
            }
        )

    def badness(d: dict) -> tuple:
        ok, tot = map(int, d["fields"].split("/"))
        missed = d["items"]["gold"] - d["items"]["tp"] + d["items"]["pred"] - d["items"]["tp"]
        return (d["valid"], ok - tot, -missed)

    worst = [d["id"] for d in sorted(per_doc, key=badness)[:WORST_N] if not d["perfect"]]
    return {
        "headline": headline
        | {
            "field_accuracy_exact": round(agg["field_accuracy_exact"], 4),
            "line_item_precision": round(agg["line_item_precision"], 4),
            "line_item_recall": round(agg["line_item_recall"], 4),
        },
        "per_field": extract.per_field(docs),
        "by_source": by_source,
        "worst_failures": worst,
        "per_doc": per_doc,
        "scoring_notes": [
            "Only fields with non-null ground truth are scored (CORD has no vendor or date).",
            "Short strings: headline uses fuzzy match (token_set_ratio >= 90); exact also given.",
            "Zero-priced line items (modifiers, free extras) are ignored on both sides.",
            "A line item with a blank true amount only needs a matching description.",
            "Perfect document = every scored field and every priced line item right.",
            "95% intervals: 1,000 bootstrap resamples of documents, seed 2026.",
        ],
    }


def score_categorise(results: list[tuple[dict, ModelOutcome]]) -> dict[str, Any]:
    scored = [
        (
            doc,
            out,
            categorise.score_categories(out.parsed if out.schema_valid else None, doc["label"]),
        )
        for doc, out in results
    ]
    cats = [s for _, _, s in scored]
    agg = categorise.aggregate(cats)
    return {
        "headline": {
            name: with_ci(agg[name], cats, lambda xs, n=name: categorise.aggregate(xs)[n])
            for name in ("accuracy", "macro_f1", "schema_validity")
        },
        "confusion_matrix": categorise.confusion(cats),
        "per_doc": [
            {
                "id": d["id"],
                "valid": s.valid,
                "correct": s.correct,
                "rows": s.rows,
                "extra_rows": s.extra,
                "error_code": o.error_code,
            }
            for d, o, s in scored
        ],
        "scoring_notes": [
            "A missing or extra row_id counts as wrong for that row.",
            "95% intervals: 1,000 bootstrap resamples of documents, seed 2026.",
        ],
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        f"# Evaluation: {report['model_key']} on {report['split']} ({report['prompt']})",
        "",
        f"- Model: `{report['model_id']}` (reasoning: {report['reasoning_effort']})",
        f"- Documents: {report['docs_scored']} scored of {report['docs_total']}",
        f"- Created: {report['created_at']}",
        "",
        "| Metric | Value (95% interval) |",
        "|---|---|",
    ]
    for name, v in report["scores"]["headline"].items():
        if isinstance(v, dict):
            lines.append(f"| {name.replace('_', ' ')} | {v['display']} |")
        else:
            lines.append(f"| {name.replace('_', ' ')} | {v * 100:.1f}% |")
    sp = report["speed_cost"]
    lines += [
        f"| p50 / p95 latency | {sp['latency_ms_p50']} / {sp['latency_ms_p95']} ms |",
        f"| cost per 1,000 docs | ${sp['cost_per_1000_docs_usd']} |",
        f"| total cost of this run | ${sp['cost_usd_total']} |",
        "",
    ]
    if "per_field" in report["scores"]:
        lines += ["| Field | Scored | Accuracy | Exact |", "|---|---|---|---|"]
        for f, v in report["scores"]["per_field"].items():
            lines.append(
                f"| {f} | {v['scored']} | {v['accuracy'] * 100:.1f}% "
                f"| {v['accuracy_exact'] * 100:.1f}% |"
            )
        lines.append("")
    lines += ["Notes:"] + [f"- {n}" for n in report["scores"]["scoring_notes"]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m docduel.eval")
    ap.add_argument("--model", required=True, help="model key from config/models.yaml")
    ap.add_argument("--split", required=True, choices=list(SPLITS))
    ap.add_argument("--prompt", required=True, help="for example extract_v1 or categorise_v1")
    ap.add_argument(
        "--confirm-test", action="store_true", help="required to run on the frozen test set"
    )
    ap.add_argument("--limit", type=int, default=None, help="only the first N documents")
    ap.add_argument("--max-usd", type=float, default=0.10, help="stop spending after this")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument(
        "--rescore",
        action="store_true",
        help="re-score the answers saved in the existing report (no model calls, free)",
    )
    args = ap.parse_args(argv)

    task, _, version = args.prompt.rpartition("_")
    if task not in SCORED_TASKS:
        sys.exit(f"--prompt must be one of {[t + '_' + VERSION for t in SCORED_TASKS]}")
    if version != VERSION:
        sys.exit(f"prompt version {version} not available (current: {VERSION})")
    if args.split == DATASET_VERSION and not args.confirm_test:
        sys.exit(
            "Refusing to run on the frozen test set without --confirm-test. "
            "Tune prompts on dev, not test (rule R4)."
        )

    load_dotenv(BACKEND_DIR / ".env")
    models = load_models()
    if args.model not in models:
        sys.exit(f"unknown model key {args.model}; choose from {sorted(models)}")
    spec = models[args.model]
    docs = load_docs(args.split, task)[: args.limit]
    stem = f"eval_{args.model}_{args.split}_{args.prompt}"
    run_at = datetime.now(UTC).isoformat(timespec="seconds")
    if args.rescore:
        results, run_at, steady = load_saved(report_dir() / f"{stem}.json", docs)
        print(f"re-scoring {len(results)} saved answers (no model calls)")
    else:
        print(f"{args.model} on {args.split}: {len(docs)} {task} docs (max ${args.max_usd})")
        if spec.provider == "vllm" and docs:
            # Wake the GPU first so a cold start does not count as busy time (not scored).
            print("waking the GPU (one untimed warm-up request)...")
            await run_all(spec, docs[:1], task, args.max_usd, 1)
        started = time.perf_counter()
        results = await run_all(spec, docs, task, args.max_usd, args.concurrency)
        wall = time.perf_counter() - started
        steady = steady_load(spec, wall, len(docs), args.concurrency)
    ran = [(d, o) for d, o in results if o is not None]
    skipped = [d["id"] for d, o in results if o is None]
    outs = [o for _, o in ran]
    scores = score_extract(ran) if task == "extract" else score_categorise(ran)

    report = {
        "created_at": run_at,
        "scored_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model_key": args.model,
        "model_id": spec.model_id,
        "reasoning_effort": spec.reasoning_effort,
        "split": args.split,
        "prompt": args.prompt,
        "task": task,
        "docs_total": len(docs),
        "docs_scored": len(ran),
        "skipped_budget": skipped,
        "scores": scores,
        "speed_cost": speed_and_cost(outs) | ({"steady_load": steady} if steady else {}),
        "outputs": [{"id": d["id"]} | saved_outcome(o) for d, o in ran],
    }
    out_dir = report_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{stem}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    write_markdown(report, out_dir / f"{stem}.md")
    print(
        "\n".join(
            f"  {k}: {v['display'] if isinstance(v, dict) else v}"
            for k, v in scores["headline"].items()
        )
    )
    label = "run cost" if args.rescore else "spent"
    print(f"  {label} ${report['speed_cost']['cost_usd_total']:.4f}; report: reports/{stem}.json")
    if skipped:
        print(f"  WARNING: {len(skipped)} docs skipped by the --max-usd budget")


if __name__ == "__main__":
    asyncio.run(main())
