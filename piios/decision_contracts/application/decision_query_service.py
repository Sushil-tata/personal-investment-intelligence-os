from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from piios.decision_contracts.application.diagnostics_service import (
    ConfidenceDiagnostic,
    DecisionLineageDiagnostic,
    GovernanceReviewBacklog,
    RecommendationDiagnosticsService,
    TraceabilityDiagnostic,
)
from piios.decision_contracts.domain.decision import InvestmentDecision
from piios.decision_contracts.domain.proposal import RecommendationProposal, RecommendationProposalVersion
from piios.decision_contracts.infrastructure.repository_protocols import (
    InvestmentDecisionRepositoryProtocol,
    RecommendationProposalRepositoryProtocol,
    RecommendationProposalVersionRepositoryProtocol,
)


class DecisionQueryError(Exception):
    pass


class ProposalNotFoundError(DecisionQueryError):
    pass


class ProposalVersionNotFoundError(DecisionQueryError):
    pass


class DecisionNotFoundError(DecisionQueryError):
    pass


@dataclass(frozen=True)
class RecommendationProposalDetail:
    proposal_id: str
    target_type: str
    target_key: str
    scope: str
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class RecommendationProposalVersionDetail:
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
    authoritative_confidence: float
    priority_level: str
    priority_score: float
    required_human_review: bool
    supersedes_version_id: str | None


@dataclass(frozen=True)
class DecisionDetail:
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


class DecisionQueryService:
    def __init__(
        self,
        proposal_repository: RecommendationProposalRepositoryProtocol,
        version_repository: RecommendationProposalVersionRepositoryProtocol,
        decision_repository: InvestmentDecisionRepositoryProtocol,
        diagnostics_service: RecommendationDiagnosticsService,
    ) -> None:
        self._proposal_repository = proposal_repository
        self._version_repository = version_repository
        self._decision_repository = decision_repository
        self._diagnostics_service = diagnostics_service

    def get_recommendation_proposal_detail(self, proposal_id: str) -> RecommendationProposalDetail:
        proposal = self._proposal_repository.get(proposal_id)
        if proposal is None:
            raise ProposalNotFoundError(f"proposal_id not found: {proposal_id}")
        return _proposal_detail(proposal)

    def get_proposal_version_detail(self, proposal_version_id: str) -> RecommendationProposalVersionDetail:
        version = self._version_repository.get(proposal_version_id)
        if version is None:
            raise ProposalVersionNotFoundError(f"proposal_version_id not found: {proposal_version_id}")

        _ = self.get_recommendation_proposal_detail(version.proposal_id)
        return _version_detail(version)

    def list_decisions_for_proposal_version(self, proposal_version_id: str) -> tuple[DecisionDetail, ...]:
        _ = self.get_proposal_version_detail(proposal_version_id)
        rows = self._decision_repository.list_for_proposal_version(proposal_version_id)
        return tuple(_decision_detail(row) for row in rows)

    def get_latest_decision_for_proposal_version(self, proposal_version_id: str) -> DecisionDetail | None:
        _ = self.get_proposal_version_detail(proposal_version_id)
        row = self._decision_repository.get_latest_for_proposal_version(proposal_version_id)
        if row is None:
            return None
        return _decision_detail(row)

    def get_traceability_diagnostic(self, proposal_version_id: str) -> TraceabilityDiagnostic:
        return self._diagnostics_service.diagnose_traceability(proposal_version_id)

    def get_confidence_diagnostic(self, proposal_version_id: str) -> ConfidenceDiagnostic:
        return self._diagnostics_service.diagnose_confidence(proposal_version_id)

    def get_decision_lineage_diagnostic(self, decision_id: str) -> DecisionLineageDiagnostic:
        diag = self._diagnostics_service.diagnose_decision(decision_id)
        if diag.decision_state == "<unknown>":
            raise DecisionNotFoundError(f"decision_id not found: {decision_id}")
        return diag

    def get_governance_review_backlog(self, proposal_version_id: str) -> GovernanceReviewBacklog:
        _ = self.get_proposal_version_detail(proposal_version_id)
        return self._diagnostics_service.build_governance_review_backlog(proposal_version_id)


def _proposal_detail(proposal: RecommendationProposal) -> RecommendationProposalDetail:
    return RecommendationProposalDetail(
        proposal_id=proposal.proposal_id,
        target_type=proposal.target_type,
        target_key=proposal.target_key,
        scope=proposal.scope,
        status=proposal.status.value,
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
    )


def _version_detail(version: RecommendationProposalVersion) -> RecommendationProposalVersionDetail:
    return RecommendationProposalVersionDetail(
        proposal_version_id=version.proposal_version_id,
        proposal_id=version.proposal_id,
        version_number=version.version_number,
        status=version.status.value,
        created_at=version.created_at,
        snapshot_id=version.snapshot_id,
        action=version.action_proposal.action.value,
        action_note=version.action_proposal.note,
        action_min_weight=(
            version.action_proposal.position_size_range.min_weight
            if version.action_proposal.position_size_range is not None
            else None
        ),
        action_max_weight=(
            version.action_proposal.position_size_range.max_weight
            if version.action_proposal.position_size_range is not None
            else None
        ),
        authoritative_confidence=version.confidence_breakdown.overall_confidence,
        priority_level=version.priority.level.value,
        priority_score=version.priority.score,
        required_human_review=version.required_human_review,
        supersedes_version_id=version.supersedes_version_id,
    )


def _decision_detail(decision: InvestmentDecision) -> DecisionDetail:
    return DecisionDetail(
        decision_id=decision.decision_id,
        proposal_version_id=decision.proposal_version_id,
        state=decision.state.value,
        decision_meaning=(
            "REQUEST_RESEARCH"
            if decision.state.value == "DEFERRED" and decision.reason_code.strip().upper() == "REQUEST_RESEARCH"
            else decision.state.value
        ),
        reason_code=decision.reason_code,
        reason_text=decision.reason_text,
        decided_by=decision.decided_by,
        decided_at=decision.decided_at,
        preferred_alternative_target_key=decision.preferred_alternative_target_key,
        modified_action=decision.modified_action.action.value if decision.modified_action is not None else None,
        modified_action_note=decision.modified_action.note if decision.modified_action is not None else None,
        modified_action_min_weight=(
            decision.modified_action.position_size_range.min_weight
            if decision.modified_action is not None and decision.modified_action.position_size_range is not None
            else None
        ),
        modified_action_max_weight=(
            decision.modified_action.position_size_range.max_weight
            if decision.modified_action is not None and decision.modified_action.position_size_range is not None
            else None
        ),
        modified_position_min_weight=(
            decision.modified_position_size.min_weight
            if decision.modified_position_size is not None
            else None
        ),
        modified_position_max_weight=(
            decision.modified_position_size.max_weight
            if decision.modified_position_size is not None
            else None
        ),
    )
