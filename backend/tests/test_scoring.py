"""Scoring rules from Plan Section 10 (money edge cases live in test_normalise_cord.py)."""

import pytest

from docduel.scoring import bootstrap, categorise, extract
from docduel.scoring.extract import (
    match_line_items,
    money_equal,
    parse_date,
    relative_score,
    score_extraction,
    text_scores,
)


def gold_receipt(**over):
    base = {
        "vendor_name": None,
        "document_date": None,
        "document_number": None,
        "currency": "IDR",
        "line_items": [
            {"description": "NASI GORENG", "quantity": 1, "unit_price": None, "amount": 25000},
            {"description": "ES TEH", "quantity": 1, "unit_price": None, "amount": 5000},
        ],
        "subtotal": None,
        "tax": None,
        "service_charge": None,
        "discount": None,
        "total": 30000,
        "payment_method": "cash",
    }
    base.update(over)
    return base


# ---- money --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pred", "gold", "ok"),
    [
        (25000, "25.000", True),
        (25000.0, "25,000", True),
        (1250500, "1.250.500", True),
        (25000, "Rp 25.000", True),
        (12.5, "12.50", True),
        (-5000, "-5,000", True),
        (12.51, "12.50", True),  # within 0.01
        (12.52, "12.50", False),
        (None, "12.50", False),
        ("abc", "12.50", False),
    ],
)
def test_money(pred, gold, ok):
    assert money_equal(pred, gold) is ok


# ---- dates --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "iso"),
    [
        ("2026-04-03", "2026-04-03"),
        ("03/04/2026", "2026-04-03"),  # day first
        ("3 Apr 2026", "2026-04-03"),
        ("April 3, 2026", "2026-04-03"),
        ("not a date", None),
        (None, None),
    ],
)
def test_parse_date(value, iso):
    assert parse_date(value) == iso


def test_date_exact_match_only():
    gold = gold_receipt(document_date="2026-04-03")
    assert score_extraction(gold_receipt(document_date="03/04/2026"), gold).fields["document_date"][
        "exact"
    ]
    assert not score_extraction(gold_receipt(document_date="2026-04-04"), gold).fields[
        "document_date"
    ]["exact"]


# ---- short strings ------------------------------------------------------------------


def test_text_exact_and_fuzzy():
    assert text_scores("Joe's Cafe", "joes cafe") == (False, True)
    assert text_scores("JOE'S CAFE", "Joe's Cafe") == (True, True)
    assert text_scores("ACME Pty Ltd", "ACME Pty. Ltd.") == (True, True)  # punctuation
    assert text_scores("INV-00123", "INV 00123") == (True, True)
    assert text_scores("Joes Cafe Pty Ltd", "Joes Cafe") == (False, True)  # token set
    assert text_scores("Bakery", "Joes Cafe") == (False, False)
    assert text_scores(None, "Joes Cafe") == (False, False)


# ---- null ground truth is not scored ------------------------------------------------


def test_only_non_null_fields_scored():
    s = score_extraction(gold_receipt(), gold_receipt())
    assert set(s.fields) == {"currency", "total", "payment_method"}
    assert s.field_total == 3 and s.perfect


# ---- invalid output -----------------------------------------------------------------


def test_invalid_output_scores_zero():
    s = score_extraction(None, gold_receipt())
    assert not s.valid and s.field_correct == 0 and not s.perfect
    assert s.items.tp == 0 and s.items.n_pred == 0 and s.items.n_gold == 2


# ---- line items ---------------------------------------------------------------------


def test_line_items_hungarian_order_free():
    pred = [
        {"description": "Es Teh", "amount": 5000},
        {"description": "Nasi Goreng", "amount": 25000},
    ]
    m = match_line_items(pred, gold_receipt()["line_items"])
    assert (m.tp, m.n_pred, m.n_gold) == (2, 2, 2)


def test_line_items_amount_must_match():
    pred = [{"description": "NASI GORENG", "amount": 26000}]
    m = match_line_items(pred, gold_receipt()["line_items"])
    assert (m.tp, m.n_pred, m.n_gold) == (0, 1, 2)


def test_line_items_description_threshold():
    pred = [{"description": "Mineral water", "amount": 25000}]
    assert match_line_items(pred, gold_receipt()["line_items"]).tp == 0


def test_duplicate_items_pair_by_amount():
    gold = [
        {"description": "BASO TAHU", "amount": 46000},
        {"description": "BASO TAHU", "amount": 23000},
    ]
    pred = [
        {"description": "BASO TAHU", "amount": 23000},
        {"description": "BASO TAHU", "amount": 46000},
    ]
    assert match_line_items(pred, gold).tp == 2


def test_blank_true_amount_matches_on_description():
    gold = [{"description": "BLUS WANITA", "amount": None}]
    pred = [{"description": "BLUS WANITA", "amount": 120000}]
    assert match_line_items(pred, gold).tp == 1
    assert match_line_items([{"description": "Other", "amount": 1}], gold).tp == 0


