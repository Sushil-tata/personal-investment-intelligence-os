from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ResolveIdentityQuery:
    company_id: str | None = None
    security_id: str | None = None
    listing_id: str | None = None
    isin: str | None = None
    exchange: str | None = None
    ticker: str | None = None
    provider: str | None = None
    provider_identifier: str | None = None
    legacy_asset_id: str | None = None
    legacy_ticker: str | None = None
    company_name: str | None = None
    jurisdiction: str | None = None
    trading_currency: str | None = None
    effective_date: date | None = None


@dataclass(frozen=True)
class SearchCompanyQuery:
    name: str


@dataclass(frozen=True)
class UnresolvedIssuesQuery:
    limit: int = 100
