from __future__ import annotations

from dataclasses import fields, replace
import json

import pytest

from piios.decision_contracts.application.decision_engine import RecommendationDecisionEngine
from piios.decision_contracts.application.recommendation_reconstruction_service import (
    MissingInputSnapshotError,
    MissingTraceError,
    RecommendationReconstructionService,
)
from piios.decision_contracts.application.recommendation_replay_verification_service import (
    RecommendationReplayVerificationService,
    _input_from_snapshot_payload,
)
from piios.decision_contracts.application.scoring_components import RecommendationEngineInput
from piios.decision_contracts.domain.enums import RecommendationAction
from piios.decision_contracts.infrastructure.in_memory_repositories import (
    InMemoryInvestmentDecisionRepository,
    InMemoryRecommendationProposalRepository,
    InMemoryRecommendationProposalVersionRepository,
    InMemoryRecommendationReasonRepository,
    InMemoryRecommendationSnapshotRepository,
    InMemoryRecommendationTraceRepository,
)
from piios.decision_contracts.tests.functional_acceptance_helpers import build_input, scenario_catalog


def _bundle() -> tuple[
    RecommendationDecisionEngine,
    RecommendationReplayVerificationService,
    InMemoryRecommendationProposalVersionRepository,
    InMemoryRecommendationSnapshotRepository,
    InMemoryRecommendationTraceRepository,
]:
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
    return engine, replay, version_repo, snapshot_repo, trace_repo


def test_replay_success_passes_when_persisted_artifacts_match() -> None:
    engine, replay, _, _, _ = _bundle()
    generated = engine.generate_recommendation(build_input(scenario_catalog()["A_strong_positive"]))

    report = replay.verify_by_proposal_version(generated.proposal_version.proposal_version_id)

    assert report.status == "PASS"
    assert report.persisted_input_hash == generated.input_snapshot.input_hash
    assert report.recomputed_input_hash == generated.input_snapshot.input_hash
    assert report.persisted_trace_id == generated.recommendation_trace.trace_id
    assert report.recomputed_trace_id == generated.recommendation_trace.trace_id
    assert report.differences == tuple()


def test_replay_failure_reports_detailed_differences_when_input_is_tampered() -> None:
    engine, replay, _, snapshot_repo, _ = _bundle()
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


def test_replay_failure_reports_persisted_proposal_tamper_precisely() -> None:
    engine, replay, version_repo, _, _ = _bundle()
    generated = engine.generate_recommendation(build_input(scenario_catalog()["A_strong_positive"]))

    row = version_repo._by_id[generated.proposal_version.proposal_version_id]
    tampered = replace(
        row,
        action_proposal=replace(
            row.action_proposal,
            action=RecommendationAction.SELL,
            note="strategy=balanced-v1; score=0.111111",
        ),
    )
    version_repo._by_id[row.proposal_version_id] = tampered
    version_repo._by_proposal_id[row.proposal_id] = [tampered]

    report = replay.verify_by_proposal_version(generated.proposal_version.proposal_version_id)

    assert report.status == "FAIL"
    diff_fields = {row.field for row in report.differences}
    assert "persisted_proposal.action" in diff_fields
    assert "persisted_proposal.overall_score" in diff_fields


def test_replay_is_read_only_over_repositories() -> None:
    engine, replay, version_repo, snapshot_repo, trace_repo = _bundle()
    generated = engine.generate_recommendation(build_input(scenario_catalog()["D_missing_evidence"]))

    before = {
        "versions": len(version_repo._by_id),
        "versions_for_proposal": len(version_repo._by_proposal_id[generated.proposal.proposal_id]),
        "snapshots": len(snapshot_repo._by_snapshot_id),
        "snapshots_by_version": len(snapshot_repo._by_version_id),
        "traces": len(trace_repo._traces),
        "entries": sum(len(rows) for rows in trace_repo._entries_by_trace_id.values()),
        "claim_links": len(trace_repo._claim_links),
        "evidence_links": len(trace_repo._evidence_links),
    }

    report = replay.verify_by_proposal_version(generated.proposal_version.proposal_version_id)
    assert report.status == "PASS"

    after = {
        "versions": len(version_repo._by_id),
        "versions_for_proposal": len(version_repo._by_proposal_id[generated.proposal.proposal_id]),
        "snapshots": len(snapshot_repo._by_snapshot_id),
        "snapshots_by_version": len(snapshot_repo._by_version_id),
        "traces": len(trace_repo._traces),
        "entries": sum(len(rows) for rows in trace_repo._entries_by_trace_id.values()),
        "claim_links": len(trace_repo._claim_links),
        "evidence_links": len(trace_repo._evidence_links),
    }
    assert after == before


def test_replay_missing_snapshot_fails_with_explicit_error() -> None:
    engine, replay, _, snapshot_repo, _ = _bundle()
    generated = engine.generate_recommendation(build_input(scenario_catalog()["E_stale_evidence"]))

    snapshot_repo._by_snapshot_id.pop(generated.input_snapshot.snapshot_id, None)
    snapshot_repo._by_version_id.pop(generated.proposal_version.proposal_version_id, None)

    with pytest.raises(MissingInputSnapshotError):
        replay.verify_by_proposal_version(generated.proposal_version.proposal_version_id)


