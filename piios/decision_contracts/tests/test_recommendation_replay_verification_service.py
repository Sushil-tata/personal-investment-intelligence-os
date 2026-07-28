from __future__ import annotations

import json

from piios.decision_contracts.application.decision_engine import RecommendationDecisionEngine
from piios.decision_contracts.application.recommendation_reconstruction_service import RecommendationReconstructionService
from piios.decision_contracts.application.recommendation_replay_verification_service import (
    RecommendationReplayVerificationService,
)
from piios.decision_contracts.infrastructure.in_memory_repositories import (
    InMemoryInvestmentDecisionRepository,
    InMemoryRecommendationProposalRepository,
    InMemoryRecommendationProposalVersionRepository,
    InMemoryRecommendationReasonRepository,
    InMemoryRecommendationSnapshotRepository,
    InMemoryRecommendationTraceRepository,
)
from piios.decision_contracts.tests.functional_acceptance_helpers import build_input, scenario_catalog


def _bundle() -> tuple[RecommendationDecisionEngine, RecommendationReplayVerificationService, InMemoryRecommendationSnapshotRepository]:
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
    reconstruction = RecommendationReconstructionService(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        snapshot_repository=snapshot_repo,
        trace_repository=trace_repo,
        reason_repository=reason_repo,
        decision_repository=decision_repo,
    )
    replay = RecommendationReplayVerificationService(reconstruction)
    return engine, replay, snapshot_repo


def test_replay_success_passes_when_persisted_artifacts_match() -> None:
    engine, replay, _ = _bundle()
    generated = engine.generate_recommendation(build_input(scenario_catalog()["A_strong_positive"]))

    report = replay.verify_by_proposal_version(generated.proposal_version.proposal_version_id)

    assert report.status == "PASS"
    assert report.persisted_input_hash == generated.input_snapshot.input_hash
    assert report.recomputed_input_hash == generated.input_snapshot.input_hash
    assert report.persisted_trace_id == generated.recommendation_trace.trace_id
    assert report.recomputed_trace_id == generated.recommendation_trace.trace_id
    assert report.differences == tuple()


def test_replay_failure_reports_detailed_differences_when_input_is_tampered() -> None:
    engine, replay, snapshot_repo = _bundle()
    generated = engine.generate_recommendation(build_input(scenario_catalog()["B_strong_negative"]))

    snapshot_row = snapshot_repo._by_snapshot_id[generated.input_snapshot.snapshot_id]
    payload = json.loads(snapshot_row.canonical_payload_json)
    payload["thesis_health"]["thesis_health_index"] = 0.95
    payload["thesis_health"]["evidence_quality"] = 0.95
    payload["thesis_health"]["contradictory_strength"] = 0.01
    tampered = generated.input_snapshot.__class__(
        snapshot_id=snapshot_row.snapshot_id,
        proposal_version_id=snapshot_row.proposal_version_id,
        captured_at=snapshot_row.captured_at,
        canonical_payload_json=json.dumps(payload, sort_keys=True, separators=(",", ":")),
        input_hash=snapshot_row.input_hash,
    )
    snapshot_repo._by_snapshot_id[generated.input_snapshot.snapshot_id] = tampered
    snapshot_repo._by_version_id[generated.proposal_version.proposal_version_id] = tampered

    report = replay.verify_by_proposal_version(generated.proposal_version.proposal_version_id)

    assert report.status == "FAIL"
    assert report.differences
    diff_fields = {row.field for row in report.differences}
    assert "action" in diff_fields or "overall_score" in diff_fields
    assert "deterministic_input_hash" in diff_fields


def test_replay_is_deterministic_across_repeated_verifications() -> None:
    engine, replay, _ = _bundle()
    generated = engine.generate_recommendation(build_input(scenario_catalog()["C_mixed_conflicting"]))

    first = replay.verify_by_proposal_version(generated.proposal_version.proposal_version_id)
    second = replay.verify_by_proposal_version(generated.proposal_version.proposal_version_id)

    assert first == second
