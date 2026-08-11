from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

EligibilityState = Literal[
    "ELIGIBLE",
    "INSUFFICIENT_HISTORY",
    "ILLIQUID",
    "MISSING_PRICE",
    "INVALID_PRICE_SERIES",
]


@dataclass(frozen=True)
class FactorSnapshot:
    ticker: str
    as_of: date
    eligibility: EligibilityState
    reason: str | None
    return_3m_pct: float | None = None
    return_6m_pct: float | None = None
    return_12m_pct: float | None = None
    realized_volatility: float | None = None
    max_drawdown_pct: float | None = None
    distance_from_52w_high_pct: float | None = None
    liquidity_score: float | None = None
    liquidity_status: str = "UNAVAILABLE"
    median_daily_value: float | None = None
    momentum_score: float | None = None
    risk_score: float | None = None
    price_risk_signal_score: float | None = None


@dataclass(frozen=True)
class PortfolioMembership:
    ticker: str
    rank: int
    decile: int
    top10: bool
    top20: bool
    top_decile: bool
    bottom_decile: bool


@dataclass(frozen=True)
class ForwardReturnPoint:
    ticker: str
    as_of: date
    horizon_days: int
    gross_return: float | None
    net_return: float | None


@dataclass
class MonthlyResult:
    as_of: date
    eligible_count: int
    ineligible_count: int
    eligibility_counts: dict[str, int]
    rank_ic_by_horizon: dict[int, float | None]
    memberships: list[PortfolioMembership] = field(default_factory=list)
    factor_rows: list[FactorSnapshot] = field(default_factory=list)
    forward_rows: list[ForwardReturnPoint] = field(default_factory=list)


@dataclass
class BootstrapCI:
    lower: float
    upper: float


@dataclass
class HorizonSummary:
    horizon_days: int
    mean_ic: float | None
    median_ic: float | None
    ic_std: float | None
    ic_positive_month_pct: float | None
    ic_count: int
    ic_ci_90: BootstrapCI | None
    top_decile_return: float | None
    bottom_decile_return: float | None
    top_minus_bottom_spread: float | None
    spread_ci_90: BootstrapCI | None
    top20_excess_return: float | None
    top20_net_excess_return: float | None
    top20_excess_ci_90: BootstrapCI | None


@dataclass
class PortfolioStats:
    mean_return: float | None
    median_return: float | None
    benchmark_excess_return: float | None
    hit_rate_vs_universe_median: float | None
    volatility: float | None
    worst_cohort_return: float | None
    best_cohort_return: float | None
