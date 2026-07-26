from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from .enums import (
    EntityScope,
    IdentifierType,
    IdentityStatus,
    ListingStatus,
    RelationshipType,
    ResolutionIssueStatus,
    SecurityType,
    VerificationStatus,
)
from .value_objects import (
    CompanyId,
    CountryCode,
    CurrencyCode,
    EffectiveDateRange,
    ExchangeCode,
    IdentifierValue,
    ListingId,
    SecurityId,
    Ticker,
)


@dataclass(frozen=True)
class Company:
    company_id: CompanyId
    legal_name: str
    common_name: str | None
    company_type: str
    jurisdiction_of_incorporation: CountryCode
    primary_economic_country: CountryCode
    sector: str | None
    industry: str | None
    active_range: EffectiveDateRange
    status: IdentityStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Security:
    security_id: SecurityId
    issuer_company_id: CompanyId | None
    issuer_name: str | None
    security_type: SecurityType
    security_name: str
    issue_currency: CurrencyCode
    issue_date: date | None
    maturity_date: date | None
    share_class_or_seniority: str | None
    economic_exposure_type: str | None
    active_range: EffectiveDateRange
    status: IdentityStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ListingInstrument:
    listing_id: ListingId
    security_id: SecurityId
    exchange_code: ExchangeCode
    ticker: Ticker
    trading_currency: CurrencyCode
    listing_country: CountryCode
    is_primary_listing: bool
    lot_size: Decimal | None
    price_source_symbol: str | None
    active_range: EffectiveDateRange
    status: ListingStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class SecurityIdentifier:
    identifier_id: str
    scope: EntityScope
    entity_id: str
    identifier_type: IdentifierType
    identifier_value: IdentifierValue
    provider_or_authority: str
    active_range: EffectiveDateRange
    verification_status: VerificationStatus
    source: str
    created_at: datetime


@dataclass(frozen=True)
class TickerHistoryRecord:
    ticker_history_id: str
    listing_id: ListingId
    exchange_code: ExchangeCode
    ticker: Ticker
    active_range: EffectiveDateRange
    change_reason: str | None
    source: str
    verification_status: VerificationStatus


@dataclass(frozen=True)
class SecurityRelationship:
    relationship_id: str
    source_scope: EntityScope
    source_entity_id: str
    target_scope: EntityScope
    target_entity_id: str
    relationship_type: RelationshipType
    conversion_ratio: Decimal | None
    active_range: EffectiveDateRange
    source: str
    verification_status: VerificationStatus


@dataclass(frozen=True)
class LegacyIdentityMapping:
    mapping_id: str
    legacy_source: str
    legacy_record_id: str
    legacy_asset_id: str | None
    legacy_instrument_id: str | None
    legacy_ticker: str | None
    company_id: str | None
    security_id: str | None
    listing_id: str | None
    resolution_status: str
    provenance: str
    created_at: datetime


@dataclass(frozen=True)
class ResolutionCandidate:
    company_id: str | None
    security_id: str | None
    listing_id: str | None
    match_basis: str
    rule_strength: str
    is_active: bool
    is_historical: bool
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IdentityResolutionIssue:
    issue_id: str
    source_record_type: str
    source_record_id: str
    reason: str
    candidate_payload: list[dict[str, str | None]]
    recommended_resolution: str | None
    owner_decision: str | None
    reviewer: str | None
    reviewed_at: datetime | None
    notes: str | None
    resulting_mapping_id: str | None
    status: ResolutionIssueStatus
    created_at: datetime
