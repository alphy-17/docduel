"""95% bootstrap confidence intervals (Plan Section 10.3).

Resample documents with replacement 1,000 times (fixed seed), recompute the metric on each
resample, and take the 2.5th and 97.5th percentiles.
"""

from collections.abc import Callable, Sequence

import numpy as np

SEED = 2026
RESAMPLES = 1000


def bootstrap_ci[T](
    docs: Sequence[T],
    metric: Callable[[list[T]], float],
    resamples: int = RESAMPLES,
    seed: int = SEED,
) -> tuple[float, float]:
    if not docs:
        return 0.0, 0.0
    rng = np.random.default_rng(seed)
    n = len(docs)
    values = [metric([docs[i] for i in rng.integers(0, n, size=n)]) for _ in range(resamples)]
    low, high = np.percentile(values, [2.5, 97.5])
    return float(low), float(high)


def fmt_ci(value: float, ci: tuple[float, float]) -> str:
    """'91.2% (87.0-94.8)'."""
    return f"{value * 100:.1f}% ({ci[0] * 100:.1f}-{ci[1] * 100:.1f})"
