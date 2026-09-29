"""GET /api/benchmark reads the eval reports (Plan 5.6, rule R5)."""

import json

from fastapi.testclient import TestClient

from docduel.main import app
from docduel.routes import benchmark

HEADLINE = {"field_accuracy": {"value": 0.9, "ci95": [0.8, 0.95], "display": "90.0% (80.0-95.0)"}}


def _report(**scores):
    return {
        "created_at": "2026-09-27T00:00:00+00:00",
        "docs_scored": 2,
        "speed_cost": {"cost_per_1000_docs_usd": 0.2},
        "outputs": [{"id": "a"}],
        "scores": scores,
    }


def test_empty_when_no_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "report_dir", lambda: tmp_path)
    body = TestClient(app).get("/api/benchmark").json()
    assert body["dataset_version"] == "test-v1"
    assert body["ours"] is None and body["relative_score"] is None
    assert body["models"]["openai"]["extract"] is None
    assert body["models"]["small-ft-r2"]["status"] == "active"


def test_reads_reports_and_relative_score(tmp_path, monkeypatch):
    per_doc = [{"id": "a", "perfect": True}, {"id": "b", "perfect": False}]
    ex = _report(
        headline=HEADLINE,
        per_field={},
        by_source={},
        worst_failures=["b"],
        per_doc=per_doc,
        scoring_notes=["n"],
    )
    (tmp_path / "eval_openai_test-v1_extract_v1.json").write_text(json.dumps(ex))
    ours = json.loads(json.dumps(ex))
    ours["scores"]["headline"]["field_accuracy"]["value"] = 0.72
    (tmp_path / "eval_small-ft-r1_test-v1_extract_v1.json").write_text(json.dumps(ours))
    cat = _report(
        headline={},
        confusion_matrix={"Dining": {"Dining": 3}},
        per_doc=[{"rows": 20}, {"rows": 20}],
    )
    (tmp_path / "eval_openai_test-v1_categorise_v1.json").write_text(json.dumps(cat))
    monkeypatch.setattr(benchmark, "report_dir", lambda: tmp_path)

    body = TestClient(app).get("/api/benchmark").json()
    openai = body["models"]["openai"]
    assert openai["extract"]["headline"] == HEADLINE
    assert [d["id"] for d in openai["extract"]["worst_failures"]] == ["b"]
    assert "outputs" not in openai["extract"]
    assert openai["categorise"]["rows"] == 40
    assert body["ours"] == "small-ft-r1" and body["relative_score"] == 80.0
    rounds = {r["key"]: r for r in body["rounds"]["models"]}
    assert rounds["small-ft-r1"]["test"]["field_accuracy"]["value"] == 0.72
    assert rounds["small-base"]["test"] is None and rounds["small-ft-r1"]["holdout"] is None
    assert body["rounds"]["baseline_test"]["docs"] == 2


def test_ours_is_chosen_on_dev_not_test(tmp_path, monkeypatch):
    def write(name: str, value: float) -> None:
        rep = _report(
            headline={"field_accuracy": {"value": value}},
            per_field={},
            by_source={},
            worst_failures=[],
            per_doc=[],
            scoring_notes=[],
        )
        (tmp_path / name).write_text(json.dumps(rep))

    write("eval_small-ft-r1_test-v1_extract_v1.json", 0.96)
    write("eval_small-ft-r2_test-v1_extract_v1.json", 0.95)
    write("eval_small-ft-r1_dev_extract_v1.json", 0.979)
    write("eval_small-ft-r2_dev_extract_v1.json", 0.970)
    write("eval_small-ft-r2_hard-holdout_extract_v1.json", 0.856)
    monkeypatch.setattr(benchmark, "report_dir", lambda: tmp_path)
    body = TestClient(app).get("/api/benchmark").json()
    assert body["ours"] == "small-ft-r1"
    r2 = next(r for r in body["rounds"]["models"] if r["key"] == "small-ft-r2")
    assert r2["holdout"]["field_accuracy"]["value"] == 0.856
