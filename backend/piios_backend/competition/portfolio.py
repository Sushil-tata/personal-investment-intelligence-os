from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StrategyTrack:
    strategy_id: str
    contributed: float = 0.0
    nav: float = 0.0


def apply_month(
    *,
    track: StrategyTrack,
    monthly_contribution: float,
    monthly_return: float,
) -> tuple[float, float]:
    """Apply contribution first, then monthly return to keep all contestants on identical rules."""
    track.contributed += monthly_contribution
    nav_before_return = track.nav + monthly_contribution
    track.nav = nav_before_return * (1.0 + monthly_return)
    return nav_before_return, track.nav


def equal_contribution_rule(_strategy_id: str, monthly_contribution: float) -> float:
    return monthly_contribution
