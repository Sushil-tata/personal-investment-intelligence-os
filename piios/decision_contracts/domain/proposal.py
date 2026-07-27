from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from piios.decision_contracts.domain.enums import ProposalStatus, ReasonType
from piios.decision_contracts.domain.value_objects import (
    ActionProposal,
    ConfidenceBreakdown,
    ExecutionConsideration,
    MonitoringTrigger,
    RecommendationPriority,
    ReasonWeight,
    RiskWarning,
)


@dataclass(frozen=True)
class RecommendationProposal:
    proposal_id: str
    target_type: str
    target_key: str
    scope: str
    status: ProposalStatus
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.proposal_id.strip():
            raise ValueError("proposal_id must not be empty")
        if not self.target_type.strip():
            raise ValueError("target_type must not be empty")
        if not self.target_key.strip():
            raise ValueError("target_key must not be empty")
        if not self.scope.strip():
            raise ValueError("scope must not be empty")


@dataclass(frozen=True)
class RecommendationProposalVersion:
    proposal_version_id: str
    proposal_id: str
    version_number: int
    status: ProposalStatus
    created_at: datetime
    snapshot_id: str
    action_proposal: ActionProposal
    confidence_breakdown: ConfidenceBreakdown
    priority: RecommendationPriority
    required_human_review: bool
    supersedes_version_id: str | None = None

    def __post_init__(self) -> None:
        if not self.proposal_version_id.strip():
            raise ValueError("proposal_version_id must not be empty")
        if not self.proposal_id.strip():
            raise ValueError("proposal_id must not be empty")
        if self.version_number <= 0:
            raise ValueError("version_number must be > 0")
        if not self.snapshot_id.strip():
            raise ValueError("snapshot_id must not be empty")
        if self.supersedes_version_id is not None and not self.supersedes_version_id.strip():
            raise ValueError("supersedes_version_id cannot be blank")


@dataclass(frozen=True)
class RecommendationInputSnapshot:
    snapshot_id: str
    proposal_version_id: str
    captured_at: datetime
    canonical_payload_json: str
    input_hash: str

    def __post_init__(self) -> None:
        if not self.snapshot_id.strip():
            raise ValueError("snapshot_id must not be empty")
        if not self.proposal_version_id.strip():
            raise ValueError("proposal_version_id must not be empty")
        if not self.canonical_payload_json.strip():
            raise ValueError("canonical_payload_json must not be empty")
        if not self.input_hash.strip():
            raise ValueError("input_hash must not be empty")


@dataclass(frozen=True)
class RecommendationReason:
    reason_id: str
    proposal_version_id: str
    rank: int
    reason_type: ReasonType
    weight: ReasonWeight
    reason_code: str
    detail_json: str

    def __post_init__(self) -> None:
        if not self.reason_id.strip():
            raise ValueError("reason_id must not be empty")
        if not self.proposal_version_id.strip():
            raise ValueError("proposal_version_id must not be empty")
        if self.rank <= 0:
            raise ValueError("rank must be > 0")
        if not self.reason_code.strip():
            raise ValueError("reason_code must not be empty")
        if not self.detail_json.strip():
            raise ValueError("detail_json must not be empty")


@dataclass(frozen=True)
class RecommendationClaimLink:
    claim_link_id: str
    proposal_version_id: str
    claim_id: str
    contribution_weight: ReasonWeight
    role: str

    def __post_init__(self) -> None:
        if not self.claim_link_id.strip():
            raise ValueError("claim_link_id must not be empty")
        if not self.proposal_version_id.strip():
            raise ValueError("proposal_version_id must not be empty")
        if not self.claim_id.strip():
            raise ValueError("claim_id must not be empty")
        if not self.role.strip():
            raise ValueError("role must not be empty")


@dataclass(frozen=True)
class RecommendationEvidenceLink:
    evidence_link_id: str
    proposal_version_id: str
    evidence_id: str
    interpretation_id: str | None
    freshness_days: int
    quality_score: float
    conflict_flag: bool

    def __post_init__(self) -> None:
        if not self.evidence_link_id.strip():
            raise ValueError("evidence_link_id must not be empty")
        if not self.proposal_version_id.strip():
            raise ValueError("proposal_version_id must not be empty")
        if not self.evidence_id.strip():
            raise ValueError("evidence_id must not be empty")
        if self.interpretation_id is not None and not self.interpretation_id.strip():
            raise ValueError("interpretation_id cannot be blank")
        if self.freshness_days < 0:
            raise ValueError("freshness_days must be >= 0")
        if self.quality_score < 0.0 or self.quality_score > 1.0:
            raise ValueError("quality_score must be within [0.0, 1.0]")


@dataclass(frozen=True)
class RecommendationRiskWarning:
    warning_id: str
    proposal_version_id: str
    warning: RiskWarning

    def __post_init__(self) -> None:
        if not self.warning_id.strip():
            raise ValueError("warning_id must not be empty")
        if not self.proposal_version_id.strip():
            raise ValueError("proposal_version_id must not be empty")


@dataclass(frozen=True)
class RecommendationExecutionConsideration:
    consideration_id: str
    proposal_version_id: str
    consideration: ExecutionConsideration

    def __post_init__(self) -> None:
        if not self.consideration_id.strip():
            raise ValueError("consideration_id must not be empty")
        if not self.proposal_version_id.strip():
            raise ValueError("proposal_version_id must not be empty")


@dataclass(frozen=True)
class RecommendationMonitoringTrigger:
    trigger_id: str
    proposal_version_id: str
    trigger: MonitoringTrigger

    def __post_init__(self) -> None:
        if not self.trigger_id.strip():
            raise ValueError("trigger_id must not be empty")
        if not self.proposal_version_id.strip():
            raise ValueError("proposal_version_id must not be empty")
