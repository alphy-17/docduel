"""Fine-tuning set builder (Plan 7.1): answer format, CORD null masking, dev slice."""

import json

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
