from datetime import date

from piios_backend.adapters.interfaces import MarketDataAdapter, PricePoint


class PolygonAdapter(MarketDataAdapter):
    def history(self, ticker: str, start: date, end: date) -> list[PricePoint]:
        return []
