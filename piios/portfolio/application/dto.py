from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class DataIssueDTO(BaseModel):
    severity: str
    code: str
    message: str
    row_number: int | None = None
    field_name: str | None = None


class HoldingDTO(BaseModel):
    holding_id: str
    ticker: str
    name: str
    account_id: str
    bucket: str
    quantity: Decimal
    price: Decimal
    trading_currency: str
    asset_class: str
    listing_country: str
    economic_country: str
    sector: str | None = None
    industry: str | None = None
    theme: str | None = None
    company_id: str | None = None
    security_id: str | None = None
    listing_id: str | None = None
    identity_resolution_status: str | None = None


class CashBalanceDTO(BaseModel):
    account_id: str
    currency: str
    amount: Decimal


class PortfolioSnapshotDTO(BaseModel):
    snapshot_id: str
    portfolio_id: str
    portfolio_name: str
    reporting_currency: str
    as_of_utc: datetime
    source_filename: str
    holdings: list[HoldingDTO]
    cash_balances: list[CashBalanceDTO] = Field(default_factory=list)


class PortfolioImportResultDTO(BaseModel):
    snapshot: PortfolioSnapshotDTO | None
    issues: list[DataIssueDTO] = Field(default_factory=list)


class ExposureItemDTO(BaseModel):
    key: str
    value_reporting: Decimal
    weight_pct: Decimal


class ConcentrationMetricsDTO(BaseModel):
    hhi_fraction: Decimal
    hhi_basis_points: Decimal
    top_1_weight_pct: Decimal
    top_5_weight_pct: Decimal
    top_10_weight_pct: Decimal


class ProposedTradeImpactDTO(BaseModel):
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
    issues: list[DataIssueDTO]
