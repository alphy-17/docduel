"""Prompt building and few-shot safety checks."""

import json

import pytest

from docduel.runs.prompting import PROMPTS_DIR, build_prompt
from docduel.schemas.extraction import ReceiptExtraction, TransactionCategories
from docduel.testset import is_test_document

FEWSHOT = {"extract_v1": ReceiptExtraction, "categorise_v1": TransactionCategories}


def test_summarise_has_schema_and_document() -> None:
    p = build_prompt("summarise", text="Invoice 42 from Acme, total $10")
    assert p.version == "summarise_v1"
    assert [m["role"] for m in p.messages] == ["system", "user"]
    assert "Invoice 42" in p.messages[-1]["content"]
    assert p.response_format["json_schema"]["name"] == "SummaryOutput"


def test_custom_is_plain_text_and_needs_instructions() -> None:
    p = build_prompt("custom", text="doc", instructions="  Who is the vendor? ")
    assert p.response_format is None
    assert p.messages[-1]["content"].endswith("Instruction: Who is the vendor?")
    with pytest.raises(ValueError):
        build_prompt("custom", text="doc", instructions=" ")


def test_describe_sends_image_as_data_url() -> None:
    p = build_prompt("describe", image=(b"\x89PNGfake", "image/png"))
    parts = p.messages[-1]["content"]
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert p.response_format is None
    with pytest.raises(ValueError):
        build_prompt("describe", text="no image")


def test_unknown_task_rejected() -> None:
    with pytest.raises(ValueError):
        build_prompt("translate", text="x")  # type: ignore[arg-type]


@pytest.mark.parametrize("name", sorted(FEWSHOT))
def test_fewshot_files_are_valid_train_examples(name: str) -> None:
    path = PROMPTS_DIR / "fewshot" / f"{name}.json"
    if not path.exists():
        pytest.skip("few-shot file not built yet (python -m docduel.datasets.fewshot)")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["source_split"] == "train"
    assert len(data["examples"]) == 3
    for ex in data["examples"]:
        FEWSHOT[name].model_validate(ex["output"])  # labels match the schema
        assert not is_test_document(ex["sha256"])  # rule R4: never a test document
        assert ex["text"].strip()
    task = name.removesuffix("_v1")
    p = build_prompt(task, text="new document")  # type: ignore[arg-type]
    roles = [m["role"] for m in p.messages]
    assert roles == ["system"] + ["user", "assistant"] * 3 + ["user"]
