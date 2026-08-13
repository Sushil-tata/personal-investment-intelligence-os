from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any

# Prospective-fundamental timestamp semantics: application retrieval/freeze time only.
APPLICATION_RETRIEVAL_TIMESTAMP = "APPLICATION_RETRIEVAL_TIMESTAMP"


@dataclass(frozen=True)
class StrategyDefinition:
    strategy_id: str
    version: int
    engine_version: str
    description: str
    kind: str  # CORE or BENCHMARK


@dataclass(frozen=True)
class CoreDecision:
    decision_id: str
    strategy_id: str
    as_of_date: str
    run_timestamp: str
    ticker: str
    action: str
    proposed_allocation: float
    market_source_retrieval_timestamp: str | None
    fundamental_source_retrieval_timestamp: str | None
    fundamental_timestamp_semantics: str = APPLICATION_RETRIEVAL_TIMESTAMP


@dataclass(frozen=True)
class StrategyEvent:
    event_id: str
    strategy_id: str
    as_of_date: str
    event_type: str
    payload: dict[str, Any]
    event_hash: str


@dataclass(frozen=True)
class MonthlySnapshot:
    strategy_id: str
    as_of_date: str
    nav_before_return: float
    nav_after_return: float
    monthly_contribution: float
    monthly_return: float
    cumulative_contributed: float


@dataclass(frozen=True)
class LeaderboardRow:
    strategy_id: str
    ending_nav: float
    cumulative_contributed: float
    net_profit: float
    total_return_pct: float
    annualized_return_pct: float
    volatility_pct: float
    max_drawdown_pct: float
    months_tracked: int


@dataclass(frozen=True)
class CompetitionResult:
    registry_version_hash: str
    start_month: str
    end_month: str
    monthly_contribution: float
    snapshots: list[MonthlySnapshot] = field(default_factory=list)
    leaderboard: list[LeaderboardRow] = field(default_factory=list)


def canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
