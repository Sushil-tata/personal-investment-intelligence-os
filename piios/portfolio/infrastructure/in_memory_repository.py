from __future__ import annotations

from datetime import datetime

from piios.portfolio.domain.entities import Holding, Portfolio, PortfolioSnapshot
from piios.portfolio.infrastructure.repository_protocol import PortfolioRepositoryProtocol


class InMemoryPortfolioRepository(PortfolioRepositoryProtocol):
    def __init__(self) -> None:
        self._portfolios: dict[str, Portfolio] = {}
        self._snapshots: dict[str, PortfolioSnapshot] = {}
        self._portfolio_snapshots: dict[str, list[str]] = {}

    def save_portfolio(self, portfolio: Portfolio) -> None:
        self._portfolios[portfolio.portfolio_id] = portfolio

    def save_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        self._snapshots[snapshot.snapshot_id] = snapshot
        self._portfolio_snapshots.setdefault(snapshot.portfolio.portfolio_id, []).append(snapshot.snapshot_id)

    def get_latest_snapshot(self, portfolio_id: str) -> PortfolioSnapshot | None:
        ids = self._portfolio_snapshots.get(portfolio_id, [])
        if not ids:
            return None
        rows = [self._snapshots[sid] for sid in ids]
        rows.sort(key=lambda x: x.as_of_utc)
        return rows[-1]

    def get_snapshot_by_id(self, snapshot_id: str) -> PortfolioSnapshot | None:
        return self._snapshots.get(snapshot_id)

    def list_holdings(self, portfolio_id: str, as_of_utc: datetime | None = None) -> list[Holding]:
        if as_of_utc is None:
            latest = self.get_latest_snapshot(portfolio_id)
            return latest.portfolio.holdings if latest else []

        ids = self._portfolio_snapshots.get(portfolio_id, [])
        if not ids:
            return []
        selected = [self._snapshots[sid] for sid in ids if self._snapshots[sid].as_of_utc <= as_of_utc]
        if not selected:
            return []
        selected.sort(key=lambda x: x.as_of_utc)
        return selected[-1].portfolio.holdings

    def get_portfolio_metadata(self, portfolio_id: str) -> dict[str, str] | None:
        portfolio = self._portfolios.get(portfolio_id)
        if not portfolio:
            return None
        return {
            "portfolio_id": portfolio.portfolio_id,
            "name": portfolio.name,
            "reporting_currency": portfolio.reporting_currency.code,
        }
