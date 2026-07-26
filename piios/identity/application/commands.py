from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from piios.identity.domain.enums import EntityScope, IdentifierType, RelationshipType, SecurityType


@dataclass(frozen=True)
class CreateCompanyCommand:
    company_id: str
    legal_name: str
    common_name: str | None
    company_type: str
    jurisdiction_of_incorporation: str
    primary_economic_country: str
    sector: str | None
    industry: str | None
    active_from: date
    active_to: date | None


@dataclass(frozen=True)
class CreateSecurityCommand:
    security_id: str
    issuer_company_id: str | None
    issuer_name: str | None
    security_type: SecurityType
    security_name: str
    issue_currency: str
    issue_date: date | None
    maturity_date: date | None
    share_class_or_seniority: str | None
    economic_exposure_type: str | None
    active_from: date
    active_to: date | None


@dataclass(frozen=True)
class CreateListingCommand:
    listing_id: str
    security_id: str
    exchange_code: str
    ticker: str
    trading_currency: str
    listing_country: str
    is_primary_listing: bool
    lot_size: Decimal | None
    price_source_symbol: str | None
    active_from: date
    active_to: date | None


@dataclass(frozen=True)
class AddIdentifierCommand:
    identifier_id: str
    scope: EntityScope
    entity_id: str
    identifier_type: IdentifierType
    identifier_value: str
    provider_or_authority: str
    active_from: date
    active_to: date | None
    source: str


@dataclass(frozen=True)
class AddTickerHistoryCommand:
    ticker_history_id: str
    listing_id: str
    exchange_code: str
    ticker: str
    active_from: date
    active_to: date | None
    change_reason: str | None
    source: str


@dataclass(frozen=True)
class CreateRelationshipCommand:
    relationship_id: str
    source_scope: EntityScope
    source_entity_id: str
    target_scope: EntityScope
    target_entity_id: str
    relationship_type: RelationshipType
    conversion_ratio: Decimal | None
    active_from: date
    active_to: date | None
    source: str


@dataclass(frozen=True)
class MarkIdentityVerifiedCommand:
    identifier_id: str


@dataclass(frozen=True)
class RetireListingCommand:
    listing_id: str
    retired_on: date


@dataclass(frozen=True)
class LinkLegacyIdentityCommand:
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