def test_replay_missing_trace_fails_with_explicit_error() -> None:
    engine, replay, _, _, trace_repo = _bundle()
    generated = engine.generate_recommendation(build_input(scenario_catalog()["C_mixed_conflicting"]))

    trace_repo._traces.pop(generated.recommendation_trace.trace_id, None)
    trace_repo._trace_by_proposal_version.pop(generated.proposal_version.proposal_version_id, None)
    trace_repo._trace_by_execution_identity.pop(generated.recommendation_trace.execution_identity, None)
    trace_repo._entries_by_trace_id.pop(generated.recommendation_trace.trace_id, None)

    with pytest.raises(MissingTraceError):
        replay.verify_by_proposal_version(generated.proposal_version.proposal_version_id)


def test_replay_is_deterministic_across_repeated_verifications() -> None:
    engine, replay, _, _, _ = _bundle()
    generated = engine.generate_recommendation(build_input(scenario_catalog()["C_mixed_conflicting"]))

    first = replay.verify_by_proposal_version(generated.proposal_version.proposal_version_id)
    second = replay.verify_by_proposal_version(generated.proposal_version.proposal_version_id)

    assert first == second


def test_replay_input_contract_mapping_guards_against_drift() -> None:
    engine, _, _, _, _ = _bundle()
    generated = engine.generate_recommendation(build_input(scenario_catalog()["A_strong_positive"]))

    payload = json.loads(generated.input_snapshot.canonical_payload_json)
    replay_input = _input_from_snapshot_payload(generated.input_snapshot.canonical_payload_json)

    expected_engine_fields = {
        "proposal_id",
        "target_type",
        "target_key",
        "scope",
        "thesis_version_id",
        "generated_at",
        "thesis_health_snapshot",
        "claims",
        "evidence_items",
        "interpretations",
        "portfolio_context",
        "strategy_key",
        "metadata",
    }
    actual_engine_fields = {row.name for row in fields(RecommendationEngineInput)}
    assert actual_engine_fields == expected_engine_fields

    # Top-level contract keys used by replay reconstruction must all be present.
    required_payload_keys = {
        "generated_at",
        "proposal",
        "thesis_health",
        "portfolio_context",
        "claims",
        "evidence",
        "interpretations",
        "metadata",
        "component_scores",
        "strategy_result",
        "explanation",
    }
    assert required_payload_keys.issubset(set(payload.keys()))

    assert replay_input.proposal_id == payload["proposal"]["proposal_id"]
    assert replay_input.target_type == payload["proposal"]["target_type"]
    assert replay_input.target_key == payload["proposal"]["target_key"]
    assert replay_input.scope == payload["proposal"]["scope"]
    assert replay_input.strategy_key == payload["proposal"]["strategy_key"]
    assert replay_input.thesis_version_id == payload["thesis_health"]["thesis_version_id"]
    assert replay_input.generated_at.isoformat() == payload["generated_at"]

    th = payload["thesis_health"]
    assert replay_input.thesis_health_snapshot.computation_version == th["computation_version"]
    assert replay_input.thesis_health_snapshot.computed_at.isoformat() == th["computed_at"]
    assert replay_input.thesis_health_snapshot.evidence_freshness == float(th["evidence_freshness"])
    assert replay_input.thesis_health_snapshot.evidence_quality == float(th["evidence_quality"])
    assert replay_input.thesis_health_snapshot.supporting_strength == float(th["supporting_strength"])
    assert replay_input.thesis_health_snapshot.contradictory_strength == float(th["contradictory_strength"])
    assert replay_input.thesis_health_snapshot.provenance_completeness == float(th["provenance_completeness"])
    assert replay_input.thesis_health_snapshot.thesis_health_index == float(th["thesis_health_index"])

    pc = payload["portfolio_context"]
    assert replay_input.portfolio_context.has_existing_position == bool(pc["has_existing_position"])
    assert replay_input.portfolio_context.current_weight == float(pc["current_weight"])
    assert replay_input.portfolio_context.target_weight == float(pc["target_weight"])
    assert replay_input.portfolio_context.max_position_weight == float(pc["max_position_weight"])
    assert replay_input.portfolio_context.concentration_risk == float(pc["concentration_risk"])
    assert replay_input.portfolio_context.liquidity_risk == float(pc["liquidity_risk"])
    assert replay_input.portfolio_context.portfolio_underweight_signal == float(pc["portfolio_underweight_signal"])
    assert replay_input.portfolio_context.opportunity_signal == float(pc["opportunity_signal"])
    assert replay_input.portfolio_context.valuation_signal == float(pc["valuation_signal"])
    assert replay_input.portfolio_context.expected_return_signal == float(pc["expected_return_signal"])
    assert replay_input.portfolio_context.relationship_signal == float(pc["relationship_signal"])

    assert len(replay_input.claims) == len(payload["claims"])
    assert len(replay_input.evidence_items) == len(payload["evidence"])
    assert len(replay_input.interpretations) == len(payload["interpretations"])
    assert replay_input.metadata == {str(k): str(v) for k, v in payload["metadata"].items()}
