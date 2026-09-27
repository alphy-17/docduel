"""Evaluation CLI (Plan 5.2) with a fake model: test-set guard, report files, scoring."""

import asyncio
import json

import pytest

from docduel import eval as ev
from docduel.models.client import Delta, Finished

GOLD = {
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


class FakeClient:
    def __init__(self, answers: dict[str, str]) -> None:
        self.answers = answers

    async def stream(self, messages, response_format=None):
        content = messages[-1]["content"]
        text = next(v for k, v in self.answers.items() if k in content)
        yield Delta(text)
        yield Finished(text, 1000, 0, 200, 0, 10.0, 40.0)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    splits = tmp_path / "splits"
    splits.mkdir()
    docs = [
        {
            "id": f"d{i}",
            "task": "extract",
            "source": "cord",
            "sha256": f"h{i}",
            "text": f"ES TEH 5.000 TOTAL 5.000 TUNAI doc{i}",
            "label": GOLD,
        }
        for i in range(3)
    ]
    for name in ("dev.jsonl", "test.jsonl"):
        (splits / name).write_text("\n".join(json.dumps(d) for d in docs) + "\n")
    wrong = dict(GOLD, total=6000)
    answers = {
        "ES TEH 5.000 TOTAL 5.000 TUNAI doc0": json.dumps(GOLD),
        "ES TEH 5.000 TOTAL 5.000 TUNAI doc1": json.dumps(wrong),
        "ES TEH 5.000 TOTAL 5.000 TUNAI doc2": "not json",
    }
    monkeypatch.setattr(ev, "splits_dir", lambda: splits)
    monkeypatch.setattr(ev, "report_dir", lambda: tmp_path / "reports")
    monkeypatch.setattr(ev, "client_for", lambda spec: FakeClient(answers))
    monkeypatch.setattr(ev, "is_test_document", lambda h: False)
    return tmp_path


def test_refuses_test_split_without_confirm(setup):
    with pytest.raises(SystemExit, match="confirm-test"):
        asyncio.run(ev.main(["--model", "openai", "--split", "test-v1", "--prompt", "extract_v1"]))


def test_test_split_checks_manifest(setup):
    with pytest.raises(SystemExit, match="manifest"):
        asyncio.run(
            ev.main(
                [
                    "--model",
                    "openai",
                    "--split",
                    "test-v1",
                    "--prompt",
                    "extract_v1",
                    "--confirm-test",
                ]
            )
        )


def test_dev_leak_check(setup, monkeypatch):
    monkeypatch.setattr(ev, "is_test_document", lambda h: h == "h1")
    with pytest.raises(SystemExit, match="LEAK"):
        asyncio.run(ev.main(["--model", "openai", "--split", "dev", "--prompt", "extract_v1"]))


def test_rejects_unscored_prompt(setup):
    with pytest.raises(SystemExit, match="--prompt"):
        asyncio.run(ev.main(["--model", "openai", "--split", "dev", "--prompt", "summarise_v1"]))


def test_dev_run_writes_reports(setup):
    asyncio.run(ev.main(["--model", "openai", "--split", "dev", "--prompt", "extract_v1"]))
    path = setup / "reports" / "eval_openai_dev_extract_v1.json"
    report = json.loads(path.read_text())
    assert (setup / "reports" / "eval_openai_dev_extract_v1.md").exists()
    h = report["scores"]["headline"]
    # doc0 3/3 fields, doc1 2/3, doc2 invalid 0/3 -> 5/9
    assert h["field_accuracy"]["value"] == pytest.approx(5 / 9, abs=1e-4)
    assert h["schema_validity"]["value"] == pytest.approx(2 / 3, abs=1e-4)
    assert h["perfect_document_rate"]["value"] == pytest.approx(1 / 3, abs=1e-4)
    lo, hi = h["field_accuracy"]["ci95"]
    assert lo <= 5 / 9 <= hi
    assert report["scores"]["worst_failures"][0] == "d2"
    assert report["docs_scored"] == 3 and report["speed_cost"]["cost_usd_total"] > 0


def test_rescore_uses_saved_answers(setup, monkeypatch):
    args = ["--model", "openai", "--split", "dev", "--prompt", "extract_v1"]
    asyncio.run(ev.main(args))
    first = json.loads((setup / "reports" / "eval_openai_dev_extract_v1.json").read_text())
    assert len(first["outputs"]) == 3 and "raw_output" in first["outputs"][2]

    def boom(spec):
        raise AssertionError("rescore must not call a model")

    monkeypatch.setattr(ev, "client_for", boom)
    asyncio.run(ev.main([*args, "--rescore"]))
    again = json.loads((setup / "reports" / "eval_openai_dev_extract_v1.json").read_text())
    assert again["scores"]["headline"] == first["scores"]["headline"]
    assert again["created_at"] == first["created_at"]
    bad = next(d for d in again["scores"]["per_doc"] if d["id"] == "d1")
    assert bad["line_items"] is None or "expected" in bad["line_items"]


def test_steady_load_cost_for_gpu_model():
    from docduel.models.registry import ModelSpec

    gpu = ModelSpec("small-base", "vllm", "small-base", None, "K", gpu="L4")
    s = ev.steady_load(gpu, wall_seconds=36.0, docs=10, concurrency=4)
    # L4 $0.799/h -> 36 s busy / 10 docs = 3.6 s each -> $0.799 per 1,000 docs
    assert s == {
        "concurrency": 4,
        "wall_seconds": 36.0,
        "docs": 10,
        "cost_per_1000_docs_usd": 0.799,
    }
    api = ModelSpec("openai", "openai", "gpt-6-luna", None, "K")
    assert ev.steady_load(api, 36.0, 10, 4) is None
