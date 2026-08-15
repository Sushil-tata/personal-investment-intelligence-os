from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
import json

import pandas as pd

from .challengers import DATA_PENDING_STRATEGIES, select_52w_high_allocations
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
from piios_backend.services.live_feeds import live_feeds


def _month_id(date_text: str) -> str:
    return date_text[:7]


def _parse_date(value: str) -> date:
    return datetime.fromisoformat(value).date()


def _month_end(target: date) -> date:
    return date(target.year, target.month, monthrange(target.year, target.month)[1])


def _to_naive_date_index(index: pd.Index) -> pd.DatetimeIndex:
    ts = pd.to_datetime(index)
    if getattr(ts, "tz", None) is not None:
        ts = ts.tz_convert(None)
    return ts.normalize()


class MarketPriceProvider:
    """Loads close series using the existing live-feeds yfinance retrieval path."""

    def __init__(self) -> None:
        self._frame_cache: dict[str, pd.DataFrame] = {}

    def _market_frame(self, ticker: str) -> pd.DataFrame:
        cached = self._frame_cache.get(ticker)
        if cached is not None:
            return cached

        snapshot = live_feeds.history(ticker, period="5y", interval="1d")
        if snapshot.frame is None or snapshot.frame.empty:
            self._frame_cache[ticker] = pd.DataFrame()
            return self._frame_cache[ticker]

        frame = snapshot.frame.sort_index().copy()
        frame.index = _to_naive_date_index(frame.index)
        frame = frame.groupby(frame.index).last().sort_index()
        self._frame_cache[ticker] = frame
        return frame

    def close_series(self, ticker: str) -> pd.Series:
        frame = self._market_frame(ticker)
        if frame.empty:
            return pd.Series(dtype=float)
        col = "Adj Close" if "Adj Close" in frame.columns else "Close"
        if col not in frame.columns:
            return pd.Series(dtype=float)

        series = frame[col].dropna().astype(float)
        if series.empty:
            return pd.Series(dtype=float)

        return series

    def volume_series(self, ticker: str) -> pd.Series:
        frame = self._market_frame(ticker)
        if frame.empty or "Volume" not in frame.columns:
            return pd.Series(dtype=float)
        return frame["Volume"].dropna().astype(float)


def _price_return(provider: MarketPriceProvider, ticker: str, start_date: date, end_date: date) -> float | None:
    if end_date < start_date:
        return None
    series = provider.close_series(ticker)
    if series.empty:
        return None

    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)

    starts = series[series.index >= start_ts]
    ends = series[series.index <= end_ts]
    if starts.empty or ends.empty:
        return None

    start_point = starts.index[0]
    end_point = ends.index[-1]
    if end_point < start_point:
        return None

    start_price = float(starts.iloc[0])
    end_price = float(ends.iloc[-1])
    if start_price <= 0:
        return None
    return (end_price / start_price) - 1.0


def _weighted_event_return(
    provider: MarketPriceProvider,
    allocations: dict[str, float],
    start_date: date,
    end_date: date,
) -> float:
    total = sum(max(0.0, float(value)) for value in allocations.values())
    if total <= 0:
        return 0.0

    weighted = 0.0
    for ticker, allocation in allocations.items():
        weight = max(0.0, float(allocation)) / total
        price_ret = _price_return(provider, ticker, start_date, end_date)
        # If price is unavailable, keep that leg in cash (0.0 return) for this month.
        weighted += weight * (0.0 if price_ret is None else price_ret)
    return weighted


def _cash_monthly_rate() -> float:
    # Cash proxy: 4.0% annualized short-term money-market style yield converted monthly.
    # This remains a documented near-real approximation until a live policy-rate feed is integrated.
    annual_rate = 0.04
    return (1.0 + annual_rate) ** (1.0 / 12.0) - 1.0


def _series_profile(
    provider: MarketPriceProvider,
    ticker: str,
    end_date: date,
    *,
    include_liquidity: bool,
) -> dict[str, object]:
    close = provider.close_series(ticker)
    if not close.empty:
        close = close[close.index <= pd.Timestamp(end_date)]
    profile: dict[str, object] = {
        "history_observations": int(len(close)),
        "history_start": None if close.empty else close.index[0].date().isoformat(),
        "history_end": None if close.empty else close.index[-1].date().isoformat(),
    }
    if not include_liquidity:
        return profile

    volume_loader = getattr(provider, "volume_series", None)
    volume = volume_loader(ticker) if callable(volume_loader) else pd.Series(dtype=float)
    if not volume.empty:
        volume = volume[volume.index <= pd.Timestamp(end_date)]
    aligned = pd.concat([close.rename("close"), volume.rename("volume")], axis=1).dropna()
    nonzero_volume = aligned[aligned["volume"] > 0.0]
    profile["volume_observations"] = int(len(nonzero_volume))
    profile["median_daily_volume"] = (
        None if nonzero_volume.empty else round(float(nonzero_volume["volume"].median()), 6)
    )
    profile["median_daily_traded_value_inr"] = (
        None
        if nonzero_volume.empty
        else round(float((nonzero_volume["close"] * nonzero_volume["volume"]).median()), 6)
    )
    return profile


