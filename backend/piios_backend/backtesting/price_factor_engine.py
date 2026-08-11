from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from piios_backend.backtesting.models import (
    FactorSnapshot,
    ForwardReturnPoint,
    PortfolioMembership,
)
from piios_backend.services.recommendation_mvp import RecommendationMVPService


@dataclass(frozen=True)
class EngineConfig:
    lookback_days: int = 252
    momentum_weight: float = 0.20 / (0.20 + 0.15)
    risk_weight: float = 0.15 / (0.20 + 0.15)
    min_history_points: int = 253


class PriceRiskFactorEngine:
    def __init__(self, config: EngineConfig | None = None) -> None:
        self.config = config or EngineConfig()
        self._svc = RecommendationMVPService()

    def _window_return(self, series: pd.Series, lookback: int) -> float | None:
        obs = len(series)
        if obs < 2:
            return None
        idx = max(0, obs - 1 - min(lookback, obs - 1))
        start = float(series.iloc[idx])
        end = float(series.iloc[-1])
        if start <= 0:
            return None
        return ((end / start) - 1.0) * 100.0

    def _factor_from_slice(self, ticker: str, as_of: date, frame: pd.DataFrame) -> FactorSnapshot:
        if frame.empty:
            return FactorSnapshot(ticker=ticker, as_of=as_of, eligibility="MISSING_PRICE", reason="empty_history")

        frame = frame.sort_index()
        if pd.Timestamp(as_of) not in frame.index:
            return FactorSnapshot(ticker=ticker, as_of=as_of, eligibility="MISSING_PRICE", reason="no_close_on_ranking_date")

        hist = frame.loc[: pd.Timestamp(as_of)]
        if len(hist) < self.config.min_history_points:
            return FactorSnapshot(
                ticker=ticker,
                as_of=as_of,
                eligibility="INSUFFICIENT_HISTORY",
                reason=f"need_{self.config.min_history_points}_obs_have_{len(hist)}",
            )

        price_col = "Adj Close" if "Adj Close" in hist.columns else "Close"
        if price_col not in hist.columns:
            return FactorSnapshot(ticker=ticker, as_of=as_of, eligibility="MISSING_PRICE", reason="no_price_column")

        price = hist[price_col].dropna().tail(self.config.min_history_points)
        if len(price) < self.config.min_history_points:
            return FactorSnapshot(
                ticker=ticker,
                as_of=as_of,
                eligibility="INSUFFICIENT_HISTORY",
                reason="insufficient_non_null_prices",
            )

        if (price <= 0).any():
            return FactorSnapshot(ticker=ticker, as_of=as_of, eligibility="INVALID_PRICE_SERIES", reason="non_positive_price")

        returns = price.pct_change().dropna()
        if returns.empty:
            return FactorSnapshot(ticker=ticker, as_of=as_of, eligibility="INVALID_PRICE_SERIES", reason="no_returns")

        vol = float(returns.std(ddof=0) * (252.0 ** 0.5))
        running_max = price.cummax()
        drawdowns = (price / running_max) - 1.0
        max_drawdown_pct = float(drawdowns.min() * 100.0)
        high_52w = float(price.max())
        dist_52w = ((float(price.iloc[-1]) / high_52w) - 1.0) * 100.0 if high_52w > 0 else None

        volume_series = None
        if "Volume" in hist.columns:
            volume_series = hist["Volume"].reindex(price.index).fillna(0.0)
        liquidity = self._svc._liquidity_profile(price, volume_series, "India")

        if str(liquidity.get("liquidity_status") or "UNAVAILABLE") == "FAIL":
            return FactorSnapshot(
                ticker=ticker,
                as_of=as_of,
                eligibility="ILLIQUID",
                reason="liquidity_fail",
                liquidity_status="FAIL",
                liquidity_score=self._svc._safe_float(liquidity.get("liquidity_score")),
                median_daily_value=self._svc._safe_float(liquidity.get("median_daily_value")),
            )

        metrics: dict[str, float | None] = {
            "return_3m_pct": self._window_return(price, 63),
            "return_6m_pct": self._window_return(price, 126),
            "return_12m_pct": self._window_return(price, 252),
            "realized_volatility": vol,
            "max_drawdown_pct": max_drawdown_pct,
            "distance_from_52w_high_pct": dist_52w,
        }

        # Use the same validation policy behavior as production metric handling.
        validated: dict[str, float | None] = {}
        for metric_name, value in metrics.items():
            validated_value, _ = self._svc._validated_metric(metric_name, value)
            validated[metric_name] = validated_value

        if any(validated[key] is None for key in metrics):
            return FactorSnapshot(
                ticker=ticker,
                as_of=as_of,
                eligibility="INVALID_PRICE_SERIES",
                reason="metric_failed_validation",
            )

        return FactorSnapshot(
            ticker=ticker,
            as_of=as_of,
            eligibility="ELIGIBLE",
            reason=None,
            return_3m_pct=validated["return_3m_pct"],
            return_6m_pct=validated["return_6m_pct"],
            return_12m_pct=validated["return_12m_pct"],
            realized_volatility=validated["realized_volatility"],
            max_drawdown_pct=validated["max_drawdown_pct"],
            distance_from_52w_high_pct=validated["distance_from_52w_high_pct"],
            liquidity_score=self._svc._safe_float(liquidity.get("liquidity_score")),
            liquidity_status=str(liquidity.get("liquidity_status") or "UNAVAILABLE"),
            median_daily_value=self._svc._safe_float(liquidity.get("median_daily_value")),
        )

    def factor_snapshots_at(
        self,
        as_of: date,
        ticker_frames: dict[str, pd.DataFrame],
    ) -> list[FactorSnapshot]:
        return [self._factor_from_slice(ticker, as_of, frame) for ticker, frame in ticker_frames.items()]

    def score_cross_section(self, rows: list[FactorSnapshot]) -> list[FactorSnapshot]:
        eligible = [r for r in rows if r.eligibility == "ELIGIBLE"]
        if not eligible:
            return rows

        def _metric_score(metric: str, lower_is_better: bool) -> dict[str, float]:
            values = [float(getattr(r, metric)) for r in eligible if isinstance(getattr(r, metric), (int, float))]
            out: dict[str, float] = {}
            for row in eligible:
                value = getattr(row, metric)
                if not isinstance(value, (int, float)):
                    continue
                pct = self._svc._percentile_rank(float(value), values)
                out[row.ticker] = round(100.0 - pct, 2) if lower_is_better else round(pct, 2)
            return out

        m3 = _metric_score("return_3m_pct", False)
        m6 = _metric_score("return_6m_pct", False)
        m12 = _metric_score("return_12m_pct", False)
        d52 = _metric_score("distance_from_52w_high_pct", False)
        vol = _metric_score("realized_volatility", True)
        dd = _metric_score("max_drawdown_pct", False)

        scored: list[FactorSnapshot] = []
        for row in rows:
            if row.eligibility != "ELIGIBLE":
                scored.append(row)
                continue
            momentum_parts = [m3.get(row.ticker), m6.get(row.ticker), m12.get(row.ticker), d52.get(row.ticker)]
            risk_parts = [vol.get(row.ticker), dd.get(row.ticker)]
            momentum_score = self._svc._mean_or_none(momentum_parts)
            risk_score = self._svc._mean_or_none(risk_parts)
            signal_score = None
            if momentum_score is not None and risk_score is not None:
                signal_score = round(
                    (momentum_score * self.config.momentum_weight) + (risk_score * self.config.risk_weight),
                    4,
                )
            scored.append(
                FactorSnapshot(
                    ticker=row.ticker,
                    as_of=row.as_of,
                    eligibility=row.eligibility,
                    reason=row.reason,
                    return_3m_pct=row.return_3m_pct,
                    return_6m_pct=row.return_6m_pct,
                    return_12m_pct=row.return_12m_pct,
                    realized_volatility=row.realized_volatility,
                    max_drawdown_pct=row.max_drawdown_pct,
                    distance_from_52w_high_pct=row.distance_from_52w_high_pct,
                    liquidity_score=row.liquidity_score,
                    liquidity_status=row.liquidity_status,
                    median_daily_value=row.median_daily_value,
                    momentum_score=momentum_score,
                    risk_score=risk_score,
                    price_risk_signal_score=signal_score,
                )
            )
        return scored

    def build_memberships(self, scored_rows: list[FactorSnapshot]) -> list[PortfolioMembership]:
        eligible = [r for r in scored_rows if r.eligibility == "ELIGIBLE" and isinstance(r.price_risk_signal_score, (int, float))]
        eligible.sort(key=lambda r: (float(r.price_risk_signal_score), r.ticker), reverse=True)
        n = len(eligible)
        if n == 0:
            return []

        out: list[PortfolioMembership] = []
        for idx, row in enumerate(eligible, start=1):
            # Decile 10 is top-ranked, Decile 1 is bottom-ranked.
            decile = max(1, min(10, 10 - int(((idx - 1) * 10) / n)))
            out.append(
                PortfolioMembership(
                    ticker=row.ticker,
                    rank=idx,
                    decile=decile,
                    top10=idx <= 10,
                    top20=idx <= 20,
                    top_decile=decile == 10,
                    bottom_decile=decile == 1,
                )
            )
        return out

    def forward_return(
        self,
        frame: pd.DataFrame,
        as_of: date,
        horizon_days: int,
        tx_cost_rate: float,
    ) -> ForwardReturnPoint:
        price_col = "Adj Close" if "Adj Close" in frame.columns else "Close"
        series = frame[price_col].dropna().sort_index()
        ticker = str(frame.attrs.get("ticker", "UNKNOWN"))

        if pd.Timestamp(as_of) not in series.index:
            return ForwardReturnPoint(ticker=ticker, as_of=as_of, horizon_days=horizon_days, gross_return=None, net_return=None)

        idx_t = int(series.index.get_loc(pd.Timestamp(as_of)))
        start_idx = idx_t + 1
        end_idx = idx_t + horizon_days + 1
        if end_idx >= len(series) or start_idx >= len(series):
            return ForwardReturnPoint(ticker=ticker, as_of=as_of, horizon_days=horizon_days, gross_return=None, net_return=None)

        start_price = float(series.iloc[start_idx])
        end_price = float(series.iloc[end_idx])
        if start_price <= 0:
            return ForwardReturnPoint(ticker=ticker, as_of=as_of, horizon_days=horizon_days, gross_return=None, net_return=None)

        gross = (end_price / start_price) - 1.0
        net = gross - tx_cost_rate
        return ForwardReturnPoint(
            ticker=ticker,
            as_of=as_of,
            horizon_days=horizon_days,
            gross_return=float(gross),
            net_return=float(net),
        )


