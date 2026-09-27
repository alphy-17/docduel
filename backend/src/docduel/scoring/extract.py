"""Score one `extract` answer against its ground truth (Plan Section 10.1).

Rules
- Only fields whose ground truth is not null are scored (CORD has no vendor or date).
- Money: both sides parsed to Decimal, correct when the difference is at most 0.01.
- Dates: both parsed to ISO, correct only on an exact match.
- Short strings: normalised, scored exact and fuzzy (rapidfuzz token_set_ratio >= 90).
  The headline uses fuzzy.
- Line items: zero-priced items (modifiers, free bags) are dropped from both sides
  (Owner decision 2026-09-27). The rest are paired one to one with the Hungarian algorithm;
  a pair is correct when description similarity >= 80 and the amounts match. When the
  true amount is blank (CORD sometimes leaves it out), only the description must match.
- An invalid output scores zero on every field of that document.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

import numpy as np
from rapidfuzz import fuzz
from scipy.optimize import linear_sum_assignment

from docduel.scoring.normalise import normalise_text, parse_amount

MONEY_FIELDS = ("subtotal", "tax", "service_charge", "discount", "total")
TEXT_FIELDS = ("vendor_name", "document_number", "currency", "payment_method")
DATE_FIELDS = ("document_date",)
FIELDS = (
    ("vendor_name", "document_date", "document_number", "currency")
    + MONEY_FIELDS
    + ("payment_method",)
)
FUZZY_THRESHOLD = 90
ITEM_THRESHOLD = 80
MONEY_TOLERANCE = Decimal("0.01")

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%d/%m/%y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
)


def parse_date(value: object) -> str | None:
    """Return an ISO date string, or None. Slash dates are read day first (AU style)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    s = " ".join(str(value).strip().split())
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def money_equal(pred: object, gold: object) -> bool:
    p, g = parse_amount(pred), parse_amount(gold)
    if g is None:
        return p is None
    return p is not None and abs(p - g) <= MONEY_TOLERANCE


def text_scores(pred: object, gold: object) -> tuple[bool, bool]:
    """(exact, fuzzy) for a short string field."""
    p, g = normalise_text(pred), normalise_text(gold)
    if not p:
        return False, False
    exact = p == g
    return exact, exact or fuzz.token_set_ratio(p, g) >= FUZZY_THRESHOLD


def description_similarity(pred: object, gold: object) -> float:
    return float(fuzz.token_set_ratio(normalise_text(pred), normalise_text(gold)))


def _priced(items: list[dict] | None) -> list[tuple[int, dict]]:
    """Drop zero-priced items (Owner decision: ignore modifiers and free extras).

    Returns (original index, item) so results can point back at the model's own list.
    """
    kept = []
    for idx, item in enumerate(items or []):
        amount = parse_amount(item.get("amount"))
        if amount is not None and amount == 0:
            continue
        kept.append((idx, item))
    return kept


@dataclass
class ItemMatch:
    tp: int
    n_pred: int
    n_gold: int
    # (predicted index, true index, similarity, correct), indices into the original lists
    pairs: list[tuple[int, int, float, bool]] = field(default_factory=list)

    def correct_predicted(self) -> set[int]:
        return {p for p, _, _, ok in self.pairs if ok}


def match_line_items(pred_items: list[dict] | None, gold_items: list[dict] | None) -> ItemMatch:
    pred, gold = _priced(pred_items), _priced(gold_items)
    if not pred or not gold:
        return ItemMatch(0, len(pred), len(gold))
    sim = np.zeros((len(pred), len(gold)))
    amount_ok = np.zeros((len(pred), len(gold)), dtype=bool)
    for i, (_, p) in enumerate(pred):
        for j, (_, g) in enumerate(gold):
            sim[i, j] = description_similarity(p.get("description"), g.get("description"))
            # A blank true price cannot be checked, so only the description counts.
            amount_ok[i, j] = g.get("amount") is None or money_equal(
                p.get("amount"), g.get("amount")
            )
    # Pair by similarity, with a bonus for matching amounts so duplicates pair correctly.
    rows, cols = linear_sum_assignment(-(sim + 20 * amount_ok))
    pairs = []
    for i, j in zip(rows, cols, strict=True):
        ok = bool(sim[i, j] >= ITEM_THRESHOLD and amount_ok[i, j])
        pairs.append((pred[i][0], gold[j][0], float(sim[i, j]), ok))
    return ItemMatch(sum(p[3] for p in pairs), len(pred), len(gold), pairs)