def _nifty500_representation_diagnostics(
    provider: MarketPriceProvider,
    *,
    end_date: date,
    monthly_comparisons: dict[str, dict[str, object]],
) -> dict[str, object]:
    index_ticker = "^CRSLDX"
    proxy_ticker = "MONIFTY500.NS"
    index_close = provider.close_series(index_ticker)
    proxy_close = provider.close_series(proxy_ticker)
    joined = pd.concat(
        [index_close.rename("index"), proxy_close.rename("proxy")],
        axis=1,
    ).dropna()
    if not joined.empty:
        joined = joined[joined.index <= pd.Timestamp(end_date)]
    daily_returns = joined.pct_change().dropna()
    tracking_error = None
    if not daily_returns.empty:
        differences = daily_returns["proxy"] - daily_returns["index"]
        tracking_error = round(float(differences.std(ddof=0) * (252.0 ** 0.5) * 100.0), 6)

    return {
        "contestant_return_source": "benchmark_index",
        "benchmark_index": {
            "name": "NIFTY 500",
            "ticker": index_ticker,
            "instrument_type": "INDEX",
            "investable": False,
            "liquidity_applicable": False,
            **_series_profile(provider, index_ticker, end_date, include_liquidity=False),
        },
        "execution_proxy": {
            "name": "Motilal Oswal Nifty 500 ETF",
            "ticker": proxy_ticker,
            "instrument_type": "ETF",
            "investable": True,
            "liquidity_applicable": True,
            "included_as_competition_contestant": False,
            **_series_profile(provider, proxy_ticker, end_date, include_liquidity=True),
        },
        "overlap_observations": int(len(joined)),
        "annualized_daily_tracking_error_pct": tracking_error,
        "monthly_comparisons": monthly_comparisons,
        "interpretation": (
            "NIFTY500_V1 performance uses the non-investable index. The ETF is reported only as an execution proxy; "
            "its return, history, liquidity, and tracking difference are not collapsed into the index result."
        ),
    }


