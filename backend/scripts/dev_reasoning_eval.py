"""Task 3.7: compare reasoning settings for gpt-6-luna on 20 DEV documents (never test).

Quick field check only; the full scoring (fuzzy strings, Hungarian line-item matching,
confidence intervals) comes in Phase 5. Stops early if spend passes --max-usd.
Usage: uv run python scripts/dev_reasoning_eval.py --settings none,low,medium --max-usd 0.10
Writes ../reports/dev/reasoning_extract_v1.json
"""

import argparse
import asyncio
import dataclasses
import json
import random
import statistics
import sys
from collections import Counter
from datetime import UTC, datetime

from dotenv import load_dotenv

from docduel.datasets.build import splits_dir
from docduel.models.client import client_for
from docduel.models.registry import load_models
from docduel.runs.orchestrator import run_model
from docduel.runs.prompting import build_prompt
from docduel.scoring.normalise import normalise_text, parse_amount
from docduel.settings import BACKEND_DIR, REPO_DIR
from docduel.testset import is_test_document

load_dotenv(BACKEND_DIR / ".env")
SEED = 2026
MONEY = ("subtotal", "tax", "service_charge", "discount", "total")
TEXT = ("vendor_name", "document_date", "document_number", "currency", "payment_method")


def pick_docs(n_cord: int, n_invoice: int) -> list[dict]:
    rows = [json.loads(line) for line in (splits_dir() / "dev.jsonl").open(encoding="utf-8")]
    rows = [r for r in rows if r["task"] == "extract" and r["split"] == "dev"]
    rng = random.Random(SEED)
    cord = sorted((r for r in rows if r["source"] == "cord"), key=lambda r: r["id"])
    inv = sorted((r for r in rows if r["source"] == "synthetic_invoice"), key=lambda r: r["id"])
    docs = rng.sample(cord, n_cord) + rng.sample(inv, n_invoice)
    if any(is_test_document(d["sha256"]) for d in docs):
        sys.exit("LEAK: a test document is in the dev sample")
    return docs


def _money_ok(pred, gold) -> bool:
    p, g = parse_amount(pred), parse_amount(gold)
    return p is not None and abs(p - g) <= 0.01


def score(pred: dict | None, gold: dict) -> Counter:
    """Counts of correct/total per field, only where ground truth is not null (Plan 10.1)."""
    c: Counter = Counter()
    for f in MONEY + TEXT:
        if gold[f] is None:
            continue
        c[f"{f}_total"] += 1
        if pred is None:
            continue
        ok = (
            _money_ok(pred[f], gold[f])
            if f in MONEY
            else (normalise_text(pred[f]) == normalise_text(gold[f]))
        )
        c[f"{f}_ok"] += ok
    # Line items (rough): how many gold amounts appear in the prediction's amounts.
    gold_amounts = Counter(str(parse_amount(i["amount"])) for i in gold["line_items"])
    pred_amounts = Counter(
        str(parse_amount(i["amount"])) for i in (pred or {}).get("line_items", [])
    )
    c["items_gold"] += sum(gold_amounts.values())
    c["items_pred"] += sum(pred_amounts.values())
    c["items_match"] += sum((gold_amounts & pred_amounts).values())
    return c


async def evaluate(effort: str, docs: list[dict], budget: dict, max_usd: float) -> dict:
    spec = dataclasses.replace(
        load_models()["openai"], key=f"luna-{effort}", reasoning_effort=effort
    )
    sem = asyncio.Semaphore(4)

    async def noop(*_):
        return None

    async def one(doc: dict):
        async with sem:
            if budget["spent"] > max_usd:
                return doc, None
            prompt = build_prompt("extract", text=doc["text"])
            out = await run_model(spec, prompt, noop, client_for)
            budget["spent"] += out.cost_usd or 0
            return doc, out

    results = await asyncio.gather(*(one(d) for d in docs))
    totals: Counter = Counter()
    per_doc, lat, costs, reasoning, valid, errors = [], [], [], [], 0, Counter()
    for doc, out in results:
        if out is None:
            errors["skipped_budget"] += 1
            continue
        if out.error_code:
            errors[out.error_code] += 1
        valid += bool(out.schema_valid)
        s = score(out.parsed if out.schema_valid else None, doc["label"])
        totals += s
        field_ok = sum(v for k, v in s.items() if k.endswith("_ok"))
        field_total = sum(v for k, v in s.items() if k.endswith("_total"))
        per_doc.append(
            {
                "id": doc["id"],
                "fields": f"{field_ok}/{field_total}",
                "items": f"{s['items_match']}/{s['items_gold']}",
            }
        )
        if out.latency_ms is not None:
            lat.append(out.latency_ms)
            costs.append(out.cost_usd or 0)
            reasoning.append(out.reasoning_tokens)
    ok = sum(v for k, v in totals.items() if k.endswith("_ok"))
    tot = sum(v for k, v in totals.items() if k.endswith("_total"))
    prec = totals["items_match"] / totals["items_pred"] if totals["items_pred"] else 0
    rec = totals["items_match"] / totals["items_gold"] if totals["items_gold"] else 0
    return {
        "reasoning_effort": effort,
        "docs": len(docs),
        "schema_valid": valid,
        "field_accuracy": round(ok / tot, 4) if tot else None,
        "per_field": {
            f: f"{totals[f + '_ok']}/{totals[f + '_total']}"
            for f in MONEY + TEXT
            if totals[f + "_total"]
        },
        "line_item_f1_rough": round(2 * prec * rec / (prec + rec), 4) if prec + rec else 0,
        "latency_ms_p50": round(statistics.median(lat)) if lat else None,
        "latency_ms_max": round(max(lat)) if lat else None,
        "reasoning_tokens_mean": round(statistics.mean(reasoning)) if reasoning else None,
        "cost_usd_total": round(sum(costs), 6),
        "cost_per_1000_docs_usd": round(1000 * sum(costs) / len(costs), 4) if costs else None,
        "errors": dict(errors),
        "per_doc": per_doc,
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--settings", default="none,low,medium")
    ap.add_argument("--cord", type=int, default=15)
    ap.add_argument("--invoices", type=int, default=5)
    ap.add_argument("--max-usd", type=float, default=0.10)
    args = ap.parse_args()
    docs = pick_docs(args.cord, args.invoices)
    budget = {"spent": 0.0}
    runs = []
    for effort in args.settings.split(","):
        r = await evaluate(effort, docs, budget, args.max_usd)
        runs.append(r)
        print(
            f"{effort:>6}: fields {r['field_accuracy']:.1%}  items F1 {r['line_item_f1_rough']:.1%}"
            f"  valid {r['schema_valid']}/{r['docs']}  p50 {r['latency_ms_p50']} ms"
            f"  thinking {r['reasoning_tokens_mean']} tok  cost ${r['cost_usd_total']:.4f}"
            f"  errors {r['errors']}"
        )
    out = REPO_DIR / "reports" / "dev" / "reasoning_extract_v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "split": "dev",
        "prompt_version": "extract_v1",
        "model_id": load_models()["openai"].model_id,
        "doc_ids": [d["id"] for d in docs],
        "note": "Quick dev check for task 3.7; not the Phase 5 benchmark.",
        "runs": runs,
        "total_spent_usd": round(budget["spent"], 6),
    }
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"total spent ${budget['spent']:.4f}; report: {out.relative_to(REPO_DIR)}")


if __name__ == "__main__":
    asyncio.run(main())
