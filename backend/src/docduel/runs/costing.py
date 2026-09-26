"""Cost per request (Plan Section 11). Prices come from config/pricing.yaml only."""

from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from docduel.settings import get_settings

MILLION = Decimal(1_000_000)


def load_pricing(path: Path | None = None) -> dict[str, Any]:
    path = path or get_settings().config_dir / "pricing.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def openai_cost(
    prices: dict[str, Any], input_tokens: int, cached_input_tokens: int, output_tokens: int
) -> Decimal:
    """Uncached input + cached input (cheaper rate) + output. Reasoning tokens are output."""
    uncached = input_tokens - cached_input_tokens
    return (
        uncached * _d(prices["input_per_1m"])
        + cached_input_tokens * _d(prices["cached_input_per_1m"])
        + output_tokens * _d(prices["output_per_1m"])
    ) / MILLION


def gpu_cost(gpu_per_hour: float, busy_seconds: float) -> Decimal:
    """Marginal cost of a warm GPU for this request. Excludes idle time and cold starts."""
    return _d(gpu_per_hour) * _d(busy_seconds) / Decimal(3600)


def per_1000_docs(cost_per_doc: Decimal) -> Decimal:
    return cost_per_doc * 1000
