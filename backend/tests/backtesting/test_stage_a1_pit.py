from __future__ import annotations

from datetime import date

import pandas as pd

from piios_backend.backtesting.price_factor_engine import PriceRiskFactorEngine


def _make_frame(
    ticker: str,
    *,
    start_price: float,
    drift: float,
    shock_day: int | None = None,
    shock_mult: float = 1.0,
    days: int = 330,
) -> pd.DataFrame:
    idx = pd.bdate_range("2022-01-03", periods=days)
    prices = []
    value = start_price
    for i in range(days):
        if shock_day is not None and i == shock_day:
            value *= shock_mult
        value *= 1.0 + drift
        prices.append(value)

    frame = pd.DataFrame(
        {
            "Close": prices,
            "Adj Close": prices,
            "Volume": [250000.0] * len(idx),
        },
        index=idx,
    )
    frame.attrs["ticker"] = ticker
    return frame


def test_future_shock_does_not_change_score_or_rank_at_t() -> None:
    engine = PriceRiskFactorEngine()
    as_of = date(2023, 2, 28)

    base_a = _make_frame("AAA.NS", start_price=100.0, drift=0.0020)
    base_b = _make_frame("BBB.NS", start_price=100.0, drift=0.0010)

    shock_a = base_a.copy()
    # Shock is after as_of, so rank/score at as_of must remain unchanged.
    after_idx = shock_a.index.get_loc(pd.Timestamp("2023-03-15"))
    shock_a.iloc[after_idx:, shock_a.columns.get_loc("Close")] *= 5.0
    shock_a.iloc[after_idx:, shock_a.columns.get_loc("Adj Close")] *= 5.0

    snapshots_base = engine.score_cross_section(
        engine.factor_snapshots_at(as_of, {"AAA.NS": base_a, "BBB.NS": base_b})
    )
    memberships_base = engine.build_memberships(snapshots_base)

    snapshots_shock = engine.score_cross_section(
        engine.factor_snapshots_at(as_of, {"AAA.NS": shock_a, "BBB.NS": base_b})
    )
    memberships_shock = engine.build_memberships(snapshots_shock)

    score_base = {r.ticker: r.price_risk_signal_score for r in snapshots_base if r.eligibility == "ELIGIBLE"}
    score_shock = {r.ticker: r.price_risk_signal_score for r in snapshots_shock if r.eligibility == "ELIGIBLE"}
    rank_base = {m.ticker: m.rank for m in memberships_base}
    rank_shock = {m.ticker: m.rank for m in memberships_shock}

    assert score_base == score_shock
    assert rank_base == rank_shock


def test_forward_return_uses_next_day_to_horizon_not_same_day() -> None:
    engine = PriceRiskFactorEngine()
    as_of = date(2023, 2, 28)

    frame = _make_frame("AAA.NS", start_price=100.0, drift=0.0015)
    point = engine.forward_return(frame, as_of, horizon_days=20, tx_cost_rate=0.0)

    series = frame["Adj Close"].sort_index()
    idx_t = series.index.get_loc(pd.Timestamp(as_of))
    expected = (float(series.iloc[idx_t + 20 + 1]) / float(series.iloc[idx_t + 1])) - 1.0

    assert point.gross_return is not None
    assert abs(point.gross_return - expected) < 1e-12


def test_ineligible_when_history_is_insufficient() -> None:
    engine = PriceRiskFactorEngine()

    short = _make_frame("AAA.NS", start_price=100.0, drift=0.0010, days=120)
    as_of = short.index[-1].date()
    snapshots = engine.factor_snapshots_at(as_of, {"AAA.NS": short})

    assert len(snapshots) == 1
    assert snapshots[0].eligibility == "INSUFFICIENT_HISTORY"
