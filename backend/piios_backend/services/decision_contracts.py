from __future__ import annotations

from sqlmodel import Session

from piios.decision_contracts.application.decision_capture_service import (
    DecisionCaptureRequest,
    DecisionCaptureService,
)
from piios.decision_contracts.application.decision_query_service import DecisionQueryService
from piios.decision_contracts.application.diagnostics_service import RecommendationDiagnosticsService
from piios.decision_contracts.application.recommendation_reconstruction_service import RecommendationReconstructionService
from piios.decision_contracts.application.recommendation_replay_verification_service import RecommendationReplayVerificationService
from piios.decision_contracts.domain.enums import RecommendationAction
from piios.decision_contracts.infrastructure.sqlmodel_repositories import (
    SQLModelInvestmentDecisionRepository,
    SQLModelRecommendationProposalRepository,
    SQLModelRecommendationProposalVersionRepository,
    SQLModelRecommendationReasonRepository,
    SQLModelRecommendationSnapshotRepository,
    SQLModelRecommendationTraceRepository,
)
from piios.thesis.infrastructure.sqlmodel_claim_evidence_repositories import (
    SQLModelEvidenceItemRepository,
    SQLModelThesisClaimRepository,
)
from piios.thesis.infrastructure.sqlmodel_repositories import SQLModelThesisVersionRepository
from piios_backend.schemas.decision_contracts import DecisionCaptureRequestModel


class DecisionContractsService:
    def __init__(self, session: Session) -> None:
        proposal_repository = SQLModelRecommendationProposalRepository(session)
        version_repository = SQLModelRecommendationProposalVersionRepository(session)
        snapshot_repository = SQLModelRecommendationSnapshotRepository(session)
        reason_repository = SQLModelRecommendationReasonRepository(session)
        trace_repository = SQLModelRecommendationTraceRepository(session)
        decision_repository = SQLModelInvestmentDecisionRepository(session)

        reconstruction = RecommendationReconstructionService(
            proposal_repository=proposal_repository,
            version_repository=version_repository,
            snapshot_repository=snapshot_repository,
            trace_repository=trace_repository,
            reason_repository=reason_repository,
            decision_repository=decision_repository,
        )
        replay = RecommendationReplayVerificationService(reconstruction)
        diagnostics = RecommendationDiagnosticsService(
            proposal_repository=proposal_repository,
            version_repository=version_repository,
            snapshot_repository=snapshot_repository,
            trace_repository=trace_repository,
            decision_repository=decision_repository,
            reconstruction_service=reconstruction,
            replay_verification_service=replay,
            thesis_version_repository=SQLModelThesisVersionRepository(session),
            thesis_claim_repository=SQLModelThesisClaimRepository(session),
            evidence_item_repository=SQLModelEvidenceItemRepository(session),
        )

        self.capture_service = DecisionCaptureService(
            proposal_repository=proposal_repository,
            version_repository=version_repository,
            decision_repository=decision_repository,
        )
        self.query_service = DecisionQueryService(
            proposal_repository=proposal_repository,
            version_repository=version_repository,
            decision_repository=decision_repository,
            diagnostics_service=diagnostics,
        )

    def capture_decision(self, request: DecisionCaptureRequestModel):
        return self.capture_service.capture(
            DecisionCaptureRequest(
                proposal_version_id=request.proposal_version_id,
                decision_type=request.decision_type,
                reviewer=request.reviewer,
                reason_code=request.reason_code,
                reason_text=request.reason_text,
                preferred_alternative_target_key=request.preferred_alternative_target_key,
                modified_action=(RecommendationAction(request.modified_action) if request.modified_action else None),
                modified_action_note=request.modified_action_note,
                modified_action_min_weight=request.modified_action_min_weight,
                modified_action_max_weight=request.modified_action_max_weight,
                modified_position_min_weight=request.modified_position_min_weight,
                modified_position_max_weight=request.modified_position_max_weight,
                client_request_id=request.client_request_id,
            )
        )
