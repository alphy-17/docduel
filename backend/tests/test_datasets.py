import json

from docduel.datasets.invoices import PLAN as INV_PLAN
from docduel.datasets.invoices import generate as gen_invoices
from docduel.datasets.invoices import make_invoice
from docduel.datasets.leakage import find_leaks
from docduel.datasets.transactions import HELD_OUT_MERCHANTS, TRAIN_MERCHANTS, merchant_names
from docduel.datasets.transactions import generate as gen_tx


def test_merchant_lists_never_overlap():
    assert not merchant_names(TRAIN_MERCHANTS) & merchant_names(HELD_OUT_MERCHANTS)
    assert set(TRAIN_MERCHANTS) == set(HELD_OUT_MERCHANTS)  # same 8 categories


def test_invoice_totals_are_consistent():
    for t in "ABCDEFG":
        for i in range(20):
            inv = make_invoice(t, i)
            base = inv.subtotal - (inv.discount or 0) + (inv.service or 0)
            assert inv.total == (base if inv.tax_inclusive else base + inv.tax)
            assert inv.subtotal == sum(a for *_, a in inv.items)


def test_generators_are_deterministic_and_test_uses_template_f(tmp_path):
    plan = {"train": ("ABCDE", 6), "test": ("F", 2)}
    gen_invoices(tmp_path / "a", plan)
    gen_invoices(tmp_path / "b", plan)
    a = (tmp_path / "a" / "test" / "labels.jsonl").read_text()
    assert a == (tmp_path / "b" / "test" / "labels.jsonl").read_text()
    recs = [json.loads(x) for x in a.splitlines()]
    assert {r["template"] for r in recs} == {"F"}
    assert {r["rendered_as"] for r in recs} == {"text_pdf", "scan"}
    assert "F" not in INV_PLAN["train"][0] and "G" not in INV_PLAN["train"][0]


def test_transaction_test_split_uses_only_held_out_merchants(tmp_path):
    gen_tx(tmp_path, {"train": ("train", 2, 30), "test": ("held_out", 2, 20)})
    held = merchant_names(HELD_OUT_MERCHANTS)
    for line in (tmp_path / "test" / "labels.jsonl").read_text().splitlines():
        assert set(json.loads(line)["merchants"]) <= held


def _rec(id_, split, sha, merchants=()):
    return {"id": id_, "split": split, "sha256": sha, "merchants": list(merchants)}


def test_leakage_check_passes_on_clean_splits():
    train = [_rec("a", "train", "h1", ["WOOLWORTHS"]), _rec("b", "dev", "h2")]
    test = [_rec("t", "test", "h9", ["NANDOS"])]
    assert find_leaks(train, test) == []


def test_leakage_check_catches_planted_duplicate_and_merchant():
    train = [_rec("a", "train", "h1"), _rec("planted", "train", "h9", ["nandos"])]
    test = [_rec("t", "test", "h9", ["NANDOS"])]
    problems = find_leaks(train, test)
    assert any("file hash overlap" in p for p in problems)
    assert any("merchant overlap" in p for p in problems)
