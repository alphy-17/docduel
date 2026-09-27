"""Ground-truth scoring for a live Duel run on a frozen test document (Plan task 5.5).

When an uploaded file's hash matches a test-set document, each model's answer is scored
with the same Section 10 rules as the benchmark, and the page shows right (green) and
wrong (red) instead of agreement.
"""

from typing import Any

from docduel.scoring import categorise, extract

SCORED = ("extract", "categorise")


def score_model(task: str, parsed: Any, label: dict) -> dict[str, Any]:
    if task == "extract":
        s = extract.score_extraction(parsed if isinstance(parsed, dict) else None, label)
        return {
            "fields": {name: v["fuzzy"] for name, v in s.fields.items()},
            "expected": {name: label.get(name) for name in s.fields},
            "correct_items": sorted(s.items.correct_predicted()),
            "items": {"tp": s.items.tp, "pred": s.items.n_pred, "gold": s.items.n_gold},
            "field_accuracy": s.field_correct / s.field_total if s.field_total else None,
            "line_item_f1": extract.f1(s.items.tp, s.items.n_pred, s.items.n_gold)[2],
            "perfect": s.perfect,
        }
    c = categorise.score_categories(parsed if isinstance(parsed, dict) else None, label)
    truth = {int(i["row_id"]): i["category"] for i in label["items"]}
    return {
        "rows": {
            str(rid): gold == pred for rid, (gold, pred) in zip(sorted(truth), c.pairs, strict=True)
        },
        "expected": {str(k): v for k, v in truth.items()},
        "accuracy": c.correct / c.rows if c.rows else None,
    }


def ground_truth_event(
    task: str, entry: dict, answers: dict[str, tuple[bool | None, Any]]
) -> dict[str, Any] | None:
    """Build the score.completed payload. `answers` maps model key -> (schema_valid, parsed)."""
    if task not in SCORED or entry.get("task") != task:
        return None
    return {
        "mode": "ground_truth",
        "test_document_id": entry["id"],
        "results": {
            key: score_model(task, parsed if valid else None, entry["label"])
            for key, (valid, parsed) in answers.items()
        },
    }
