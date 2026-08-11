from __future__ import annotations

from collections.abc import Sequence
import math
import random
from statistics import mean, median, pstdev

from .models import BootstrapCI


def safe_mean(values: Sequence[float | None]) -> float | None:
    usable = [float(v) for v in values if isinstance(v, (int, float))]
    if not usable:
        return None
    return float(mean(usable))


def safe_median(values: Sequence[float | None]) -> float | None:
    usable = [float(v) for v in values if isinstance(v, (int, float))]
    if not usable:
        return None
    return float(median(usable))


def safe_std(values: Sequence[float | None]) -> float | None:
    usable = [float(v) for v in values if isinstance(v, (int, float))]
    if len(usable) < 2:
        return None
    return float(pstdev(usable))


def hit_rate(values: Sequence[float | None], threshold: float = 0.0) -> float | None:
    usable = [float(v) for v in values if isinstance(v, (int, float))]
    if not usable:
        return None
    hits = sum(1 for v in usable if v > threshold)
    return float(hits / len(usable))


def bootstrap_ci_90(
    values: Sequence[float | None],
    *,
    seed: int,
    iterations: int = 2000,
    block_size: int = 3,
) -> BootstrapCI | None:
    usable = [float(v) for v in values if isinstance(v, (int, float))]
    n = len(usable)
    if n < 3:
        return None

    rng = random.Random(seed)
    samples: list[float] = []
    block_size = max(1, min(block_size, n))

    for _ in range(iterations):
        draw: list[float] = []
        while len(draw) < n:
            start = rng.randrange(0, n)
            block = [usable[(start + offset) % n] for offset in range(block_size)]
            draw.extend(block)
        draw = draw[:n]
        samples.append(float(mean(draw)))

    samples.sort()
    lower_idx = max(0, math.floor(0.05 * len(samples)) - 1)
    upper_idx = min(len(samples) - 1, math.ceil(0.95 * len(samples)) - 1)
    return BootstrapCI(lower=samples[lower_idx], upper=samples[upper_idx])


def approx_effective_sample_size(month_count: int, horizon_days: int) -> int:
    overlap_factor = max(1.0, horizon_days / 20.0)
    return max(1, int(round(month_count / overlap_factor)))