def test_zero_priced_items_ignored():
    gold = gold_receipt()["line_items"] + [{"description": "Plastik kcl", "amount": 0}]
    pred = gold_receipt()["line_items"] + [{"description": "Spicy level Rp 0", "amount": 0}]
    m = match_line_items(pred, gold)
    assert (m.tp, m.n_pred, m.n_gold) == (2, 2, 2)


def test_extra_item_costs_precision_and_perfect():
    pred = gold_receipt()
    pred["line_items"] = pred["line_items"] + [{"description": "TOTAL", "amount": 30000}]
    s = score_extraction(pred, gold_receipt())
    assert s.items.n_pred == 3 and s.items.tp == 2 and not s.perfect


def test_aggregate_micro_and_f1():
    good = score_extraction(gold_receipt(), gold_receipt())
    bad = score_extraction(gold_receipt(total=1, line_items=[]), gold_receipt())
    agg = extract.aggregate([good, bad])
    assert agg["field_accuracy"] == pytest.approx(5 / 6)
    assert agg["line_item_precision"] == 1.0
    assert agg["line_item_recall"] == 0.5
    assert agg["line_item_f1"] == pytest.approx(2 / 3)
    assert agg["perfect_document_rate"] == 0.5
    assert agg["schema_validity"] == 1.0


def test_per_field_counts():
    docs = [score_extraction(gold_receipt(), gold_receipt())]
    pf = extract.per_field(docs)
    assert pf["total"] == {"scored": 1, "accuracy": 1.0, "accuracy_exact": 1.0}
    assert "vendor_name" not in pf


def test_relative_score():
    assert relative_score(0.9, 0.95) == pytest.approx(94.7368, rel=1e-4)
    assert relative_score(0.97, 0.95) > 100  # allowed
    assert relative_score(0.5, 0) is None


# ---- categorise ---------------------------------------------------------------------

GOLD_CAT = {
    "items": [
        {"row_id": 1, "category": "Dining"},
        {"row_id": 2, "category": "Transport"},
        {"row_id": 3, "category": "Groceries"},
    ]
}


def test_categorise_perfect():
    s = categorise.score_categories(GOLD_CAT, GOLD_CAT)
    assert (s.correct, s.rows) == (3, 3)


def test_categorise_missing_and_extra_rows_are_wrong():
    pred = {
        "items": [
            {"row_id": 1, "category": "Dining"},
            {"row_id": 1, "category": "Dining"},  # repeated -> extra
            {"row_id": 9, "category": "Other"},  # unknown -> extra
            {"row_id": 2, "category": "Shopping"},
        ]
    }
    s = categorise.score_categories(pred, GOLD_CAT)
    assert (s.correct, s.rows, s.extra) == (1, 5, 2)
    assert ("Groceries", categorise.MISSING) in s.pairs


def test_categorise_confusion_and_macro_f1():
    pred = {
        "items": [
            {"row_id": 1, "category": "Dining"},
            {"row_id": 2, "category": "Dining"},
            {"row_id": 3, "category": "Groceries"},
        ]
    }
    scores = [categorise.score_categories(pred, GOLD_CAT)]
    m = categorise.confusion(scores)
    assert m["Transport"]["Dining"] == 1 and m["Dining"]["Dining"] == 1
    # Dining F1 = 2/3, Transport 0, Groceries 1 -> mean 5/9
    assert categorise.macro_f1(scores) == pytest.approx(5 / 9)
    agg = categorise.aggregate(scores)
    assert agg["accuracy"] == pytest.approx(2 / 3)


def test_categorise_invalid():
    s = categorise.score_categories(None, GOLD_CAT)
    assert not s.valid and s.correct == 0 and s.rows == 3


# ---- bootstrap ----------------------------------------------------------------------


def test_bootstrap_is_seeded_and_brackets_value():
    docs = [1.0] * 45 + [0.0] * 15

    def mean(xs):
        return sum(xs) / len(xs)

    a = bootstrap.bootstrap_ci(docs, mean)
    b = bootstrap.bootstrap_ci(docs, mean)
    assert a == b
    assert a[0] < 0.75 < a[1]
    assert bootstrap.bootstrap_ci([1.0] * 10, mean) == (1.0, 1.0)


def test_fmt_ci():
    assert bootstrap.fmt_ci(0.912, (0.87, 0.948)) == "91.2% (87.0-94.8)"


def test_live_categorise_rows():
    from docduel.scoring.live import ground_truth_event

    pred = {"items": [{"row_id": 1, "category": "Dining"}, {"row_id": 2, "category": "Other"}]}
    entry = {"id": "tx", "task": "categorise", "label": GOLD_CAT}
    ev = ground_truth_event("categorise", entry, {"m": (True, pred)})
    res = ev["results"]["m"]
    assert res["rows"] == {"1": True, "2": False, "3": False}
    assert res["accuracy"] == pytest.approx(1 / 3)
    assert ground_truth_event("summarise", entry, {"m": (True, pred)}) is None


def test_item_indices_point_at_original_list():
    gold = [{"description": "Tea", "amount": 5}]
    pred = [{"description": "Spicy level", "amount": 0}, {"description": "Tea", "amount": 5}]
    assert match_line_items(pred, gold).correct_predicted() == {1}