@dataclass
class DocScore:
    """Per-document result. `fields` maps field -> {"exact": bool, "fuzzy": bool}."""

    valid: bool
    fields: dict[str, dict[str, bool]]
    items: ItemMatch

    @property
    def field_correct(self) -> int:
        return sum(f["fuzzy"] for f in self.fields.values())

    @property
    def field_correct_exact(self) -> int:
        return sum(f["exact"] for f in self.fields.values())

    @property
    def field_total(self) -> int:
        return len(self.fields)

    @property
    def perfect(self) -> bool:
        """Every scored field right and every priced line item matched, nothing extra."""
        items_ok = self.items.tp == self.items.n_gold == self.items.n_pred
        return self.valid and self.field_correct == self.field_total and items_ok


def score_extraction(pred: dict | None, gold: dict) -> DocScore:
    """Score one document. Pass pred=None when the output was invalid."""
    valid = pred is not None
    p = pred or {}
    fields: dict[str, dict[str, bool]] = {}
    for name in FIELDS:
        g = gold.get(name)
        if g is None:
            continue
        if not valid:
            fields[name] = {"exact": False, "fuzzy": False}
        elif name in MONEY_FIELDS:
            ok = money_equal(p.get(name), g)
            fields[name] = {"exact": ok, "fuzzy": ok}
        elif name in DATE_FIELDS:
            pd, gd = parse_date(p.get(name)), parse_date(g)
            ok = pd is not None and pd == gd
            fields[name] = {"exact": ok, "fuzzy": ok}
        else:
            exact, fuzzy = text_scores(p.get(name), g)
            fields[name] = {"exact": exact, "fuzzy": fuzzy}
    items = match_line_items(p.get("line_items") if valid else [], gold.get("line_items"))
    return DocScore(valid, fields, items)


def f1(tp: int, n_pred: int, n_gold: int) -> tuple[float, float, float]:
    precision = tp / n_pred if n_pred else 0.0
    recall = tp / n_gold if n_gold else 0.0
    f = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f


def aggregate(docs: list[DocScore]) -> dict[str, float]:
    """Headline metrics over a list of documents (micro averages)."""
    n = len(docs)
    ft = sum(d.field_total for d in docs)
    tp = sum(d.items.tp for d in docs)
    npred = sum(d.items.n_pred for d in docs)
    ngold = sum(d.items.n_gold for d in docs)
    precision, recall, item_f1 = f1(tp, npred, ngold)
    return {
        "field_accuracy": sum(d.field_correct for d in docs) / ft if ft else 0.0,
        "field_accuracy_exact": sum(d.field_correct_exact for d in docs) / ft if ft else 0.0,
        "line_item_precision": precision,
        "line_item_recall": recall,
        "line_item_f1": item_f1,
        "perfect_document_rate": sum(d.perfect for d in docs) / n if n else 0.0,
        "schema_validity": sum(d.valid for d in docs) / n if n else 0.0,
    }


def per_field(docs: list[DocScore]) -> dict[str, dict[str, float | int]]:
    out: dict[str, dict[str, float | int]] = {}
    for name in FIELDS:
        scored = [d.fields[name] for d in docs if name in d.fields]
        if not scored:
            continue
        out[name] = {
            "scored": len(scored),
            "accuracy": sum(s["fuzzy"] for s in scored) / len(scored),
            "accuracy_exact": sum(s["exact"] for s in scored) / len(scored),
        }
    return out


def relative_score(ours: float, openai: float) -> float | None:
    """Plan 10.4: our field accuracy / OpenAI field accuracy x 100. Never shown alone."""
    return None if not openai else ours / openai * 100
