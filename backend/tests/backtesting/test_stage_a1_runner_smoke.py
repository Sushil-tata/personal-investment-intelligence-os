from __future__ import annotations

from datetime import date

import pandas as pd

from piios_backend.backtesting.data import FrozenHistorySnapshot, TickerHistoryMeta
from piios_backend.backtesting.runner import StageA1BacktestRunner, StageA1Config


def _frame(ticker: str, start: str, periods: int, drift: float) -> pd.DataFrame:
    idx = pd.bdate_range(start, periods=periods)
    values = []
    price = 100.0
    for _ in idx:
        price *= 1.0 + drift
        values.append(price)
    frame = pd.DataFrame(
        {
            "Close": values,
            "Adj Close": values,
            "Volume": [500000.0] * len(idx),
        },
        index=idx,
    )
    frame.attrs["ticker"] = ticker
    return frame


def test_runner_smoke_with_frozen_history(monkeypatch, tmp_path) -> None:
    tickers = ["AAA.NS", "BBB.NS", "CCC.NS"]
    frames = {
        "AAA.NS": _frame("AAA.NS", "2021-01-01", 820, 0.0018),
        "BBB.NS": _frame("BBB.NS", "2021-01-01", 820, 0.0012),
        "CCC.NS": _frame("CCC.NS", "2021-01-01", 820, 0.0006),
    }
    meta = {
        t: TickerHistoryMeta(
            ticker=t,
            provider="synthetic",
            retrieval_timestamp="2026-01-01T00:00:00+00:00",
            first_date="2021-01-01",
            last_date="2024-02-01",
            observation_count=len(frames[t]),
        )
        for t in tickers
    }

    frozen = FrozenHistorySnapshot(
        provider="synthetic",
        retrieval_timestamp="2026-01-01T00:00:00+00:00",
        by_ticker=frames,
        metadata=meta,
        failures={},
    )

    monkeypatch.setattr("piios_backend.backtesting.runner.load_india_universe", lambda: tickers)
    monkeypatch.setattr("piios_backend.backtesting.runner.freeze_price_history", lambda *args, **kwargs: frozen)

    output_root = tmp_path / "runtime"
    config = StageA1Config(
        start_date=date(2022, 1, 1),
        end_date=date(2024, 1, 31),
        min_months=12,
        output_root=str(output_root),
        bootstrap_iterations=200,
    )
    payload = StageA1BacktestRunner(config).run()

    assert payload["signal_state"] in {
        "PRICE_SIGNAL_HAS_EDGE",
        "PRICE_SIGNAL_WEAK",
        "PRICE_SIGNAL_NO_EDGE",
    }
    assert payload["first_ranking_date"] is not None
    assert payload["last_ranking_date"] is not None
    assert payload["ranking_month_count"] == payload["diagnostics"]["month_count"]
    assert (output_root / "stage_a1_summary.json").exists()
    assert (output_root / "factor_snapshots.csv").exists()
    assert (output_root / "monthly_ranks.csv").exists()
    assert (output_root / "forward_returns.csv").exists()
