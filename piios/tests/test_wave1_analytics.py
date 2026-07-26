from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from piios.analytics.portfolio.concentration import hhi_metrics, position_weights, top_holdings
from piios.analytics.portfolio.exposure import by_country, by_currency, by_sector, by_theme
from piios.analytics.portfolio.valuation import cash_percentage, listed_equity_percentage, total_value
from piios.portfolio.application.services import PortfolioAnalyticsService
from piios.portfolio.domain.entities import Account, CashBalance, Holding, Portfolio, PortfolioSnapshot, Security
from piios.portfolio.domain.enums import CountryMode, ExposureBasis, PortfolioBucket
from piios.portfolio.domain.value_objects import CostBasis, Currency, Money, Price, Quantity, SecurityIdentifier
from piios.portfolio.infrastructure.csv_loader import load_portfolio_snapshot_from_csv


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fx() -> dict[str, Decimal]:
    return {
        "USD/USD": Decimal("1"),
        "INR/USD": Decimal("0.012"),
        "SGD/USD": Decimal("0.74"),
    }


def load_base_snapshot() -> PortfolioSnapshot:
    snapshot, _ = load_portfolio_snapshot_from_csv(
        file_path=str(FIXTURES / "portfolio_multicountry.csv"),
        reporting_currency="USD",
        as_of_utc=datetime(2026, 7, 26, tzinfo=timezone.utc),
    )
    assert snapshot is not None
    return snapshot


def test_total_value_and_percentage_totals() -> None:
    snapshot = load_base_snapshot()

    total, issues = total_value(snapshot, fx(), ExposureBasis.TOTAL_NET_WORTH)
    currency, _ = by_currency(snapshot, fx())
    assert total > Decimal("0")
    assert not [i for i in issues if i.severity.value == "error"]
    pct_total = sum((item.weight_pct for item in currency), Decimal("0"))
    assert Decimal("99.90") <= pct_total <= Decimal("100.10")


def test_country_exposure_listing_vs_economic() -> None:
    snapshot = load_base_snapshot()

    listing, _ = by_country(snapshot, fx(), mode=CountryMode.LISTING)
    economic, _ = by_country(snapshot, fx(), mode=CountryMode.ECONOMIC)

    listing_map = {row.key: row.weight_pct for row in listing}
    economic_map = {row.key: row.weight_pct for row in economic}
    assert listing_map != economic_map


def test_duplicate_ticker_across_exchanges_are_distinct_in_weights() -> None:
    snapshot = load_base_snapshot()
    weights, _ = position_weights(snapshot, fx())

    assert "ABC:NSE" in weights
    assert "ABC:NYSE" in weights


def test_missing_fx_rate_and_missing_sector_warning() -> None:
    snapshot = load_base_snapshot()
    first = snapshot.portfolio.holdings[0]
    modified = PortfolioSnapshot(
        snapshot_id=snapshot.snapshot_id,
        as_of_utc=snapshot.as_of_utc,
        source_filename=snapshot.source_filename,
        portfolio=Portfolio(
            portfolio_id=snapshot.portfolio.portfolio_id,
            name=snapshot.portfolio.name,
            reporting_currency=snapshot.portfolio.reporting_currency,
            accounts=snapshot.portfolio.accounts,
            holdings=[
                Holding(
                    holding_id=h.holding_id,
                    account_id=h.account_id,
                    bucket=h.bucket,
                    security=Security(
                        identifier=h.security.identifier,
                        name=h.security.name,
                        asset_class=h.security.asset_class,
                        trading_currency=h.security.trading_currency,
                        listing_country=h.security.listing_country,
                        economic_country=h.security.economic_country,
                        sector=None if h.holding_id == first.holding_id else h.security.sector,
                        industry=h.security.industry,
                        theme=h.security.theme,
                        is_listed_equity=h.security.is_listed_equity,
                        is_liquid=h.security.is_liquid,
                    ),
                    quantity=h.quantity,
                    price=h.price,
                    cost_basis=h.cost_basis,
                    price_as_of_utc=h.price_as_of_utc,
                    raw_source=h.raw_source,
                )
                for h in snapshot.portfolio.holdings
            ],
            cash_balances=snapshot.portfolio.cash_balances,
        ),
    )

    fx_missing = {"USD/USD": Decimal("1"), "INR/USD": Decimal("0.012")}
    _, issues = by_sector(modified, fx_missing)
    codes = {issue.code for issue in issues}
    assert "MISSING_FX_RATE" in codes
    assert "MISSING_SECTOR" in codes


