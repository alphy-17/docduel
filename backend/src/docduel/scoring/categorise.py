"""Score `categorise` answers (Plan Section 10.2): accuracy, macro-F1, confusion matrix.

A missing row_id counts as wrong for that row. An extra row_id (not in the ground truth,
or repeated) also counts as one wrong row.
"""

from dataclasses import dataclass

from docduel.schemas.extraction import CATEGORIES

MISSING = "(missing)"


@dataclass
class CatScore:
    valid: bool
    correct: int
    rows: int  # ground-truth rows + extra rows
    pairs: list[tuple[str, str]]  # (gold, predicted or MISSING) per ground-truth row
    extra: int


def score_categories(pred: dict | None, gold: dict) -> CatScore:
    gold_map = {int(i["row_id"]): i["category"] for i in gold["items"]}
    pred_map: dict[int, str] = {}
    extra = 0
    for item in (pred or {}).get("items", []):
        rid = int(item["row_id"])
        if rid not in gold_map or rid in pred_map:
            extra += 1
        else:
            pred_map[rid] = item["category"]
    pairs = [(g, pred_map.get(rid, MISSING)) for rid, g in sorted(gold_map.items())]
    correct = sum(g == p for g, p in pairs)
    return CatScore(pred is not None, correct, len(pairs) + extra, pairs, extra)


def confusion(scores: list[CatScore]) -> dict[str, dict[str, int]]:
    """rows = true category, columns = predicted category (plus MISSING)."""
    cols = list(CATEGORIES) + [MISSING]
    matrix = {g: dict.fromkeys(cols, 0) for g in CATEGORIES}
    for s in scores:
        for g, p in s.pairs:
            matrix[g][p if p in matrix[g] else MISSING] += 1
    return matrix


def macro_f1(scores: list[CatScore]) -> float:
    """Mean F1 over the categories that appear in the ground truth or the predictions."""
    pairs = [pair for s in scores for pair in s.pairs]
    f1s = []
    for c in CATEGORIES:
        tp = sum(g == c and p == c for g, p in pairs)
        fp = sum(g != c and p == c for g, p in pairs)
        fn = sum(g == c and p != c for g, p in pairs)
        if tp + fp + fn == 0:
            continue
        f1s.append(2 * tp / (2 * tp + fp + fn))
    return sum(f1s) / len(f1s) if f1s else 0.0


def aggregate(scores: list[CatScore]) -> dict[str, float]:
    rows = sum(s.rows for s in scores)
    n = len(scores)
    return {
        "accuracy": sum(s.correct for s in scores) / rows if rows else 0.0,
        "macro_f1": macro_f1(scores),
        "schema_validity": sum(s.valid for s in scores) / n if n else 0.0,
    }
