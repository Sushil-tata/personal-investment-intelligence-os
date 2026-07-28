from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from piios.decision_contracts.application.decision_capture_service import DecisionType
from piios.decision_contracts.application.diagnostics_service import DiagnosticSeverity, DiagnosticStatus


class DecisionCaptureRequestModel(BaseModel):
    proposal_version_id: str
    decision_type: DecisionType
    reviewer: str
    reason_code: str | None = None
    reason_text: str | None = None
    preferred_alternative_target_key: str | None = None
    modified_action: str | None = None
    modified_action_note: str | None = None
    modified_action_min_weight: float | None = None
    modified_action_max_weight: float | None = None
    modified_position_min_weight: float | None = None
    modified_position_max_weight: float | None = None
    client_request_id: str | None = None


class RecommendationProposalDetailResponse(BaseModel):
    proposal_id: str
    target_type: str
    target_key: str
    scope: str
    status: str
    created_at: datetime
    updated_at: datetime
    advisory_only: bool = True


class RecommendationProposalVersionDetailResponse(BaseModel):
    proposal_version_id: str
    proposal_id: str
    version_number: int
    status: str
    created_at: datetime
    snapshot_id: str
    action: str
    action_note: str | None
    action_min_weight: float | None
    action_max_weight: float | None
    authoritative_confidence: float = Field(ge=0.0, le=1.0)
    priority_level: str
    priority_score: float = Field(ge=0.0, le=1.0)
    required_human_review: bool
    supersedes_version_id: str | None
    advisory_only: bool = True


class DecisionDetailResponse(BaseModel):
    decision_id: str
    proposal_version_id: str
    state: str
    decision_meaning: str
    reason_code: str
    reason_text: str | None
    decided_by: str | None
    decided_at: datetime
    preferred_alternative_target_key: str | None
    modified_action: str | None
    modified_action_note: str | None
    modified_action_min_weight: float | None
    modified_action_max_weight: float | None
    modified_position_min_weight: float | None
    modified_position_max_weight: float | None
    advisory_only: bool = True


class DiagnosticCheckResponse(BaseModel):
    code: str
    status: DiagnosticStatus
    severity: DiagnosticSeverity
    message: str
    related_entity_type: str
    related_entity_id: str | None
    remediation_hint: str | None


class TraceabilityDiagnosticResponse(BaseModel):
    proposal_id: str | None
    proposal_version_id: str
    overall_status: DiagnosticStatus
    checks: tuple[DiagnosticCheckResponse, ...]
    diagnostic_codes: tuple[str, ...]
    severity: DiagnosticSeverity
    generated_at: datetime
    advisory_only: bool = True


class ConfidenceComponentResponse(BaseModel):
    name: str
    value: float | None
    status: DiagnosticStatus
    source: str
    explanation: str


class ConfidenceDiagnosticResponse(BaseModel):
    proposal_version_id: str
    authoritative_confidence: float | None
    components: tuple[ConfidenceComponentResponse, ...]
    limitations: tuple[str, ...]
    generated_at: datetime
    advisory_only: bool = True


class DecisionLineageDiagnosticResponse(BaseModel):
    decision_id: str
    proposal_id: str | None
    proposal_version_id: str
    decision_state: str
    decision_meaning: str
    overall_status: DiagnosticStatus
    checks: tuple[DiagnosticCheckResponse, ...]
    diagnostic_codes: tuple[str, ...]
    severity: DiagnosticSeverity
    generated_at: datetime
    advisory_only: bool = True


class GovernanceReviewItemResponse(BaseModel):
    review_item_id: str
    proposal_id: str | None
    proposal_version_id: str
    decision_id: str | None
    reason_code: str
    severity: DiagnosticSeverity
    status: str
    created_at: datetime
    source_diagnostic: str
    summary: str


class GovernanceReviewBacklogResponse(BaseModel):
    proposal_version_id: str
    items: tuple[GovernanceReviewItemResponse, ...]
    generated_at: datetime
    advisory_only: bool = True
