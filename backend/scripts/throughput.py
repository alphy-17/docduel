"""How cheap does our GPU get when it works on many documents at once? (Phase 9, rule R5)

  uv run python scripts/throughput.py            # about 15 min of L4 time, about $0.20

The Duel runs one document at a time, which is the most expensive way to use a GPU: we pay
per second whether the GPU is busy or not. vLLM can work on many requests together, so the
cost per document should fall as more run at once. This measures it instead of guessing.

For each level (1, 8, 16, 32 requests in flight) it sends fresh extract documents from the
TRAIN split (speed only, nothing is scored, so no test or dev data is used), times the whole
batch on a warm GPU and turns GPU seconds into cost per 1,000 documents with the L4 price in
config/pricing.yaml. OpenAI's cost per 1,000 documents is read from its test-set report.
Writes reports/throughput_small-ft-r1.json and .md.
"""

import asyncio
import json
import statistics
import sys
import time
from datetime import UTC, datetime

from dotenv import load_dotenv

from docduel.datasets.build import _read_jsonl, splits_dir
from docduel.eval import report_dir, run_all, steady_load
from docduel.models.registry import load_models
from docduel.settings import BACKEND_DIR
from docduel.testset import is_test_document

MODEL = "small-ft-r1"
LEVELS = [(1, 8), (8, 32), (16, 64), (32, 128)]  # (requests in flight, documents)


def train_docs(n: int) -> list[dict]:
    rows = [r for r in _read_jsonl(splits_dir() / "train.jsonl") if r["task"] == "extract"]
    if any(is_test_document(r["sha256"]) for r in rows):
        sys.exit("LEAK: test documents in train")
    if len(rows) < n:
        sys.exit(f"need {n} train extract docs, found {len(rows)}")
    return rows[:n]


async def main() -> None:
    load_dotenv(BACKEND_DIR / ".env")
    spec = load_models()[MODEL]
    docs = train_docs(1 + sum(n for _, n in LEVELS))
    print("waking the GPU (one untimed request; can take about 5 minutes when cold)...")
    await run_all(spec, docs[:1], "extract", 5.0, 1)
    pos, levels = 1, []
    for concurrency, n in LEVELS:
        batch = docs[pos : pos + n]  # fresh documents each level, so no cached answers help
        pos += n
        print(f"\n{concurrency} at once, {n} documents")
        started = time.perf_counter()
        results = await run_all(spec, batch, "extract", 5.0, concurrency)
        wall = time.perf_counter() - started
        outs = [o for _, o in results if o is not None]
        ok = [o for o in outs if o.schema_valid]
        steady = steady_load(spec, wall, len(batch), concurrency)
        levels.append(
            steady
            | {
                "valid_answers": len(ok),
                "latency_ms_p50": (
                    round(statistics.median(o.latency_ms for o in ok)) if ok else None
                ),
                "output_tokens_mean": round(statistics.mean(o.output_tokens for o in outs)),
            }
        )
        print(f"  {wall:.1f} s -> ${steady['cost_per_1000_docs_usd']:.3f} per 1,000 docs")

    openai = json.loads((report_dir() / "eval_openai_test-v1_extract_v1.json").read_text())
    report = {
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model_key": MODEL,
        "gpu": spec.gpu,
        "documents": "train split, extract (speed only, not scored)",
        "levels": levels,
        "openai_cost_per_1000_docs_usd": openai["speed_cost"]["cost_per_1000_docs_usd"],
    }
    out = report_dir() / f"throughput_{MODEL}"
    out.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    rows = "\n".join(
        f"| {lv['concurrency']} | {lv['docs']} | {lv['wall_seconds']} | "
        f"{lv['latency_ms_p50']} | ${lv['cost_per_1000_docs_usd']:.3f} |"
        for lv in levels
    )
    out.with_suffix(".md").write_text(
        f"# Throughput: {MODEL} on one {spec.gpu}\n\n"
        f"Created {report['created_at']}. Train-split extract documents, speed only.\n\n"
        "| In flight | Documents | Batch time (s) | Median time per doc (ms) "
        "| GPU cost per 1,000 docs |\n"
        "|---|---|---|---|---|\n"
        f"{rows}\n\n"
        f"OpenAI ({openai['model_id']}) on the test set: "
        f"${report['openai_cost_per_1000_docs_usd']:.3f} per 1,000 docs.\n",
        encoding="utf-8",
    )
    print(f"\nOpenAI: ${report['openai_cost_per_1000_docs_usd']:.3f} per 1,000 docs")
    print(f"report: reports/{out.name}.json")


if __name__ == "__main__":
    asyncio.run(main())
