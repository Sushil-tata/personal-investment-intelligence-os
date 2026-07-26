from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from piios.portfolio.application.services import PortfolioAnalyticsService
from piios.portfolio.domain.entities import Account, CashBalance, Portfolio, PortfolioSnapshot, Security, Holding
from piios.portfolio.domain.enums import CountryMode, ExposureBasis, PortfolioBucket
from piios.portfolio.domain.value_objects import CostBasis, Currency, Money, Price, Quantity, SecurityIdentifier


def _bucket_from_legacy(bucket: str | None) -> PortfolioBucket:
    if not bucket:
        return PortfolioBucket.UNKNOWN
    lower = bucket.lower()
    for item in PortfolioBucket:
        if item.value.lower() == lower:
            return item
    return PortfolioBucket.UNKNOWN


def from_legacy_holdings(
    legacy_holdings: list[object],
    reporting_currency: str = "USD",
    snapshot_id: str = "legacy-snapshot",
    owner: str = "Legacy Portfolio",
) -> PortfolioSnapshot:
    account = Account(account_id="legacy-main", account_name="Legacy Main", base_currency=Currency(reporting_currency))
    holdings: list[Holding] = []

    for row in legacy_holdings:
        ticker = str(getattr(row, "ticker", "UNKNOWN"))
        currency = str(getattr(row, "currency", "USD"))
        quantity = Quantity.from_value(getattr(row, "quantity", 0))
        market_value = Decimal(str(getattr(row, "market_value", 0)))
        unit_price = (market_value / quantity.value) if quantity.value > Decimal("0") else Decimal("0")
        security = Security(
            identifier=SecurityIdentifier(ticker=ticker),
            name=str(getattr(row, "name", ticker)),
            asset_class=str(getattr(row, "asset_class", "Equity")),
            trading_currency=Currency(currency),
            listing_country=str(getattr(row, "geography", "Unknown")),
            economic_country=str(getattr(row, "geography", "Unknown")),
            sector=str(getattr(row, "sector", "Unknown")),
            industry=None,
            theme=str(getattr(row, "theme", "Unknown")),
            is_listed_equity=True,
            is_liquid=True,
        )
        holdings.append(
            Holding(
                holding_id=str(getattr(row, "holding_id", f"legacy-{ticker}")),
                account_id="legacy-main",
                bucket=_bucket_from_legacy(str(getattr(getattr(row, "bucket", None), "value", getattr(row, "bucket", None)))),
                security=security,
                quantity=quantity,
                price=Price.from_value(unit_price, currency),
                cost_basis=CostBasis(unit_cost=Money.from_value(unit_price, currency)),
            )
        )

    portfolio = Portfolio(
        portfolio_id="legacy-portfolio",
        name=owner,
        reporting_currency=Currency(reporting_currency),
        accounts=[account],
        holdings=holdings,
        cash_balances=[CashBalance(account_id="legacy-main", balance=Money.from_value(0, reporting_currency))],
    )
    return PortfolioSnapshot(
        snapshot_id=snapshot_id,
        portfolio=portfolio,
        as_of_utc=datetime.now(timezone.utc),
        source_filename="legacy-adapter",
    )


def to_legacy_allocation(snapshot: PortfolioSnapshot, fx_rates: dict[str, Decimal], dimension: str) -> dict:
    service = PortfolioAnalyticsService()
    exposure, _ = service._exposure_by_dimension(snapshot, fx_rates, dimension, ExposureBasis.LIQUID_INVESTABLE, CountryMode.LISTING)
    total, _ = service.total_portfolio_value(snapshot, fx_rates, ExposureBasis.LIQUID_INVESTABLE)
    return {
        "total_value": float(total),
        "items": [
            {
                "dimension": dimension,
                "key": item.key,
                "market_value": float(item.value_reporting),
                "percentage": float(item.weight_pct),
            }
            for item in exposure
        ],
    }


def to_legacy_currency_exposure(snapshot: PortfolioSnapshot, fx_rates: dict[str, Decimal]) -> dict:
    service = PortfolioAnalyticsService()
    exposure, _ = service.currency_exposure(snapshot, fx_rates, ExposureBasis.LIQUID_INVESTABLE)
    total, _ = service.total_portfolio_value(snapshot, fx_rates, ExposureBasis.LIQUID_INVESTABLE)
    return {
        "total_value": float(total),
        "items": [
            {
                "currency": item.key,
                "market_value": float(item.value_reporting),
                "percentage": float(item.weight_pct),
            }
            for item in exposure
        ],
    }


def to_legacy_net_worth(snapshot: PortfolioSnapshot, fx_rates: dict[str, Decimal]) -> dict:
    service = PortfolioAnalyticsService()
    total_assets, _ = service.total_portfolio_value(snapshot, fx_rates, ExposureBasis.TOTAL_NET_WORTH)
    return {
        "owner": snapshot.portfolio.name,
        "total_assets": float(total_assets),
        "total_liabilities": 0.0,
        "net_worth": float(total_assets),
        "breakdown": [
            {"category": "Investments", "value": float(total_assets)},
            {"category": "Liabilities", "value": 0.0},
        ],
    }
