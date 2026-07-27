from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from piios.decision_contracts.application.decision_engine import RecommendationDecisionEngine
from piios.decision_contracts.application.recommendation_reconstruction_service import (
    IncompleteTraceError,
    MissingTraceError,
    RecommendationReconstructionService,
    TraceIntegrityError,
    UnsupportedTraceSchemaVersionError,
)
from piios.decision_contracts.domain.decision import InvestmentDecision
from piios.decision_contracts.domain.enums import (
    DecisionState,
    RuleResult,
    RuleSeverity,
    TraceEntryStatus,
    TraceEntryType,
    TraceExecutionStatus,
)
from piios.decision_contracts.domain.recommendation_trace import (
    ComponentResultReference,
    RecommendationTrace,
    RuleEvaluation,
    TraceEntry,
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
    service = RecommendationReconstructionService(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        snapshot_repository=snapshot_repo,
        trace_repository=trace_repo,
        reason_repository=reason_repo,
        decision_repository=decision_repo,
    )
    return engine, service, decision_repo, trace_repo


def test_reconstruction_and_explanation_are_deterministic() -> None:
    engine, service, decision_repo, _ = _bundle()
    data = build_input(scenario_catalog()["A_strong_positive"])

    result = engine.generate_recommendation(data)
    decision_repo.create(
        InvestmentDecision(
            decision_id="decision:scenario-a:v1",
            proposal_version_id=result.proposal_version.proposal_version_id,
            state=DecisionState.ACCEPTED,
            reason_code="MANDATE_ALIGNED",
            decided_at=datetime(2026, 7, 28, 12, 5, tzinfo=timezone.utc),
        )
    )

    lineage = service.reconstruct_by_investment_decision_id("decision:scenario-a:v1")
    explanation_one = service.retrieve_authoritative_explanation(result.proposal_version.proposal_version_id)
    explanation_two = service.retrieve_authoritative_explanation(result.proposal_version.proposal_version_id)

    assert lineage.proposal_version.proposal_version_id == result.proposal_version.proposal_version_id
    assert lineage.trace.trace_id == result.recommendation_trace.trace_id
    assert explanation_one == explanation_two
    assert explanation_one.primary_supporting_reasons
    assert len(explanation_one.primary_supporting_reasons) <= 3
    assert len(explanation_one.primary_limiting_reasons) <= 3
    reason_codes = {
        row.reason_code
        for row in lineage.reasons
    }
    projected_codes = {
        row["reason_code"]
        for row in explanation_one.primary_supporting_reasons + explanation_one.primary_limiting_reasons
    }
    assert projected_codes.issubset(reason_codes)
    assert service.compare_reconstructed_proposal_output(result.proposal_version.proposal_version_id)


def test_reconstruction_missing_trace_failure() -> None:
    _, service, _, _ = _bundle()
    with pytest.raises(MissingTraceError):
        service.reconstruct_by_trace_id("missing-trace")


def test_reconstruction_incomplete_trace_failure() -> None:
    _, service, _, trace_repo = _bundle()
    trace = RecommendationTrace(
        trace_id="trace:incomplete",
        proposal_id="proposal:incomplete",
        proposal_version_id="proposal:incomplete:v1",
        input_snapshot_id="proposal:incomplete:snap:v1",
        engine_name="RecommendationDecisionEngine",
        engine_version="wave2b-m3-v1",
        policy_version="policy-wave2b-v1",
        strategy_version="balanced-v1",
        execution_identity="proposal:incomplete:identity",
        computation_started_at=datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc),
        computation_completed_at=datetime(2026, 7, 28, 10, 0, 1, tzinfo=timezone.utc),
        trace_schema_version="wave2b-trace-v1",
        execution_status=TraceExecutionStatus.IN_PROGRESS,
        is_authoritative=False,
        entries=(
            TraceEntry(
                entry_id="trace:incomplete:e:01",
                trace_id="trace:incomplete",
                sequence_number=1,
                entry_type=TraceEntryType.EXECUTION_FAILURE,
                component_name="persistence",
                component_version="v1",
                status=TraceEntryStatus.FAILED,
                input_references=tuple(),
                output_references=tuple(),
                rule_evaluations=(
                    RuleEvaluation(
                        rule_id="persistence.rollback",
                        rule_version="v1",
                        rule_name="rollback",
                        result=RuleResult.PASSED,
                        observed_value="true",
                        comparison_operator="=",
                        threshold_value="true",
                        reason_code="ROLLBACK_OK",
                        severity=RuleSeverity.WARNING,
                        source_reference="engine",
                    ),
                ),
                numeric_outputs={},
                categorical_outputs={"error": "injected"},
                warning_codes=("ROLLBACK",),
                created_at=datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc),
            ),
        ),
        created_at=datetime(2026, 7, 28, 10, 0, 1, tzinfo=timezone.utc),
    )
    trace_repo.create_trace(trace)

    with pytest.raises(IncompleteTraceError):
        service.verify_trace_integrity("trace:incomplete")


def test_reconstruction_unsupported_schema_version_failure() -> None:
    engine, service, _, trace_repo = _bundle()
    data = build_input(scenario_catalog()["C_mixed_conflicting"])
    result = engine.generate_recommendation(data)
    bad_trace = replace(result.recommendation_trace, trace_schema_version="wave2b-trace-v99")

    trace_repo._traces[bad_trace.trace_id] = bad_trace

    with pytest.raises(UnsupportedTraceSchemaVersionError):
        service.verify_trace_integrity(bad_trace.trace_id)


def test_reconstruction_detects_integrity_mismatch() -> None:
    engine, service, _, trace_repo = _bundle()
    data = build_input(scenario_catalog()["D_missing_evidence"])
    result = engine.generate_recommendation(data)

    bad_entries = list(result.recommendation_trace.entries)
    bad_entries[0] = replace(bad_entries[0], sequence_number=2)
    trace_repo._entries_by_trace_id[result.recommendation_trace.trace_id] = list(bad_entries)

    with pytest.raises(TraceIntegrityError):
        service.verify_trace_integrity(result.recommendation_trace.trace_id)
