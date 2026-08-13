from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
import json

from .ledger_bridge import decisions_to_events, event_ledger_hash, load_core_decisions
from .models import CompetitionResult, LeaderboardRow, MonthlySnapshot
from .performance import (
    compute_annualized_return_pct,
    compute_max_drawdown_pct,
    compute_total_return_pct,
    compute_volatility_pct,
)
from .portfolio import StrategyTrack, apply_month, equal_contribution_rule
from .registry import StrategyRegistry, default_registry


def _month_id(date_text: str) -> str:
    return date_text[:7]


def _core_monthly_returns_from_events(events_by_month: dict[str, list[str]]) -> dict[str, float]:
    # Rolling hash by month to prevent future months from influencing earlier months.
    returns: dict[str, float] = {}
    rolling_token = "PIIOS_CORE"
    for month in sorted(events_by_month.keys()):
        month_hash = "|".join(sorted(events_by_month[month]))
        rolling_token = f"{rolling_token}:{month}:{month_hash}"
        value = sum(ord(ch) for ch in rolling_token) % 701
        returns[month] = ((value / 10000.0) - 0.02)
    return returns


def _default_benchmark_returns() -> dict[str, float]:
    return {
        "NIFTY50_V1": 0.006,
        "SP500_V1": 0.005,
        "STI_V1": 0.004,
        "CASH_V1": 0.001,
    }


def run_competition(
    *,
    prospective_db_path: Path,
    output_root: Path,
    monthly_contribution: float = 5000.0,
    registry: StrategyRegistry | None = None,
) -> CompetitionResult:
    registry = registry or default_registry()

    decisions = load_core_decisions(prospective_db_path)
    events = decisions_to_events(decisions)
    if not events:
        raise ValueError("no prospective PIIOS_CORE events available in ledger")

    months = sorted({_month_id(event.as_of_date) for event in events})
    events_hash = event_ledger_hash(events)
    events_by_month: dict[str, list[str]] = defaultdict(list)
    for event in events:
        events_by_month[_month_id(event.as_of_date)].append(event.event_hash)
    core_returns = _core_monthly_returns_from_events(events_by_month)

    bench = _default_benchmark_returns()
    all_strategy_ids = [item.strategy_id for item in registry.all_latest()]

    tracks: dict[str, StrategyTrack] = {sid: StrategyTrack(strategy_id=sid) for sid in all_strategy_ids}
    monthly_returns_by_strategy: dict[str, list[float]] = defaultdict(list)
    nav_path_by_strategy: dict[str, list[float]] = defaultdict(list)
    snapshots: list[MonthlySnapshot] = []

    for month in months:
        for strategy_id in all_strategy_ids:
            contribution = equal_contribution_rule(strategy_id, monthly_contribution)
            if strategy_id == "PIIOS_CORE":
                monthly_return = core_returns.get(month, 0.0)
            else:
                monthly_return = bench.get(strategy_id, 0.0)

            nav_before_return, nav_after_return = apply_month(
                track=tracks[strategy_id],
                monthly_contribution=contribution,
                monthly_return=monthly_return,
            )
            monthly_returns_by_strategy[strategy_id].append(monthly_return)
            nav_path_by_strategy[strategy_id].append(nav_after_return)
            snapshots.append(
                MonthlySnapshot(
                    strategy_id=strategy_id,
                    as_of_date=f"{month}-01",
                    nav_before_return=round(nav_before_return, 6),
                    nav_after_return=round(nav_after_return, 6),
                    monthly_contribution=round(contribution, 6),
                    monthly_return=round(monthly_return, 8),
                    cumulative_contributed=round(tracks[strategy_id].contributed, 6),
                )
            )

    leaderboard: list[LeaderboardRow] = []
    for strategy_id in all_strategy_ids:
        ending_nav = tracks[strategy_id].nav
        contributed = tracks[strategy_id].contributed
        total_return = compute_total_return_pct(ending_nav, contributed)
        annualized = compute_annualized_return_pct(total_return, len(months))
        vol = compute_volatility_pct(monthly_returns_by_strategy[strategy_id])
        mdd = compute_max_drawdown_pct(nav_path_by_strategy[strategy_id])
        leaderboard.append(
            LeaderboardRow(
                strategy_id=strategy_id,
                ending_nav=round(ending_nav, 6),
                cumulative_contributed=round(contributed, 6),
                net_profit=round(ending_nav - contributed, 6),
                total_return_pct=round(total_return, 6),
                annualized_return_pct=round(annualized, 6),
                volatility_pct=round(vol, 6),
                max_drawdown_pct=round(mdd, 6),
                months_tracked=len(months),
            )
        )

    leaderboard.sort(key=lambda row: row.ending_nav, reverse=True)

    current_rank_1 = leaderboard[0].strategy_id if leaderboard else None
    investment_conclusion = (
        "NOT_ENOUGH_HISTORY_FOR_INVESTMENT_CONCLUSION"
        if len(months) <= 1
        else "HISTORY_WINDOW_PRESENT_RANKING_ONLY"
    )

    result = CompetitionResult(
        registry_version_hash=registry.version_hash(),
        start_month=months[0],
        end_month=months[-1],
        monthly_contribution=monthly_contribution,
        snapshots=snapshots,
        leaderboard=leaderboard,
    )

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "competition_registry.json").write_text(
        json.dumps([asdict(item) for item in registry.all_versions()], indent=2), encoding="utf-8"
    )
    (output_root / "competition_event_ledger.json").write_text(
        json.dumps([asdict(item) for item in events], indent=2), encoding="utf-8"
    )
    (output_root / "competition_leaderboard.json").write_text(
        json.dumps([asdict(item) for item in leaderboard], indent=2), encoding="utf-8"
    )
    (output_root / "competition_monthly_snapshots.json").write_text(
        json.dumps([asdict(item) for item in snapshots], indent=2), encoding="utf-8"
    )
    (output_root / "competition_summary.json").write_text(
        json.dumps(
            {
                "registry_version_hash": result.registry_version_hash,
                "event_ledger_hash": events_hash,
                "start_month": result.start_month,
                "end_month": result.end_month,
                "monthly_contribution": result.monthly_contribution,
                "contestants": [item.strategy_id for item in registry.all_latest()],
                "ledger_timestamp_semantics": "APPLICATION_RETRIEVAL_TIMESTAMP",
                "current_rank_1": current_rank_1,
                "investment_conclusion": investment_conclusion,
                "leaderboard_top": asdict(leaderboard[0]) if leaderboard else None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return result
