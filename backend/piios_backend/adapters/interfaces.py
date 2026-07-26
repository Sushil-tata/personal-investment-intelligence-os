from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass
class PricePoint:
    ticker: str
    timestamp: str
    close: float
    volume: float


class MarketDataAdapter(Protocol):
    def history(self, ticker: str, start: date, end: date) -> list[PricePoint]:
        ...


class FundamentalsAdapter(Protocol):
    def snapshot(self, ticker: str) -> dict:
        ...
