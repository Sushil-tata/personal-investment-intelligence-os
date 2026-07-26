from datetime import date

import yfinance as yf

from piios_backend.adapters.interfaces import MarketDataAdapter, PricePoint


class YFinanceAdapter(MarketDataAdapter):
    def history(self, ticker: str, start: date, end: date) -> list[PricePoint]:
        frame = yf.Ticker(ticker).history(start=start.isoformat(), end=end.isoformat())
        rows: list[PricePoint] = []
        if frame.empty:
            return rows
        for ts, row in frame.iterrows():
            rows.append(
                PricePoint(
                    ticker=ticker,
                    timestamp=str(ts),
                    close=float(row["Close"]),
                    volume=float(row.get("Volume", 0.0)),
                )
            )
        return rows
