"""Read config/models.yaml into typed model specs. Model IDs live only in that file."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from docduel.settings import get_settings


@dataclass(frozen=True)
class ModelSpec:
    key: str
    provider: str  # "openai" or "vllm"
    model_id: str | None
    base_url_env: str | None
    api_key_env: str | None
    reasoning_effort: str | None = None  # OpenAI only
    extra_body: dict[str, Any] = field(default_factory=dict)  # vLLM-only options
    status: str = "active"
    gpu: str | None = None  # vLLM only: Modal GPU type, for cost

    @property
    def is_placeholder(self) -> bool:
        return self.status == "placeholder"


def _load(path: Path | None = None) -> dict[str, Any]:
    path = path or get_settings().config_dir / "models.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_models(path: Path | None = None) -> dict[str, ModelSpec]:
    data = _load(path)
    return {
        key: ModelSpec(
            key=key,
            provider=cfg["provider"],
            model_id=cfg.get("model_id"),
            base_url_env=cfg.get("base_url_env"),
            api_key_env=cfg.get("api_key_env"),
            reasoning_effort=cfg.get("reasoning_effort"),
            extra_body=cfg.get("extra_body") or {},
            status=cfg.get("status", "active"),
            gpu=cfg.get("gpu"),
        )
        for key, cfg in data["models"].items()
    }


def duel_keys(path: Path | None = None) -> tuple[str, str]:
    """(left, right) model keys for the Duel page."""
    duel = _load(path)["duel"]
    return duel["left"], duel["right"]
