"""Fine-tuning set builder (Plan 7.1): answer format, CORD null masking, dev slice."""

import json

import pytest

from docduel.datasets import sft

LABEL = {
    "vendor_name": None,
    "document_date": None,
    "document_number": None,
    "currency": "IDR",
    "line_items": [{"description": "ES TEH", "quantity": 1, "unit_price": None, "amount": 5000}],
    "subtotal": None,
    "tax": None,
    "service_charge": None,
    "discount": None,
    "total": 5000,
    "payment_method": "cash",
}


def test_answer_matches_schema_order_and_fewshot_style():
    answer = sft.answer_json("extract", LABEL)
    assert list(json.loads(answer)) == list(LABEL)
    assert '"amount": 5000.0' in answer  # floats, same as the few-shot examples


def test_null_spans_cover_only_unlabelled_nulls():
    answer = sft.answer_json("extract", LABEL)
    spans = sft.null_spans(answer)
    assert len(spans) == 3
    assert all(answer[a:b] == "null" for a, b in spans)
    named = dict(LABEL, vendor_name="BLUE FIG")
    assert len(sft.null_spans(sft.answer_json("extract", named))) == 2


def test_example_uses_eval_prompt_and_masks_cord_only():
    row = {
        "id": "c1",
        "task": "extract",
        "source": "cord",
        "sha256": "h",
        "text": "T",
        "label": LABEL,
    }
    ex = sft.to_example(row)
    assert ex["messages"][0]["role"] == "system"
    assert ex["messages"][-1]["content"].endswith("T\n</document>")
    assert len(ex["mask_spans"]) == 3
    inv = sft.to_example(dict(row, source="synthetic_invoice"))
    assert inv["mask_spans"] == []


def test_categorise_answer():
    label = {"items": [{"row_id": 1, "category": "Transport"}]}
    assert json.loads(sft.answer_json("categorise", label)) == label


def test_dev_slice_is_balanced_and_stable():
    rows = [{"id": f"a{i:02d}", "source": "cord"} for i in range(50)]
    rows += [{"id": f"b{i:02d}", "source": "synthetic_invoice"} for i in range(5)]
    picked = sft.dev_slice(rows, 20)
    assert len(picked) == 20
    assert sum(r["source"] == "synthetic_invoice" for r in picked) == 5
    assert picked == sft.dev_slice(list(reversed(rows)), 20)


def test_round_two_adds_corrections_three_times_and_marks_them(tmp_path, monkeypatch):
    splits = tmp_path / "splits"
    splits.mkdir()
    row = {
        "id": "c1",
        "task": "extract",
        "source": "cord",
        "sha256": "h",
        "text": "T",
        "label": LABEL,
    }
    (splits / "train.jsonl").write_text(json.dumps(row) + "\n")
    (splits / "dev.jsonl").write_text(json.dumps(dict(row, id="d1", sha256="d")) + "\n")
    (splits / "test.jsonl").write_text("")
    fixed = dict(LABEL, vendor_name="Orchard", total=12.5)
    corr = [dict(row, id="inv_G_1", sha256="g", source="correction", label=fixed)]
    marked = {}
    monkeypatch.setattr(sft, "splits_dir", lambda: splits)
    monkeypatch.setattr(sft, "check_from_disk", lambda extra_train=None: [])
    monkeypatch.setattr(sft, "load_corrections", lambda: corr)
    monkeypatch.setattr(sft, "mark_used", lambda ids, n: marked.update({n: ids}))
    out = sft.build(tmp_path / "train", round_no=2, min_corrections=1)
    lines = (tmp_path / "train" / "sft_r2_train.jsonl").read_text().splitlines()
    exs = [json.loads(x) for x in lines]
    assert [e["id"] for e in exs] == ["c1", "inv_G_1#1", "inv_G_1#2", "inv_G_1#3"]
    assert json.loads(exs[1]["answer"])["vendor_name"] == "Orchard"
    assert exs[1]["mask_spans"] == []  # corrections are fully labelled
    assert out["counts"]["train"] == {"cord:extract": 1, "correction:extract": 3}
    assert marked == {2: ["inv_G_1"]}
    with pytest.raises(SystemExit, match="only 1 verified"):
        sft.build(tmp_path / "train", round_no=2, min_corrections=40)
