from typing import Optional

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, SQLModel

from piios_backend.schemas.enums import RecommendationStatus


class Portfolio(SQLModel, table=True):
    __tablename__ = "portfolios"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    owner: str


class Account(SQLModel, table=True):
    __tablename__ = "accounts"
    id: Optional[int] = Field(default=None, primary_key=True)
    portfolio_id: int
    provider: str
    currency: str


class Asset(SQLModel, table=True):
    __tablename__ = "assets"
    id: Optional[int] = Field(default=None, primary_key=True)
    ticker: str
    name: str
    asset_class: str


class HoldingEntity(SQLModel, table=True):
    __tablename__ = "holdings"
    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int
    asset_id: int
    quantity: float
    market_value: float
    bucket: str | None = None


class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"
    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int
    asset_id: int
    transaction_type: str
    quantity: float
    price: float
    timestamp: str


class Watchlist(SQLModel, table=True):
    __tablename__ = "watchlist"
    id: Optional[int] = Field(default=None, primary_key=True)
    ticker: str
    note: str
    bucket: str | None = None


class MarketPrice(SQLModel, table=True):
    __tablename__ = "market_prices"
    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int
    price: float
    timestamp: str


class Fundamental(SQLModel, table=True):
    __tablename__ = "fundamentals"
    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int
    payload_json: str
    timestamp: str


class MacroIndicator(SQLModel, table=True):
    __tablename__ = "macro_indicators"
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str
    value: float
    timestamp: str


class ResearchDocument(SQLModel, table=True):
    __tablename__ = "research_documents"
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    content: str
    source: str
    url: str | None = None
    timestamp: str
    credibility_score: float
    extracted_entities: str
    related_ticker_theme: str


class SourceScore(SQLModel, table=True):
    __tablename__ = "source_scores"
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str
    score: float
    timestamp: str


class StockScore(SQLModel, table=True):
    __tablename__ = "stock_scores"
    id: Optional[int] = Field(default=None, primary_key=True)
    ticker: str
    total_score: float
    bucket: str | None = None
    timestamp: str


class RecommendationEntity(SQLModel, table=True):
    __tablename__ = "recommendations"
    id: Optional[int] = Field(default=None, primary_key=True)
    recommendation_id: str
    ticker: str
    thesis_id: str | None = None
    bucket: str | None = None
    bull_case: str
    bear_case: str
    why_now: str
    why_not_now: str
    thesis_invalidation_trigger: str
    position_size_suggestion: str
    time_horizon: str
    confidence_score: float
    portfolio_fit_score: float
    portfolio_bucket: str
    data_freshness_timestamp: str
    source_documents: str
    source_links: str
    rationale: str
    data_source: str
    model_version: str
    status: RecommendationStatus = RecommendationStatus.DRAFT
    approved_by: str | None = None
    advisory_only: bool = True
    created_at: str
    updated_at: str


class InvestmentThesisEntity(SQLModel, table=True):
    __tablename__ = "investment_theses"
    id: Optional[int] = Field(default=None, primary_key=True)
    thesis_id: str
    ticker: str
    asset_name: str
    theme: str
    bucket: str
    thesis: str
    bull_case: str
    bear_case: str
    why_now: str
    why_not_now: str
    invalidation_trigger: str
    valuation_notes: str
    expected_holding_period: str
    source_documents: str
    confidence_score: float
    status: RecommendationStatus = RecommendationStatus.DRAFT
    created_at: str
    updated_at: str


