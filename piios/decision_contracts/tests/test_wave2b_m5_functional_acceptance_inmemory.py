from __future__ import annotations

from dataclasses import replace
import json

from piios.decision_contracts.application.decision_capture_service import (
    DecisionCaptureRequest,
    DecisionCaptureService,
    DecisionType,
)
from piios.decision_contracts.application.decision_engine import RecommendationDecisionEngine
from piios.decision_contracts.application.decision_query_service import DecisionQueryService
from piios.decision_contracts.application.diagnostics_service import (
    DiagnosticStatus,
    RecommendationDiagnosticsService,
)
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
from piios.thesis.domain.entities import ThesisRoot, ThesisVersion
from piios.thesis.domain.enums import ThesisStatus
from piios.thesis.infrastructure.in_memory_claim_evidence_repositories import (
    InMemoryEvidenceItemRepository,
    InMemoryThesisClaimRepository,
)
from piios.thesis.infrastructure.in_memory_repositories import InMemoryThesisRootRepository, InMemoryThesisVersionRepository


def _m5_bundle(scenario_key: str):
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

    data = build_input(scenario_catalog()[scenario_key])
    generated = engine.generate_recommendation(data)

    thesis_root_repo = InMemoryThesisRootRepository()
    thesis_version_repo = InMemoryThesisVersionRepository()
    claim_repo = InMemoryThesisClaimRepository()
    evidence_repo = InMemoryEvidenceItemRepository()

    thesis_id = data.thesis_version_id.split(":v")[0]
    thesis_root_repo.create(
        ThesisRoot(
            thesis_id=thesis_id,
            ticker=generated.proposal.target_key,
            lifecycle_status=ThesisStatus.RESEARCHED,
            current_version_number=1,
            created_at=data.generated_at,
            updated_at=data.generated_at,
        )
    )
    thesis_version_repo.create(
        ThesisVersion(
            version_id=data.thesis_version_id,
            thesis_id=thesis_id,
            version_number=1,
            asset_name=generated.proposal.target_key,
            theme="AI",
            bucket="Growth",
            thesis="Base thesis",
            bull_case="Bull",
            bear_case="Bear",
            why_now="Now",
            why_not_now="Not now",
            invalidation_trigger="Invalidation",
            valuation_notes="Valuation",
            expected_holding_period="2-5 years",
            source_documents=("doc1",),
            confidence_score=70.0,
            status=ThesisStatus.RESEARCHED,
            created_at=data.generated_at,
        )
    )
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

    return {
        "data": data,
        "generated": generated,
        "snapshot_repo": snapshot_repo,
        "trace_repo": trace_repo,
        "decision_repo": decision_repo,
        "capture": capture,
        "query": query,
        "diagnostics": diagnostics,
    }


def test_m5_inmemory_clean_acceptance_end_to_end() -> None:
    bundle = _m5_bundle("A_strong_positive")
    proposal_version_id = bundle["generated"].proposal_version.proposal_version_id

    captured = bundle["capture"].capture(
        DecisionCaptureRequest(
            proposal_version_id=proposal_version_id,
            decision_type=DecisionType.ACCEPT,
            reviewer="rm_001",
            reason_code="APPROVED",
            client_request_id="accept-1",
        )
    )

    proposal = bundle["query"].get_recommendation_proposal_detail(bundle["generated"].proposal.proposal_id)
    version = bundle["query"].get_proposal_version_detail(proposal_version_id)
    decisions = bundle["query"].list_decisions_for_proposal_version(proposal_version_id)
    traceability = bundle["query"].get_traceability_diagnostic(proposal_version_id)
    confidence = bundle["query"].get_confidence_diagnostic(proposal_version_id)
    lineage = bundle["query"].get_decision_lineage_diagnostic(captured.decision_id)
    backlog = bundle["query"].get_governance_review_backlog(proposal_version_id)

    assert proposal.proposal_id == bundle["generated"].proposal.proposal_id
    assert version.proposal_version_id == proposal_version_id
    assert len(decisions) == 1
    assert decisions[0].decision_id == captured.decision_id
    assert traceability.overall_status == DiagnosticStatus.PASS
    assert confidence.authoritative_confidence == bundle["generated"].proposal_version.confidence_breakdown.overall_confidence
    assert lineage.decision_state == "ACCEPTED"
    assert all(row.severity.value != "CRITICAL" for row in backlog.items)


def test_m5_inmemory_modified_decision_keeps_proposal_immutable_and_backlog_item() -> None:
    bundle = _m5_bundle("A_strong_positive")
    proposal_version_id = bundle["generated"].proposal_version.proposal_version_id
    original_action = bundle["generated"].proposal_version.action_proposal.action

    captured = bundle["capture"].capture(
        DecisionCaptureRequest(
            proposal_version_id=proposal_version_id,
            decision_type=DecisionType.MODIFIED,
            reviewer="rm_001",
            reason_code="ADJUST_SIZE",
            modified_action=original_action,
            modified_position_min_weight=0.01,
            modified_position_max_weight=0.03,
            client_request_id="modified-1",
        )
    )

    version = bundle["query"].get_proposal_version_detail(proposal_version_id)
    lineage = bundle["query"].get_decision_lineage_diagnostic(captured.decision_id)
    backlog = bundle["query"].get_governance_review_backlog(proposal_version_id)

    assert version.action == original_action.value
    assert lineage.decision_state == "MODIFIED"
    assert any(row.reason_code == "MODIFIED_RECOMMENDATION" for row in backlog.items)