def run_competition(
    *,
    prospective_db_path: Path,
    output_root: Path,
    monthly_contribution: float = 5000.0,
    registry: StrategyRegistry | None = None,
    price_provider: MarketPriceProvider | None = None,
    today: date | None = None,
) -> CompetitionResult:
    registry = registry or default_registry()
    price_provider = price_provider or MarketPriceProvider()
    today = today or datetime.now(timezone.utc).date()

    decisions = load_core_decisions(prospective_db_path)
    events = decisions_to_events(decisions)
    if not events:
        raise ValueError("no prospective PIIOS_CORE events available in ledger")

    months = sorted({_month_id(event.as_of_date) for event in events})
    events_hash = event_ledger_hash(events)
    events_by_month: dict[str, list[object]] = defaultdict(list)
    for event in events:
        events_by_month[_month_id(event.as_of_date)].append(event)

    benchmark_ticker = {
        "NIFTY50_V1": "NIFTYBEES.NS",
        "NIFTY500_V1": "^CRSLDX",
        "SP500_V1": "SPY",
        "STI_V1": "ES3.SI",
    }
    cash_rate = _cash_monthly_rate()

    monthly_core_returns: dict[str, float] = {}
    monthly_benchmark_returns: dict[str, dict[str, float]] = defaultdict(dict)
    monthly_challenger_returns: dict[str, dict[str, float]] = defaultdict(dict)
    monthly_windows: dict[str, dict[str, str]] = {}
    monthly_core_components: dict[str, list[dict[str, object]]] = defaultdict(list)
    monthly_challenger_components: dict[str, dict[str, list[dict[str, object]]]] = defaultdict(dict)
    nifty500_monthly_comparisons: dict[str, dict[str, object]] = {}

    for month in months:
        batch = [item for item in events_by_month[month] if hasattr(item, "payload")]
        starts = [_parse_date(str(item.as_of_date)) for item in batch]
        start_date = min(starts)
        end_date = min(_month_end(start_date), today)
        monthly_windows[month] = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

        allocations: dict[str, float] = {}
        for item in batch:
            payload_allocations = item.payload.get("allocations", {}) if isinstance(item.payload, dict) else {}
            if not isinstance(payload_allocations, dict):
                continue
            for ticker, value in payload_allocations.items():
                try:
                    allocations[str(ticker)] = float(value)
                except Exception:
                    continue

        month_total = sum(max(0.0, float(value)) for value in allocations.values())
        for ticker, allocation in allocations.items():
            normalized_weight = (max(0.0, float(allocation)) / month_total) if month_total > 0 else 0.0
            ret = _price_return(price_provider, ticker, start_date, end_date)
            monthly_core_components[month].append(
                {
                    "ticker": ticker,
                    "proposed_allocation": round(float(allocation), 6),
                    "weight": round(normalized_weight, 8),
                    "price_return": None if ret is None else round(float(ret), 8),
                }
            )

        monthly_core_returns[month] = _weighted_event_return(price_provider, allocations, start_date, end_date)

        challenger_allocations, challenger_components = select_52w_high_allocations(
            price_provider,
            as_of_date=start_date,
        )
        monthly_challenger_components[month]["52W_HIGH_V1"] = challenger_components
        monthly_challenger_returns["52W_HIGH_V1"][month] = _weighted_event_return(
            price_provider,
            challenger_allocations,
            start_date,
            end_date,
        )

        for strategy_id, ticker in benchmark_ticker.items():
            bench_ret = _price_return(price_provider, ticker, start_date, end_date)
            monthly_benchmark_returns[strategy_id][month] = 0.0 if bench_ret is None else bench_ret
        nifty500_proxy_ret = _price_return(price_provider, "MONIFTY500.NS", start_date, end_date)
        nifty500_index_ret = _price_return(price_provider, "^CRSLDX", start_date, end_date)
        nifty500_monthly_comparisons[month] = {
            "benchmark_index_return": None if nifty500_index_ret is None else round(nifty500_index_ret, 8),
            "execution_proxy_return": None if nifty500_proxy_ret is None else round(nifty500_proxy_ret, 8),
            "tracking_difference_pct_points": (
                None
                if nifty500_index_ret is None or nifty500_proxy_ret is None
                else round((nifty500_proxy_ret - nifty500_index_ret) * 100.0, 6)
            ),
        }
        monthly_benchmark_returns["CASH_V1"][month] = cash_rate

    all_strategy_ids = [item.strategy_id for item in registry.all_latest()]

    tracks: dict[str, StrategyTrack] = {sid: StrategyTrack(strategy_id=sid) for sid in all_strategy_ids}
    monthly_returns_by_strategy: dict[str, list[float]] = defaultdict(list)
    nav_path_by_strategy: dict[str, list[float]] = defaultdict(list)
    snapshots: list[MonthlySnapshot] = []

    for month in months:
        for strategy_id in all_strategy_ids:
            contribution = equal_contribution_rule(strategy_id, monthly_contribution)
            if strategy_id == "PIIOS_CORE_V1":
                monthly_return = monthly_core_returns.get(month, 0.0)
            elif strategy_id == "52W_HIGH_V1":
                monthly_return = monthly_challenger_returns.get(strategy_id, {}).get(month, 0.0)
            else:
                monthly_return = monthly_benchmark_returns.get(strategy_id, {}).get(month, 0.0)

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
                "data_pending_strategies": DATA_PENDING_STRATEGIES,
                "sizing_note": "52W_HIGH_V1 uses equal-weight sizing because liquidity/volatility inputs are not available in the current MarketPriceProvider interface; liquidity proxy in this version is minimum recent trading-day observations only.",
                "ledger_timestamp_semantics": "APPLICATION_RETRIEVAL_TIMESTAMP",
                "portfolio_execution_model": "MONTHLY_FULL_REBALANCE_TO_EVENT_ALLOCATIONS",
                "current_rank_1": current_rank_1,
                "investment_conclusion": investment_conclusion,
                "contestant_data_sources": {
                    "PIIOS_CORE_V1": "real weighted price return of held tickers via live_feeds.history(yfinance); source ledger strategy_id remains PIIOS_CORE",
                    "52W_HIGH_V1": "real price return of monthly near-52-week-high basket selected from India universe via live_feeds.history(yfinance)",
                    "NIFTY50_V1": "real proxy price return via NIFTYBEES.NS from live_feeds.history(yfinance)",
                    "NIFTY500_V1": "real NIFTY 500 benchmark index return via ^CRSLDX from live_feeds.history(yfinance); MONIFTY500.NS execution proxy reported separately",
                    "SP500_V1": "real proxy price return via SPY from live_feeds.history(yfinance)",
                    "STI_V1": "real proxy price return via ES3.SI from live_feeds.history(yfinance)",
                    "CASH_V1": "near-real cash proxy from documented annualized 4.0% converted to monthly rate",
                },
                "monthly_windows": monthly_windows,
                "piios_core_monthly_components": monthly_core_components,
                "challenger_monthly_components": monthly_challenger_components,
                "nifty500_representation": _nifty500_representation_diagnostics(
                    price_provider,
                    end_date=max(_parse_date(window["end_date"]) for window in monthly_windows.values()),
                    monthly_comparisons=nifty500_monthly_comparisons,
                ),
                "leaderboard_top": asdict(leaderboard[0]) if leaderboard else None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return result
