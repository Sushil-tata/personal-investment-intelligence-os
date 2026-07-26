from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class CompanyCreateRequest(BaseModel):
    company_id: str
    legal_name: str
    common_name: str | None = None
    company_type: str
    jurisdiction_of_incorporation: str
    primary_economic_country: str
    sector: str | None = None
    industry: str | None = None
    active_from: date
    active_to: date | None = None


class CompanyResponse(BaseModel):
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
    status: str


class SecurityCreateRequest(BaseModel):
    security_id: str
    issuer_company_id: str | None = None
    issuer_name: str | None = None
    security_type: str
    security_name: str
    issue_currency: str
    issue_date: date | None = None
    maturity_date: date | None = None
    share_class_or_seniority: str | None = None
    economic_exposure_type: str | None = None
    active_from: date
    active_to: date | None = None


class SecurityResponse(BaseModel):
    security_id: str
    issuer_company_id: str | None
    issuer_name: str | None
    security_type: str
    security_name: str
    issue_currency: str
    issue_date: date | None
    maturity_date: date | None
    share_class_or_seniority: str | None
    economic_exposure_type: str | None
    active_from: date
    active_to: date | None
    status: str


class ListingCreateRequest(BaseModel):
    listing_id: str
    security_id: str
    exchange_code: str
    ticker: str
    trading_currency: str
    listing_country: str
    is_primary_listing: bool = False
    lot_size: Decimal | None = None
    price_source_symbol: str | None = None
    active_from: date
    active_to: date | None = None


class ListingResponse(BaseModel):
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
    status: str


class IdentifierCreateRequest(BaseModel):
    identifier_id: str
    entity_scope: str
    entity_id: str
    identifier_type: str
    identifier_value: str
    provider_or_authority: str
    active_from: date
    active_to: date | None = None
    source: str


class RelationshipCreateRequest(BaseModel):
    relationship_id: str
    source_scope: str
    source_entity_id: str
    target_scope: str
    target_entity_id: str
    relationship_type: str
    conversion_ratio: Decimal | None = None
    active_from: date
    active_to: date | None = None
    source: str


class ResolutionRequest(BaseModel):
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


class ResolutionCandidateResponse(BaseModel):
    company_id: str | None
    security_id: str | None
    listing_id: str | None
    match_basis: str
    rule_strength: str
    is_active: bool
    is_historical: bool


class ResolutionResponse(BaseModel):
    status: str
    candidates: list[ResolutionCandidateResponse] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    effective_date: date | None = None
    requires_human_review: bool = False


class ResolutionIssueResponse(BaseModel):
    issue_id: str
    source_record_type: str
    source_record_id: str
    reason: str
    candidates: list[dict[str, str | None]]
    recommended_resolution: str | None
    owner_decision: str | None
    reviewer: str | None
    reviewed_at: str | None
    notes: str | None
    resulting_mapping_id: str | None
    status: str
    created_at: str


class ShadowIdentityCheckItem(BaseModel):
    source_type: str
    source_id: str
    legacy_subject: str
    resolution_status: str
    candidate_count: int
    warnings: list[str] = Field(default_factory=list)


class ShadowIdentityDiagnosticsResponse(BaseModel):
    enabled: bool
    checked_records: int
    unresolved_records: int
    items: list[ShadowIdentityCheckItem]
