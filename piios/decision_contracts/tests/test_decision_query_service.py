from __future__ import annotations

from piios.decision_contracts.application.decision_capture_service import (
    DecisionCaptureRequest,
    DecisionCaptureService,
    DecisionType,
)
from piios.decision_contracts.application.decision_engine import RecommendationDecisionEngine
from piios.decision_contracts.application.decision_query_service import DecisionQueryService
from piios.decision_contracts.application.diagnostics_service import RecommendationDiagnosticsService
from piios.decision_contracts.application.recommendation_reconstruction_service import RecommendationReconstructionService
from piios.decision_contracts.application.recommendation_replay_verification_service import RecommendationReplayVerificationService
from piios.decision_contracts.infrastructure.in_memory_repositories import (
    InMemoryInvestmentDecisionRepository,
    InMemoryRecommendationProposalRepository,
    InMemoryRecommendationProposalVersionRepository,
    InMemoryRecommendationReasonRepository,
    InMemoryRecommendationSnapshotRepository,
    InMemoryRecommendationTraceRepository,
)
from piios.decision_contracts.tests.functional_acceptance_helpers import build_input, scenario_catalog
from piios.thesis.infrastructure.in_memory_claim_evidence_repositories import (
    InMemoryEvidenceItemRepository,
    InMemoryThesisClaimRepository,
)
from piios.thesis.infrastructure.in_memory_repositories import InMemoryThesisVersionRepository


def _bundle():
    proposal_repo = InMemoryRecommendationProposalRepository()
    version_repo = InMemoryRecommendationProposalVersionRepository()
    snapshot_repo = InMemoryRecommendationSnapshotRepository()
    reason_repo = InMemoryRecommendationReasonRepository()
    trace_repo = InMemoryRecommendationTraceRepository()
    decision_repo = InMemoryInvestmentDecisionRepository()

    engine = RecommendationDecisionEngine(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        snapshot_repository=snapshot_repo,
        reason_repository=reason_repo,
        trace_repository=trace_repo,
    )

    data = build_input(scenario_catalog()["A_strong_positive"])
    generated = engine.generate_recommendation(data)

    thesis_version_repo = InMemoryThesisVersionRepository()
    claim_repo = InMemoryThesisClaimRepository()
    evidence_repo = InMemoryEvidenceItemRepository()
    for claim in data.claims:
        claim_repo.create(claim)
    for evidence in data.evidence_items:
        evidence_repo.create(evidence)

    reconstruction = RecommendationReconstructionService(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        snapshot_repository=snapshot_repo,
        trace_repository=trace_repo,
        reason_repository=reason_repo,
        decision_repository=decision_repo,
    )
    replay = RecommendationReplayVerificationService(reconstruction)
    diagnostics = RecommendationDiagnosticsService(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        snapshot_repository=snapshot_repo,
        trace_repository=trace_repo,
        decision_repository=decision_repo,
        reconstruction_service=reconstruction,
        replay_verification_service=replay,
        thesis_version_repository=thesis_version_repo,
        thesis_claim_repository=claim_repo,
        evidence_item_repository=evidence_repo,
    )

    capture = DecisionCaptureService(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        decision_repository=decision_repo,
    )
    query = DecisionQueryService(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        decision_repository=decision_repo,
        diagnostics_service=diagnostics,
    )
    return generated, capture, query


def test_query_contracts_cover_required_application_capabilities() -> None:
    generated, capture, query = _bundle()
    proposal_id = generated.proposal.proposal_id
    proposal_version_id = generated.proposal_version.proposal_version_id

    capture.capture(
        DecisionCaptureRequest(
            proposal_version_id=proposal_version_id,
            decision_type=DecisionType.ACCEPT,
            reviewer="rm_001",
            reason_code="APPROVED",
            client_request_id="q-1",
        )
    )
    capture.capture(
        DecisionCaptureRequest(
            proposal_version_id=proposal_version_id,
            decision_type=DecisionType.REQUEST_RESEARCH,
            reviewer="rm_001",
            client_request_id="q-2",
        )
    )

    proposal = query.get_recommendation_proposal_detail(proposal_id)
    version = query.get_proposal_version_detail(proposal_version_id)
    decisions = query.list_decisions_for_proposal_version(proposal_version_id)
    latest = query.get_latest_decision_for_proposal_version(proposal_version_id)
    traceability = query.get_traceability_diagnostic(proposal_version_id)
    confidence = query.get_confidence_diagnostic(proposal_version_id)
    lineage = query.get_decision_lineage_diagnostic(decisions[-1].decision_id)
    backlog = query.get_governance_review_backlog(proposal_version_id)

    assert proposal.proposal_id == proposal_id
    assert version.proposal_version_id == proposal_version_id
    assert len(decisions) == 2
    assert latest is not None and latest.decision_id == decisions[-1].decision_id
    assert traceability.proposal_version_id == proposal_version_id
    assert confidence.proposal_version_id == proposal_version_id
    assert lineage.decision_id == decisions[-1].decision_id
    assert any(row.reason_code == "REQUEST_RESEARCH_DECISION" for row in backlog.items)


def test_query_decision_meaning_distinguishes_request_research_from_deferred() -> None:
    generated, capture, query = _bundle()
    proposal_version_id = generated.proposal_version.proposal_version_id

    deferred = capture.capture(
        DecisionCaptureRequest(
            proposal_version_id=proposal_version_id,
            decision_type=DecisionType.DEFERRED,
            reviewer="rm_001",
            reason_code="WAIT_FOR_EVENT",
            client_request_id="q-deferred",
        )
    )
    research = capture.capture(
        DecisionCaptureRequest(
            proposal_version_id=proposal_version_id,
            decision_type=DecisionType.REQUEST_RESEARCH,
            reviewer="rm_001",
            client_request_id="q-research",
        )
    )

    deferred_detail = query.get_latest_decision_for_proposal_version(proposal_version_id)
    research_lineage = query.get_decision_lineage_diagnostic(research.decision_id)
    deferred_lineage = query.get_decision_lineage_diagnostic(deferred.decision_id)

    assert deferred_detail is not None
    assert deferred_lineage.decision_meaning == "DEFERRED"
    assert research_lineage.decision_meaning == "REQUEST_RESEARCH"