def liquidity_tx_cost_rate(liquidity_status: str, liquidity_score: float | None) -> float:
    # Stage A1 cost schedule proxy because PIT relative market-cap buckets are unavailable.
    if liquidity_status in {"UNAVAILABLE", "FAIL"}:
        return 0.025
    score = float(liquidity_score) if isinstance(liquidity_score, (int, float)) else 0.0
    if score >= 80.0:
        return 0.004
    if score >= 60.0:
        return 0.010
    if score >= 40.0:
        return 0.020
    return 0.025


def spearman_rank_ic(rows: list[tuple[float, float]]) -> float | None:
    if len(rows) < 3:
        return None
    df = pd.DataFrame(rows, columns=["score", "fwd"])
    if df["score"].nunique() < 2 or df["fwd"].nunique() < 2:
        return None
    # Avoid SciPy dependency by computing Spearman as Pearson correlation of average ranks.
    rank_score = df["score"].rank(method="average")
    rank_fwd = df["fwd"].rank(method="average")
    value = rank_score.corr(rank_fwd, method="pearson")
    if value is None or pd.isna(value):
        return None
    return float(value)


def group_mean(points: list[ForwardReturnPoint], tickers: set[str], horizon_days: int, *, net: bool = False) -> float | None:
    vals: list[float] = []
    for point in points:
        if point.horizon_days != horizon_days or point.ticker not in tickers:
            continue
        value = point.net_return if net else point.gross_return
        if isinstance(value, (int, float)):
            vals.append(float(value))
    if not vals:
        return None
    return float(sum(vals) / len(vals))


def row_by_ticker(rows: list[FactorSnapshot]) -> dict[str, FactorSnapshot]:
    return {row.ticker: row for row in rows}


def membership_sets(memberships: list[PortfolioMembership]) -> dict[str, set[str]]:
    return {
        "top10": {m.ticker for m in memberships if m.top10},
        "top20": {m.ticker for m in memberships if m.top20},
        "top_decile": {m.ticker for m in memberships if m.top_decile},
        "bottom_decile": {m.ticker for m in memberships if m.bottom_decile},
        "full": {m.ticker for m in memberships},
    }


def decile_groups(memberships: list[PortfolioMembership]) -> dict[int, set[str]]:
    out: dict[int, set[str]] = {i: set() for i in range(1, 11)}
    for m in memberships:
        out[m.decile].add(m.ticker)
    return out
