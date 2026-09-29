"""GET /api/benchmark (Plan task 5.6): the latest test-set reports for every model.

Every number comes from reports/eval_<model>_test-v1_<prompt>.json, written by
`python -m docduel.eval` (rule R5). Nothing here is typed by hand.
"""

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from docduel.datasets.build import DATASET_VERSION
from docduel.models.registry import load_models
from docduel.runs.prompting import VERSION
from docduel.scoring.extract import relative_score
from docduel.settings import REPO_DIR

router = APIRouter(prefix="/api")

# Our model's keys, best first; the Benchmark shows the first one that has a report.
OURS = ("small-ft-r2", "small-ft-r1", "small-base")
BASELINE = "openai"


def report_dir() -> Path:
    return REPO_DIR / "reports"


ROUNDS = ("small-base", "small-ft-r1", "small-ft-r2")  # base, round 1, round 2 (Plan 8.9)
ROUND_METRICS = ("field_accuracy", "line_item_f1", "perfect_document_rate")


def _read(model: str, prompt: str, split: str = DATASET_VERSION) -> dict[str, Any] | None:
    path = report_dir() / f"eval_{model}_{split}_{prompt}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_view(report: dict[str, Any]) -> dict[str, Any]:
    scores = report["scores"]
    by_id = {d["id"]: d for d in scores["per_doc"]}
    return {
        "created_at": report["created_at"],
        "docs": report["docs_scored"],
        "headline": scores["headline"],
        "per_field": scores["per_field"],
        "by_source": scores["by_source"],
        "worst_failures": [by_id[i] for i in scores["worst_failures"] if i in by_id],
        "speed_cost": report["speed_cost"],
        "notes": scores["scoring_notes"],
    }


def _categorise_view(report: dict[str, Any]) -> dict[str, Any]:
    scores = report["scores"]
    return {
        "created_at": report["created_at"],
        "docs": report["docs_scored"],
        "rows": sum(d["rows"] for d in scores["per_doc"]),
        "headline": scores["headline"],
        "confusion_matrix": scores["confusion_matrix"],
        "speed_cost": report["speed_cost"],
    }


@router.get("/benchmark")
def benchmark() -> dict[str, Any]:
    specs = load_models()
    models: dict[str, Any] = {}
    for key in (*OURS, BASELINE):
        spec = specs.get(key)
        ex = _read(key, f"extract_{VERSION}")
        cat = _read(key, f"categorise_{VERSION}")
        models[key] = {
            "model_id": spec.model_id if spec else None,
            "reasoning_effort": spec.reasoning_effort if spec else None,
            "status": spec.status if spec else "unknown",
            "extract": _extract_view(ex) if ex else None,
            "categorise": _categorise_view(cat) if cat else None,
        }

    # Our headline model is chosen on dev, never on the test set: best dev field accuracy.
    def dev_score(key: str) -> float:
        dev = _read(key, f"extract_{VERSION}", "dev")
        return dev["scores"]["headline"]["field_accuracy"]["value"] if dev else -1.0

    candidates = [k for k in OURS if models[k]["extract"]]
    ours = max(candidates, key=dev_score) if candidates else None  # ties keep OURS order
    relative = None
    if ours and models[BASELINE]["extract"]:
        relative = relative_score(
            models[ours]["extract"]["headline"]["field_accuracy"]["value"],
            models[BASELINE]["extract"]["headline"]["field_accuracy"]["value"],
        )
    return {
        "dataset_version": DATASET_VERSION,
        "prompt_version": VERSION,
        "ours": ours,
        "baseline": BASELINE,
        "relative_score": round(relative, 1) if relative is not None else None,
        "models": models,
        "rounds": _rounds(),
    }


def _metrics(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if report is None:
        return None
    head = report["scores"]["headline"]
    return {"docs": report["docs_scored"], **{m: head.get(m) for m in ROUND_METRICS}}


def _rounds() -> dict[str, Any]:
    """Base -> round 1 -> round 2 on the frozen test set and the hard-case holdout (Plan 8.9)."""
    prompt = f"extract_{VERSION}"
    return {
        "models": [
            {
                "key": key,
                "test": _metrics(_read(key, prompt)),
                "holdout": _metrics(_read(key, prompt, "hard-holdout")),
            }
            for key in ROUNDS
        ],
        "baseline_test": _metrics(_read(BASELINE, prompt)),
    }
