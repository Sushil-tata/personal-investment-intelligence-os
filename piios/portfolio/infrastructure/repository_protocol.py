from __future__ import annotations

from datetime import datetime
from typing import Protocol

from piios.portfolio.domain.entities import Holding, Portfolio, PortfolioSnapshot


class PortfolioRepositoryProtocol(Protocol):
    def save_portfolio(self, portfolio: Portfolio) -> None:
        ...

    def save_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        ...

    def get_latest_snapshot(self, portfolio_id: str) -> PortfolioSnapshot | None:
        ...

    def get_snapshot_by_id(self, snapshot_id: str) -> PortfolioSnapshot | None:
        ...

    def list_holdings(self, portfolio_id: str, as_of_utc: datetime | None = None) -> list[Holding]:
        ...

    def get_portfolio_metadata(self, portfolio_id: str) -> dict[str, str] | None:
        ...