def test_cash_only_and_empty_portfolio() -> None:
    account = Account(account_id="cash", account_name="Cash Account", base_currency=Currency("USD"))
    empty_snapshot = PortfolioSnapshot(
        snapshot_id="s-empty",
        as_of_utc=datetime.now(timezone.utc),
        source_filename="synthetic",
        portfolio=Portfolio(
            portfolio_id="p-empty",
            name="Empty",
            reporting_currency=Currency("USD"),
            accounts=[account],
            holdings=[],
            cash_balances=[CashBalance(account_id="cash", balance=Money.from_value(10000, "USD"))],
        ),
    )

    total, _ = total_value(empty_snapshot, fx())
    cash_pct, _ = cash_percentage(empty_snapshot, fx())
    listed_pct, _ = listed_equity_percentage(empty_snapshot, fx())
    assert total == Decimal("10000.00")
    assert cash_pct == Decimal("100.00")
    assert listed_pct == Decimal("0")


def test_stale_price_warning() -> None:
    snapshot = load_base_snapshot()
    stale_holding = snapshot.portfolio.holdings[0]
    updated = Holding(
        holding_id=stale_holding.holding_id,
        account_id=stale_holding.account_id,
        bucket=stale_holding.bucket,
        security=stale_holding.security,
        quantity=stale_holding.quantity,
        price=stale_holding.price,
        cost_basis=stale_holding.cost_basis,
        price_as_of_utc=datetime.now(timezone.utc) - timedelta(days=10),
        raw_source=stale_holding.raw_source,
    )
    stale_snapshot = PortfolioSnapshot(
        snapshot_id=snapshot.snapshot_id,
        as_of_utc=snapshot.as_of_utc,
        source_filename=snapshot.source_filename,
        portfolio=Portfolio(
            portfolio_id=snapshot.portfolio.portfolio_id,
            name=snapshot.portfolio.name,
            reporting_currency=snapshot.portfolio.reporting_currency,
            accounts=snapshot.portfolio.accounts,
            holdings=[updated, *snapshot.portfolio.holdings[1:]],
            cash_balances=snapshot.portfolio.cash_balances,
        ),
    )

    service = PortfolioAnalyticsService(stale_price_hours=24)
    _, issues = service.asset_class_exposure(stale_snapshot, fx())
    assert any(issue.code == "STALE_PRICE" for issue in issues)


def test_proposed_purchase_impact_usd_5000() -> None:
    snapshot = load_base_snapshot()
    service = PortfolioAnalyticsService()
    impact = service.proposed_purchase_impact(
        snapshot=snapshot,
        fx_rates=fx(),
        command_amount=Money.from_value(5000, "USD"),
        proposed_country="United States",
        proposed_sector="Technology",
        proposed_theme="AI Compute",
        proposed_ticker="NVDA:NASDAQ",
    )

    assert impact.after_total_value > impact.before_total_value
    assert impact.position_weight_delta["NVDA:NASDAQ"] > Decimal("0")


def test_rounding_and_hhi() -> None:
    snapshot = load_base_snapshot()
    metrics, _ = hhi_metrics(snapshot, fx())
    top, _ = top_holdings(snapshot, fx(), limit=3)
    assert metrics.hhi_fraction >= Decimal("0")
    assert len(top) == 3
    assert all(item.weight_pct.as_tuple().exponent <= -2 for item in top)


def test_theme_and_currency_exposure_present() -> None:
    snapshot = load_base_snapshot()
    theme, _ = by_theme(snapshot, fx())
    currency, _ = by_currency(snapshot, fx())
    assert theme
    assert currency
