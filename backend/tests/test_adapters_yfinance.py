from datetime import date

import pandas as pd

from piios_backend.adapters.yfinance_adapter import YFinanceAdapter


class _FakeTicker:
    def history(self, start: str, end: str):
        idx = pd.to_datetime(["2026-01-02", "2026-01-03"])
        return pd.DataFrame({"Close": [100.0, 101.5], "Volume": [10, 12]}, index=idx)


def test_yfinance_adapter_interface_shape(monkeypatch) -> None:
    import yfinance as yf

    monkeypatch.setattr(yf, "Ticker", lambda ticker: _FakeTicker())
    adapter = YFinanceAdapter()
    rows = adapter.history("MSFT", start=date(2026, 1, 1), end=date(2026, 1, 5))
    assert isinstance(rows, list)
    assert rows[0].ticker == "MSFT"
    assert rows[0].close == 100.0
