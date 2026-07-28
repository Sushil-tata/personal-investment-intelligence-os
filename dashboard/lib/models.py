"""Typed, frontend-side mirrors of backend Pydantic response models.

These dataclasses exist purely so pages can work with named attributes
instead of raw dicts, and so a missing/renamed backend field fails loudly
(via TypeError on construction) instead of silently rendering blank.

Field names and types are kept in lockstep with the backend schemas under
``backend/piios_backend/schemas/*.py`` as read on the ``frontend`` branch.
This file must never add fields the backend does not actually return —
if a screen needs a field that isn't here, that's an API gap, not a
reason to invent one (see dashboard/API_GAPS.md).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Holding:
    holding_id: str
    ticker: str
    name: str
    quantity: float
    market_value: float
    bucket: str | None
    geography: str
    currency: str
    asset_class: str
    sector: str
    theme: str


@dataclass
class WatchlistIdea:
    watchlist_id: str
    ticker: str
    note: str
    bucket: str | None


@dataclass
class PortfolioSnapshot:
    snapshot_id: str
    owner: str
    total_value: float
    holdings: list[Holding]


@dataclass
class DriftItem:
    dimension: str
    key: str
    target_percentage: float
    actual_percentage: float
    drift_amount: float
    drift_percentage: float
    severity: str
    recommended_action: str
    advisory_only: bool


@dataclass
class PortfolioDriftResponse:
    generated_at: str
    items: list[DriftItem]


@dataclass
class PortfolioTargetsResponse:
    targets: dict
    thresholds: dict


@dataclass
class FamilyPortfolioMember:
    member_id: str
    member_name: str
    relation: str
    base_currency: str


@dataclass
class FamilyPortfolioResponse:
    households: list[FamilyPortfolioMember]


@dataclass
class NetWorthItem:
    category: str
    value: float


@dataclass
class NetWorthResponse:
    owner: str
    total_assets: float
    total_liabilities: float
    net_worth: float
    breakdown: list[NetWorthItem]


@dataclass
class AllocationItem:
    dimension: str
    key: str
    market_value: float
    percentage: float


@dataclass
class AllocationResponse:
    total_value: float
    items: list[AllocationItem]


@dataclass
class CurrencyExposureItem:
    currency: str
    market_value: float
    percentage: float


@dataclass
class CurrencyExposureResponse:
    total_value: float
    items: list[CurrencyExposureItem]


@dataclass
class IPSConstraint:
    constraint_id: str
    name: str
    rule_type: str
    threshold_value: float
    severity: str
    enabled: bool


@dataclass
class IPSConstraintResponse:
    constraints: list[IPSConstraint]


@dataclass
class InstrumentMasterItem:
    instrument_id: str
    ticker: str
    name: str
    asset_class: str
    currency: str
    exchange: str
    data_source: str


@dataclass
class InstrumentMasterResponse:
    instruments: list[InstrumentMasterItem]


@dataclass
class DataTrustSourceItem:
    source_id: str
    source_name: str
    trust_tier: str
    score: float
    freshness_sla_hours: int


@dataclass
class DataTrustHierarchyResponse:
    hierarchy: list[DataTrustSourceItem]


@dataclass
class Recommendation:
    recommendation_id: str
    ticker: str
    thesis_id: str | None
    bucket: str | None
    portfolio_bucket: str
    bull_case: str
    bear_case: str
    why_now: str
    why_not_now: str
    thesis_invalidation_trigger: str
    position_size_suggestion: str
    time_horizon: str
    confidence_score: float
    portfolio_fit_score: float
    data_freshness_timestamp: str
    source_documents: list[str]
    source_links: list[str]
    rationale: str
    data_source: str
    model_version: str
    status: str
    created_at: str
    updated_at: str
    approved_by: str | None
    advisory_only: bool


@dataclass
class RecommendationQueueResponse:
    items: list[Recommendation]


@dataclass
class TopRecommendation:
    ticker: str
    sector: str
    score: float
    daily_pct: float
    weekly_pct: float
    close: float
    volume_ratio: float
    recommended_action: str


@dataclass
class TacticalSignal:
    signal_id: str
    ticker: str
    bucket: str | None
    status: str
    entry_zone: str
    invalidation: str
    target: str
    advisory_only: bool


@dataclass
class JournalEntry:
    entry_id: str
    ticker: str
    notes: str
    outcome: str
    bucket: str | None
    created_at: str


@dataclass
class InvestmentThesis:
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
    source_documents: list[str]
    confidence_score: float
    status: str
    created_at: str
    updated_at: str


@dataclass
class ResearchDocumentResponse:
    title: str
    source: str
    timestamp: str
    url: str
    credibility_score: float
    extracted_entities: list[str]
    related_ticker_theme: str


@dataclass
class ResearchFeedResponse:
    items: list[ResearchDocumentResponse]


@dataclass
class ResolutionIssueResponse:
    issue_id: str
    source_record_type: str
    source_record_id: str
    reason: str
    candidates: list[dict]
    recommended_resolution: str | None
    owner_decision: str | None
    reviewer: str | None
    reviewed_at: str | None
    notes: str | None
    resulting_mapping_id: str | None
    status: str
    created_at: str


@dataclass
class ShadowIdentityCheckItem:
    source_type: str
    source_id: str
    legacy_subject: str
    resolution_status: str
    candidate_count: int
    warnings: list[str] = field(default_factory=list)


@dataclass
class ShadowIdentityDiagnosticsResponse:
    enabled: bool
    checked_records: int
    unresolved_records: int
    items: list[ShadowIdentityCheckItem]


@dataclass
class HealthResponse:
    status: str
    product: str


# --- Wave 2B decision-contracts models -------------------------------------
# Mirrors backend/piios_backend/schemas/decision_contracts.py exactly, per
# piios/docs/WAVE2B_M5_FRONTEND_CONTRACT.md. Field names/types here must
# never drift from that contract without a corresponding backend change.

DIAGNOSTIC_STATUSES = ("PASS", "FAIL", "WARNING", "UNAVAILABLE", "NOT_APPLICABLE")
DIAGNOSTIC_SEVERITIES = ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")
DECISION_TYPES = ("ACCEPT", "REJECT", "MODIFIED", "OVERRIDDEN", "DEFERRED", "REQUEST_RESEARCH")


@dataclass
class RecommendationProposalDetail:
    proposal_id: str
    target_type: str
    target_key: str
    scope: str
    status: str
    created_at: str
    updated_at: str
    advisory_only: bool = True


@dataclass
class RecommendationProposalVersionDetail:
    proposal_version_id: str
    proposal_id: str
    version_number: int
    status: str
    created_at: str
    snapshot_id: str
    action: str
    authoritative_confidence: float
    priority_level: str
    priority_score: float
    required_human_review: bool
    action_note: str | None = None
    action_min_weight: float | None = None
    action_max_weight: float | None = None
    supersedes_version_id: str | None = None
    advisory_only: bool = True


@dataclass
class DecisionDetail:
    decision_id: str
    proposal_version_id: str
    state: str
    decision_meaning: str
    reason_code: str
    decided_at: str
    reason_text: str | None = None
    decided_by: str | None = None
    preferred_alternative_target_key: str | None = None
    modified_action: str | None = None
    modified_action_note: str | None = None
    modified_action_min_weight: float | None = None
    modified_action_max_weight: float | None = None
    modified_position_min_weight: float | None = None
    modified_position_max_weight: float | None = None
    advisory_only: bool = True


@dataclass
class DiagnosticCheck:
    code: str
    status: str
    severity: str
    message: str
    related_entity_type: str
    related_entity_id: str | None
    remediation_hint: str | None


@dataclass
class TraceabilityDiagnostic:
    proposal_version_id: str
    overall_status: str
    checks: list[DiagnosticCheck]
    diagnostic_codes: list[str]
    severity: str
    generated_at: str
    proposal_id: str | None = None
    advisory_only: bool = True


@dataclass
class ConfidenceComponent:
    name: str
    value: float | None
    status: str
    source: str
    explanation: str


@dataclass
class ConfidenceDiagnostic:
    proposal_version_id: str
    authoritative_confidence: float | None
    components: list[ConfidenceComponent]
    limitations: list[str]
    generated_at: str
    advisory_only: bool = True


@dataclass
class DecisionLineageDiagnostic:
    decision_id: str
    proposal_version_id: str
    decision_state: str
    decision_meaning: str
    overall_status: str
    checks: list[DiagnosticCheck]
    diagnostic_codes: list[str]
    severity: str
    generated_at: str
    proposal_id: str | None = None
    advisory_only: bool = True


@dataclass
class GovernanceReviewItem:
    review_item_id: str
    proposal_version_id: str
    reason_code: str
    severity: str
    status: str
    created_at: str
    source_diagnostic: str
    summary: str
    proposal_id: str | None = None
    decision_id: str | None = None


@dataclass
class GovernanceReviewBacklog:
    proposal_version_id: str
    items: list[GovernanceReviewItem]
    generated_at: str
    advisory_only: bool = True


# --- Wave 3 recommendation MVP models --------------------------------------


@dataclass
class PortfolioObservation:
    code: str
    severity: str
    detail: str


@dataclass
class RecommendationScoreComponent:
    name: str
    value: float | None
    weight: float
    status: str
    explanation: str


@dataclass
class RecommendationEvidence:
    code: str
    detail: str
    source: str


@dataclass
class RecommendationLimitation:
    code: str
    detail: str
    severity: str


@dataclass
class AllocationRecommendation:
    action: str
    ticker: str
    instrument_name: str
    portfolio_role: str
    current_value: float
    current_weight: float
    proposed_allocation: float
    proposed_total_value: float
    post_weight: float
    score: float
    confidence: float
    market_data_provider: str
    market_data_mode: str
    market_data_as_of: str | None
    is_stale: bool
    fallback_reason: str | None
    seeded_input: bool
    rationale: str
    diversification_contribution: str
    risks: list[str]
    unavailable_inputs: list[str]
    conditions_to_change: list[str]
    components: list[RecommendationScoreComponent]
    evidence: list[RecommendationEvidence]


@dataclass
class PortfolioRecommendationResponse:
    recommendation_id: str
    status: str
    as_of_timestamp: str
    market_data_provider: str
    market_data_mode: str
    input_freshness: str
    investable_amount: float
    allocation_total: float
    allocation_difference: float
    overall_confidence: float
    advisory_only: bool
    portfolio_observations: list[PortfolioObservation]
    recommendations: list[AllocationRecommendation]
    assumptions: list[str]
    limitations: list[RecommendationLimitation]
