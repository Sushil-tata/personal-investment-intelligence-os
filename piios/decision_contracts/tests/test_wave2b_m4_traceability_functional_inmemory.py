from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from piios.decision_contracts.application.decision_engine import RecommendationDecisionEngine
from piios.decision_contracts.application.recommendation_reconstruction_service import (
    RecommendationReconstructionService,
    TraceIntegrityError,
)
from piios.decision_contracts.domain.decision import InvestmentDecision
from piios.decision_contracts.domain.enums import DecisionState
from piios.decision_contracts.infrastructure.in_memory_repositories import (
    InMemoryInvestmentDecisionRepository,
    InMemoryRecommendationProposalRepository,
    InMemoryRecommendationProposalVersionRepository,
    InMemoryRecommendationReasonRepository,
    InMemoryRecommendationSnapshotRepository,
    InMemoryRecommendationTraceRepository,
)
from piios.decision_contracts.tests.functional_acceptance_helpers import build_input, scenario_catalog


def _setup():
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
    service = RecommendationReconstructionService(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        snapshot_repository=snapshot_repo,
        trace_repository=trace_repo,
        reason_repository=reason_repo,
        decision_repository=decision_repo,
    )
    return engine, service, decision_repo, trace_repo


def test_scenario_a_full_recommendation_reconstruction_inmemory() -> None:
    engine, service, decision_repo, _ = _setup()
    data = build_input(scenario_catalog()["A_strong_positive"])
    generated = engine.generate_recommendation(data)

    decision_repo.create(
        InvestmentDecision(
            decision_id="decision:m4:inmemory:a",
            proposal_version_id=generated.proposal_version.proposal_version_id,
            state=DecisionState.ACCEPTED,
            reason_code="ALIGNED",
            decided_at=datetime(2026, 7, 28, 13, 0, tzinfo=timezone.utc),
        )
    )

    lineage = service.reconstruct_by_investment_decision_id("decision:m4:inmemory:a")
    assert lineage.input_snapshot.snapshot_id == generated.input_snapshot.snapshot_id
    assert lineage.trace.proposal_version_id == generated.proposal_version.proposal_version_id
    assert lineage.proposal.proposal_id == generated.proposal.proposal_id
    assert lineage.investment_decisions[-1].decision_id == "decision:m4:inmemory:a"


def test_scenario_b_deterministic_replay_inmemory() -> None:
    engine, service, _, _ = _setup()
    data = build_input(scenario_catalog()["C_mixed_conflicting"])

    first = engine.generate_recommendation(data)
    second = engine.generate_recommendation(data)

    first_explanation = service.retrieve_authoritative_explanation(first.proposal_version.proposal_version_id)
    second_explanation = service.retrieve_authoritative_explanation(second.proposal_version.proposal_version_id)

    assert first.proposal_version.proposal_version_id == second.proposal_version.proposal_version_id
    assert first.recommendation_trace.trace_id == second.recommendation_trace.trace_id
    assert first_explanation == second_explanation


def test_scenario_c_material_input_change_creates_new_trace_inmemory() -> None:
    engine, service, _, _ = _setup()
    base = build_input(scenario_catalog()["D_missing_evidence"])
    first = engine.generate_recommendation(base)

    changed = replace(
        base,
        thesis_health_snapshot=replace(base.thesis_health_snapshot, evidence_quality=0.33),
    )
    second = engine.generate_recommendation(changed)

    assert second.proposal_version.version_number == 2
    assert first.input_snapshot.input_hash != second.input_snapshot.input_hash
    assert first.recommendation_trace.trace_id != second.recommendation_trace.trace_id

    first_lineage = service.reconstruct_by_proposal_version(first.proposal_version.proposal_version_id)
    second_lineage = service.reconstruct_by_proposal_version(second.proposal_version.proposal_version_id)
    assert first_lineage.trace.trace_id != second_lineage.trace.trace_id


def test_scenario_e_integrity_mismatch_fails_explicitly_inmemory() -> None:
    engine, service, _, trace_repo = _setup()
    data = build_input(scenario_catalog()["E_stale_evidence"])
    generated = engine.generate_recommendation(data)

    tampered_entries = list(generated.recommendation_trace.entries)
    tampered_entries[0] = replace(tampered_entries[0], sequence_number=2)
    trace_repo._entries_by_trace_id[generated.recommendation_trace.trace_id] = tampered_entries

    with pytest.raises(TraceIntegrityError):
        service.verify_trace_integrity(generated.recommendation_trace.trace_id)