def test_m5_inmemory_override_visible_in_lineage_and_backlog() -> None:
    bundle = _m5_bundle("A_strong_positive")
    proposal_version_id = bundle["generated"].proposal_version.proposal_version_id

    captured = bundle["capture"].capture(
        DecisionCaptureRequest(
            proposal_version_id=proposal_version_id,
            decision_type=DecisionType.OVERRIDDEN,
            reviewer="rm_001",
            reason_code="ALTERNATIVE_BETTER",
            preferred_alternative_target_key="AMD",
            client_request_id="override-1",
        )
    )

    lineage = bundle["query"].get_decision_lineage_diagnostic(captured.decision_id)
    backlog = bundle["query"].get_governance_review_backlog(proposal_version_id)

    assert lineage.decision_state == "OVERRIDDEN"
    assert any(row.reason_code == "OVERRIDDEN_RECOMMENDATION" for row in backlog.items)


def test_m5_inmemory_deferred_decision_classified_as_unresolved_review() -> None:
    bundle = _m5_bundle("A_strong_positive")
    proposal_version_id = bundle["generated"].proposal_version.proposal_version_id

    captured = bundle["capture"].capture(
        DecisionCaptureRequest(
            proposal_version_id=proposal_version_id,
            decision_type=DecisionType.DEFERRED,
            reviewer="rm_001",
            reason_code="WAIT_FOR_EVENT",
            client_request_id="deferred-1",
        )
    )

    lineage = bundle["query"].get_decision_lineage_diagnostic(captured.decision_id)
    backlog = bundle["query"].get_governance_review_backlog(proposal_version_id)

    assert lineage.decision_state == "DEFERRED"
    assert lineage.decision_meaning == "DEFERRED"
    assert any(row.reason_code == "DEFERRED_DECISION" for row in backlog.items)


def test_m5_inmemory_request_research_representation_distinct_from_regular_deferral() -> None:
    bundle = _m5_bundle("A_strong_positive")
    proposal_version_id = bundle["generated"].proposal_version.proposal_version_id

    captured = bundle["capture"].capture(
        DecisionCaptureRequest(
            proposal_version_id=proposal_version_id,
            decision_type=DecisionType.REQUEST_RESEARCH,
            reviewer="rm_001",
            client_request_id="research-1",
        )
    )

    lineage = bundle["query"].get_decision_lineage_diagnostic(captured.decision_id)
    backlog = bundle["query"].get_governance_review_backlog(proposal_version_id)

    assert lineage.decision_state == "DEFERRED"
    assert lineage.decision_meaning == "REQUEST_RESEARCH"
    assert any(row.reason_code == "REQUEST_RESEARCH_DECISION" for row in backlog.items)


def test_m5_inmemory_traceability_failure_creates_backlog_and_keeps_records_immutable() -> None:
    bundle = _m5_bundle("A_strong_positive")
    proposal_version_id = bundle["generated"].proposal_version.proposal_version_id
    snapshot_repo = bundle["snapshot_repo"]

    before_count = len(bundle["decision_repo"].list_for_proposal_version(proposal_version_id))
    snapshot_repo._by_snapshot_id.pop(bundle["generated"].input_snapshot.snapshot_id, None)
    snapshot_repo._by_version_id.pop(proposal_version_id, None)

    traceability = bundle["query"].get_traceability_diagnostic(proposal_version_id)
    backlog = bundle["query"].get_governance_review_backlog(proposal_version_id)
    after_count = len(bundle["decision_repo"].list_for_proposal_version(proposal_version_id))

    assert traceability.overall_status == DiagnosticStatus.FAIL
    assert any(row.reason_code == "MISSING_SNAPSHOT" for row in backlog.items)
    assert after_count == before_count


def test_m5_inmemory_replay_mismatch_creates_backlog_and_keeps_decision_intact() -> None:
    bundle = _m5_bundle("A_strong_positive")
    proposal_version_id = bundle["generated"].proposal_version.proposal_version_id

    captured = bundle["capture"].capture(
        DecisionCaptureRequest(
            proposal_version_id=proposal_version_id,
            decision_type=DecisionType.ACCEPT,
            reviewer="rm_001",
            reason_code="APPROVED",
            client_request_id="accept-replay",
        )
    )

    row = bundle["snapshot_repo"]._by_snapshot_id[bundle["generated"].input_snapshot.snapshot_id]
    payload = json.loads(row.canonical_payload_json)
    payload["thesis_health"]["supporting_strength"] = 0.01
    payload["thesis_health"]["contradictory_strength"] = 0.99
    tampered = replace(
        bundle["generated"].input_snapshot,
        canonical_payload_json=json.dumps(payload, sort_keys=True, separators=(",", ":")),
    )
    bundle["snapshot_repo"]._by_snapshot_id[bundle["generated"].input_snapshot.snapshot_id] = tampered
    bundle["snapshot_repo"]._by_version_id[proposal_version_id] = tampered

    traceability = bundle["query"].get_traceability_diagnostic(proposal_version_id)
    backlog = bundle["query"].get_governance_review_backlog(proposal_version_id)
    lineage = bundle["query"].get_decision_lineage_diagnostic(captured.decision_id)

    assert any(row.code == "REPLAY_VERIFICATION_FAIL" for row in traceability.checks)
    assert any(row.reason_code == "REPLAY_MISMATCH" for row in backlog.items)
    assert lineage.decision_id == captured.decision_id
