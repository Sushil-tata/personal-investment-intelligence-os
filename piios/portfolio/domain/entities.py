from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from .enums import DataIssueSeverity, PortfolioBucket
from .value_objects import CostBasis, Currency, Money, Price, Quantity, SecurityIdentifier


@dataclass(frozen=True)
class DataQualityIssue:
    severity: DataIssueSeverity
    code: str
    message: str
    row_number: int | None = None
    field_name: str | None = None


@dataclass(frozen=True)
class Security:
    identifier: SecurityIdentifier
    name: str
    asset_class: str
    trading_currency: Currency
    listing_country: str
    economic_country: str
    sector: str | None = None
    industry: str | None = None
    theme: str | None = None
    company_id: str | None = None
    security_id: str | None = None
    listing_id: str | None = None
    identity_resolution_status: str | None = None
    is_listed_equity: bool = True
    is_liquid: bool = True


@dataclass(frozen=True)
class Account:
    account_id: str
    account_name: str
    base_currency: Currency


@dataclass(frozen=True)
class Holding:
    holding_id: str
    account_id: str
    bucket: PortfolioBucket
    security: Security
    quantity: Quantity
    price: Price
    cost_basis: CostBasis | None = None
    price_as_of_utc: datetime | None = None
    raw_source: dict[str, str] = field(default_factory=dict)

    @property
    def market_value_original(self) -> Money:
        return Money(amount=self.quantity.value * self.price.amount, currency=self.price.currency)


@dataclass(frozen=True)
class CashBalance:
    account_id: str
    balance: Money


@dataclass(frozen=True)
class Portfolio:
    portfolio_id: str
    name: str
    reporting_currency: Currency
    accounts: list[Account]
    holdings: list[Holding]
    cash_balances: list[CashBalance] = field(default_factory=list)


@dataclass(frozen=True)
class PortfolioSnapshot:
    snapshot_id: str
    portfolio: Portfolio
    as_of_utc: datetime
    source_filename: str


@dataclass(frozen=True)
class ProposedAllocation:
    account_id: str
    bucket: PortfolioBucket
    security_identifier: SecurityIdentifier
    security_name: str
    asset_class: str
    listing_country: str
    economic_country: str
    sector: str | None
    industry: str | None
    theme: str | None
    amount: Money


@dataclass(frozen=True)
class ProposedTradeImpact:
    reporting_currency: str
    proposed_amount: Decimal
    before_total_value: Decimal
    after_total_value: Decimal
    listed_equity_pct_before: Decimal
    listed_equity_pct_after: Decimal
    cash_pct_before: Decimal
    cash_pct_after: Decimal
    country_concentration_delta: dict[str, Decimal]
    sector_concentration_delta: dict[str, Decimal]
    theme_concentration_delta: dict[str, Decimal]
    position_weight_delta: dict[str, Decimal]
    issues: list[DataQualityIssue] = field(default_factory=list)