class ThesisRootEntity(SQLModel, table=True):
    __tablename__ = "thesis_roots"
    __table_args__ = (
        UniqueConstraint("thesis_id", name="uq_thesis_roots_thesis_id"),
        Index("ix_thesis_roots_ticker", "ticker"),
        Index("ix_thesis_roots_status", "lifecycle_status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    thesis_id: str
    ticker: str
    lifecycle_status: str
    current_version_number: int = 1
    created_at: str
    updated_at: str
    closed_reason: str | None = None
    closed_at: str | None = None


class ThesisVersionEntity(SQLModel, table=True):
    __tablename__ = "thesis_versions"
    __table_args__ = (
        UniqueConstraint("version_id", name="uq_thesis_versions_version_id"),
        UniqueConstraint("thesis_id", "version_number", name="uq_thesis_versions_thesis_version_number"),
        Index("ix_thesis_versions_thesis_id", "thesis_id"),
        Index("ix_thesis_versions_status", "status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    version_id: str
    thesis_id: str
    version_number: int
    asset_name: str
    theme: str
    bucket: str
    thesis: str
    bull_case: str
    bear_case: str
    why_now: str
    why_not_now: str
    invalidation_trigger: str
    valuation_notes: str
    expected_holding_period: str
    source_documents: str
    confidence_score: float
    status: str
    created_at: str


class ThesisClaimEntity(SQLModel, table=True):
    __tablename__ = "thesis_claims"
    __table_args__ = (
        UniqueConstraint("claim_id", name="uq_thesis_claims_claim_id"),
        UniqueConstraint("thesis_version_id", "claim_key", name="uq_thesis_claims_version_claim_key"),
        Index("ix_thesis_claims_thesis_version_id", "thesis_version_id"),
        Index("ix_thesis_claims_thesis_id", "thesis_id"),
        Index("ix_thesis_claims_status", "status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    claim_id: str
    thesis_version_id: str
    thesis_id: str | None = None
    claim_key: str
    claim_text: str
    claim_type: str
    status: str
    active_from: str
    active_to: str | None = None
    created_at: str
    updated_at: str


class EvidenceSourceEntity(SQLModel, table=True):
    __tablename__ = "evidence_sources"
    __table_args__ = (
        UniqueConstraint("source_id", name="uq_evidence_sources_source_id"),
        Index("ix_evidence_sources_type", "source_type"),
        Index("ix_evidence_sources_system", "source_system"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: str
    source_type: str
    publisher: str
    url: str | None = None
    source_system: str
    published_at: str | None = None
    retrieved_at: str
    credibility_tier: str
    created_at: str


class EvidenceItemEntity(SQLModel, table=True):
    __tablename__ = "evidence_items"
    __table_args__ = (
        UniqueConstraint("evidence_id", name="uq_evidence_items_evidence_id"),
        Index("ix_evidence_items_source_id", "source_id"),
        Index("ix_evidence_items_content_hash", "content_hash"),
        Index("ix_evidence_items_as_of_date", "as_of_date"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    evidence_id: str
    source_id: str
    title: str
    excerpt: str
    content_hash: str | None = None
    as_of_date: str | None = None
    metadata_json: str
    created_at: str


class ClaimEvidenceInterpretationEntity(SQLModel, table=True):
    __tablename__ = "claim_evidence_interpretations"
    __table_args__ = (
        UniqueConstraint("interpretation_id", name="uq_claim_evidence_interpretations_interpretation_id"),
        Index("ix_claim_evidence_interp_claim_active", "claim_id", "effective_to"),
        Index("ix_claim_evidence_interp_evidence_id", "evidence_id"),
        Index("ix_claim_evidence_interp_supersedes", "supersedes_interpretation_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    interpretation_id: str
    claim_id: str
    evidence_id: str
    relation: str
    strength: str
    note: str | None = None
    effective_from: str
    effective_to: str | None = None
    supersedes_interpretation_id: str | None = None
    superseded_by_interpretation_id: str | None = None
    created_at: str


class ProvenanceRecordEntity(SQLModel, table=True):
    __tablename__ = "provenance_records"
    __table_args__ = (
        UniqueConstraint("provenance_id", name="uq_provenance_records_provenance_id"),
        Index("ix_provenance_records_entity", "entity_type", "entity_id"),
        Index("ix_provenance_records_source_system", "source_system"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    provenance_id: str
    entity_type: str
    entity_id: str
    action: str
    actor_type: str
    actor_reference: str
    ingestion_method: str
    source_system: str
    extraction_method: str
    model_name: str | None = None
    model_version: str | None = None
    payload_hash: str | None = None
    created_at: str


class TacticalSignalEntity(SQLModel, table=True):
    __tablename__ = "tactical_signals"
    id: Optional[int] = Field(default=None, primary_key=True)
    signal_id: str
    ticker: str
    bucket: str | None = None
    status: str
    entry_zone: str
    invalidation: str
    target: str
    advisory_only: bool = True
    created_at: str


class RiskProfile(SQLModel, table=True):
    __tablename__ = "risk_profiles"
    id: Optional[int] = Field(default=None, primary_key=True)
    max_position_pct: float
    max_tactical_pct: float
    max_single_ticker_pct: float


class JournalEntryEntity(SQLModel, table=True):
    __tablename__ = "journal_entries"
    id: Optional[int] = Field(default=None, primary_key=True)
    entry_id: str
    ticker: str
    notes: str
    outcome: str
    bucket: str | None = None
    created_at: str


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"
    id: Optional[int] = Field(default=None, primary_key=True)
    event_type: str
    details: str
    timestamp: str


class GraphRun(SQLModel, table=True):
    __tablename__ = "graph_runs"
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str
    ticker: str
    status: str
    requested_by: str
    created_at: str
    updated_at: str


class GraphNodeOutput(SQLModel, table=True):
    __tablename__ = "graph_node_outputs"
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str
    node_name: str
    output_json: str
    timestamp: str


class FamilyPortfolioMemberEntity(SQLModel, table=True):
    __tablename__ = "family_portfolio_members"
    id: Optional[int] = Field(default=None, primary_key=True)
    member_id: str
    member_name: str
    relation: str
    base_currency: str


class IPSConstraintEntity(SQLModel, table=True):
    __tablename__ = "ips_constraints"
    id: Optional[int] = Field(default=None, primary_key=True)
    constraint_id: str
    name: str
    rule_type: str
    threshold_value: float
    severity: str
    enabled: bool = True


class InstrumentMasterEntity(SQLModel, table=True):
    __tablename__ = "instrument_master"
    id: Optional[int] = Field(default=None, primary_key=True)
    instrument_id: str
    ticker: str
    name: str
    asset_class: str
    currency: str
    exchange: str
    data_source: str


class DataTrustSourceEntity(SQLModel, table=True):
    __tablename__ = "data_trust_sources"
    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: str
    source_name: str
    trust_tier: str
    score: float
    freshness_sla_hours: int


class IdentityCompanyEntity(SQLModel, table=True):
    __tablename__ = "identity_companies"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_identity_companies_company_id"),
        Index("ix_identity_companies_legal_name", "legal_name"),
        Index("ix_identity_companies_status", "status"),
        Index("ix_identity_companies_effective_dates", "active_from", "active_to"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: str
    legal_name: str
    common_name: str | None = None
    company_type: str
    jurisdiction_of_incorporation: str
    primary_economic_country: str
    sector: str | None = None
    industry: str | None = None
    active_from: str
    active_to: str | None = None
    status: str
    created_at: str
    updated_at: str


class IdentitySecurityEntity(SQLModel, table=True):
    __tablename__ = "identity_securities"
    __table_args__ = (
        UniqueConstraint("security_id", name="uq_identity_securities_security_id"),
        Index("ix_identity_securities_company_id", "issuer_company_id"),
        Index("ix_identity_securities_status", "status"),
        Index("ix_identity_securities_effective_dates", "active_from", "active_to"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    security_id: str
    issuer_company_id: str | None = None
    issuer_name: str | None = None
    security_type: str
    security_name: str
    issue_currency: str
    issue_date: str | None = None
    maturity_date: str | None = None
    share_class_or_seniority: str | None = None
    economic_exposure_type: str | None = None
    active_from: str
    active_to: str | None = None
    status: str
    created_at: str
    updated_at: str


class IdentityListingInstrumentEntity(SQLModel, table=True):
    __tablename__ = "identity_listing_instruments"
    __table_args__ = (
        UniqueConstraint("listing_id", name="uq_identity_listing_listing_id"),
        Index("ix_identity_listing_security_id", "security_id"),
        Index("ix_identity_listing_exchange_ticker", "exchange_code", "ticker_canonical"),
        Index("ix_identity_listing_status", "status"),
        Index("ix_identity_listing_effective_dates", "active_from", "active_to"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: str
    security_id: str
    exchange_code: str
    ticker_source: str
    ticker_canonical: str
    trading_currency: str
    listing_country: str
    is_primary_listing: bool = False
    lot_size: float | None = None
    price_source_symbol: str | None = None
    active_from: str
    active_to: str | None = None
    status: str
    created_at: str
    updated_at: str


class IdentitySecurityIdentifierEntity(SQLModel, table=True):
    __tablename__ = "identity_security_identifiers"
    __table_args__ = (
        UniqueConstraint("identifier_id", name="uq_identity_identifiers_identifier_id"),
        Index("ix_identity_identifiers_lookup", "identifier_type", "identifier_value", "provider_or_authority"),
        Index("ix_identity_identifiers_scope", "entity_scope", "entity_id"),
        Index("ix_identity_identifiers_effective_dates", "active_from", "active_to"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    identifier_id: str
    entity_scope: str
    entity_id: str
    identifier_type: str
    identifier_value: str
    provider_or_authority: str
    active_from: str
    active_to: str | None = None
    verification_status: str
    source: str
    created_at: str
    updated_at: str


class IdentityTickerHistoryEntity(SQLModel, table=True):
    __tablename__ = "identity_ticker_history"
    __table_args__ = (
        UniqueConstraint("ticker_history_id", name="uq_identity_ticker_history_id"),
        Index("ix_identity_ticker_listing", "listing_id"),
        Index("ix_identity_ticker_lookup", "exchange_code", "ticker_canonical"),
        Index("ix_identity_ticker_effective_dates", "active_from", "active_to"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    ticker_history_id: str
    listing_id: str
    exchange_code: str
    ticker_source: str
    ticker_canonical: str
    active_from: str
    active_to: str | None = None
    change_reason: str | None = None
    source: str
    verification_status: str
    created_at: str
    updated_at: str


class IdentitySecurityRelationshipEntity(SQLModel, table=True):
    __tablename__ = "identity_security_relationships"
    __table_args__ = (
        UniqueConstraint("relationship_id", name="uq_identity_relationships_relationship_id"),
        Index("ix_identity_relationships_source", "source_scope", "source_entity_id"),
        Index("ix_identity_relationships_target", "target_scope", "target_entity_id"),
        Index("ix_identity_relationships_effective_dates", "active_from", "active_to"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    relationship_id: str
    source_scope: str
    source_entity_id: str
    target_scope: str
    target_entity_id: str
    relationship_type: str
    conversion_ratio: float | None = None
    active_from: str
    active_to: str | None = None
    source: str
    verification_status: str
    created_at: str
    updated_at: str


class IdentityLegacyMappingEntity(SQLModel, table=True):
    __tablename__ = "identity_legacy_mappings"
    __table_args__ = (
        UniqueConstraint("mapping_id", name="uq_identity_legacy_mapping_id"),
        Index("ix_identity_legacy_source_record", "legacy_source", "legacy_record_id"),
        Index("ix_identity_legacy_asset", "legacy_asset_id"),
        Index("ix_identity_legacy_ticker", "legacy_ticker"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    mapping_id: str
    legacy_source: str
    legacy_record_id: str
    legacy_asset_id: str | None = None
    legacy_instrument_id: str | None = None
    legacy_ticker: str | None = None
    company_id: str | None = None
    security_id: str | None = None
    listing_id: str | None = None
    resolution_status: str
    provenance: str
    created_at: str


class IdentityResolutionIssueEntity(SQLModel, table=True):
    __tablename__ = "identity_resolution_issues"
    __table_args__ = (
        UniqueConstraint("issue_id", name="uq_identity_resolution_issue_id"),
        Index("ix_identity_resolution_issue_status", "status"),
        Index("ix_identity_resolution_issue_source", "source_record_type", "source_record_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    issue_id: str
    source_record_type: str
    source_record_id: str
    reason: str
    candidate_payload: str
    recommended_resolution: str | None = None
    owner_decision: str | None = None
    reviewer: str | None = None
    reviewed_at: str | None = None
    notes: str | None = None
    resulting_mapping_id: str | None = None
    status: str
    created_at: str
    updated_at: str
