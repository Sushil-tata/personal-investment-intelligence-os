from __future__ import annotations

from datetime import datetime, timezone

from piios.portfolio.domain.entities import Account, CashBalance, Portfolio, PortfolioSnapshot
from piios.portfolio.domain.value_objects import Currency, Money
from piios.portfolio.infrastructure.in_memory_repository import InMemoryPortfolioRepository


def test_in_memory_repository_roundtrip() -> None:
    repo = InMemoryPortfolioRepository()
    portfolio = Portfolio(
        portfolio_id="p1",
        name="Test",
        reporting_currency=Currency("USD"),
        accounts=[Account(account_id="a1", account_name="Primary", base_currency=Currency("USD"))],
        holdings=[],
        cash_balances=[CashBalance(account_id="a1", balance=Money.from_value(1000, "USD"))],
    )
    repo.save_portfolio(portfolio)
    snapshot = PortfolioSnapshot(
        snapshot_id="s1",
        portfolio=portfolio,
        as_of_utc=datetime(2026, 7, 26, tzinfo=timezone.utc),
        source_filename="unit",
    )
    repo.save_snapshot(snapshot)

    latest = repo.get_latest_snapshot("p1")
    assert latest is not None
    assert latest.snapshot_id == "s1"
    assert repo.get_snapshot_by_id("s1") is not None
    assert repo.get_portfolio_metadata("p1") is not None
