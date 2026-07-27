from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlmodel import SQLModel, Session, create_engine

from piios.decision_contracts.domain.enums import (
    ProposalStatus,
    RuleResult,
    RuleSeverity,
    TraceEntryStatus,
    TraceEntryType,
    TraceExecutionStatus,
)
from piios.decision_contracts.domain.proposal import RecommendationInputSnapshot, RecommendationProposal, RecommendationProposalVersion
from piios.decision_contracts.domain.recommendation_trace import (
    ComponentResultReference,
    RecommendationTrace,
    RuleEvaluation,
    TraceEntry,
)
from piios.decision_contracts.domain.value_objects import (
    ActionProposal,
    ConfidenceBreakdown,
    RecommendationConfidenceDimensions,
    RecommendationPriority,
)
from piios.decision_contracts.domain.enums import Priority, RecommendationAction
from piios.decision_contracts.infrastructure import sqlmodel_entities as decision_sqlmodel_entities  # noqa: F401
from piios.decision_contracts.infrastructure.in_memory_repositories import (
    InMemoryRecommendationProposalRepository,
    InMemoryRecommendationProposalVersionRepository,
    InMemoryRecommendationSnapshotRepository,
    InMemoryRecommendationTraceRepository,
)
from piios.decision_contracts.infrastructure.sqlmodel_repositories import (
    SQLModelRecommendationProposalRepository,
    SQLModelRecommendationProposalVersionRepository,
    SQLModelRecommendationSnapshotRepository,
    SQLModelRecommendationTraceRepository,
)
from piios.thesis_health.infrastructure import sqlmodel_entities as thesis_health_sqlmodel_entities  # noqa: F401
from piios_backend.models import entities as backend_entities  # noqa: F401


@pytest.fixture(params=["in_memory", "sqlmodel"])
def trace_bundle(request, tmp_path):
    if request.param == "in_memory":
        return {
            "proposal": InMemoryRecommendationProposalRepository(),
            "version": InMemoryRecommendationProposalVersionRepository(),
            "snapshot": InMemoryRecommendationSnapshotRepository(),
            "trace": InMemoryRecommendationTraceRepository(),
        }

    db_path = tmp_path / "trace_repo.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    request.addfinalizer(session.close)
    return {
        "proposal": SQLModelRecommendationProposalRepository(session),
        "version": SQLModelRecommendationProposalVersionRepository(session),
        "snapshot": SQLModelRecommendationSnapshotRepository(session),
        "trace": SQLModelRecommendationTraceRepository(session),
    }


def _seed_foundation(bundle, proposal_id: str = "proposal:p1") -> str:
    bundle["proposal"].create(
        RecommendationProposal(
            proposal_id=proposal_id,
            target_type="SECURITY",
            target_key="NVDA",
            scope="PORTFOLIO",
            status=ProposalStatus.ACTIVE,
            created_at=datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc),
        )
    )

    proposal_version_id = f"{proposal_id}:v1"
    bundle["version"].create(
        RecommendationProposalVersion(
            proposal_version_id=proposal_version_id,
            proposal_id=proposal_id,
            version_number=1,
            status=ProposalStatus.ACTIVE,
            created_at=datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc),
            snapshot_id=f"{proposal_id}:snap:v1",
            action_proposal=ActionProposal(action=RecommendationAction.ADD),
            confidence_breakdown=ConfidenceBreakdown(
                dimensions=RecommendationConfidenceDimensions(
                    company_quality=0.8,
                    valuation_attractiveness=0.7,
                    portfolio_suitability=0.6,
                    recommendation_confidence=0.7,
                    relationship_confidence=0.5,
                    expected_return=0.6,
                ),
                overall_confidence=0.65,
            ),
            priority=RecommendationPriority(level=Priority.HIGH, score=0.8),
            required_human_review=False,
            supersedes_version_id=None,
        )
    )

    bundle["snapshot"].create(
        RecommendationInputSnapshot(
            snapshot_id=f"{proposal_id}:snap:v1",
            proposal_version_id=proposal_version_id,
            captured_at=datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc),
            canonical_payload_json='{"proposal_id":"p1"}',
            input_hash=f"{proposal_id}:hash",
        )
    )
    return proposal_version_id


def _trace(proposal_id: str, proposal_version_id: str) -> RecommendationTrace:
    trace_id = f"{proposal_version_id}:trace:abc"
    entry = TraceEntry(
        entry_id=f"{trace_id}:e:01",
        trace_id=trace_id,
        sequence_number=1,
        entry_type=TraceEntryType.INPUT_SNAPSHOT_REFERENCE,
        component_name="input_snapshot",
        component_version="v1",
        status=TraceEntryStatus.APPLIED,
        input_references=tuple(),
        output_references=(
            ComponentResultReference(
                reference_type="RecommendationInputSnapshot",
                reference_id=f"{proposal_id}:snap:v1",
                source="decision_recommendation_input_snapshots",
            ),
        ),
        rule_evaluations=(
            RuleEvaluation(
                rule_id="r1",
                rule_version="balanced-v1",
                rule_name="input_hash",
                result=RuleResult.PASSED,
                observed_value="same",
                comparison_operator="=",
                threshold_value="same",
                reason_code="HASH_MATCH",
                severity=RuleSeverity.INFO,
                source_reference="snapshot",
            ),
        ),
        numeric_outputs={"entry_count": 1.0},
        categorical_outputs={"input_hash": f"{proposal_id}:hash"},
        warning_codes=tuple(),
        created_at=datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc),
    )
    return RecommendationTrace(
        trace_id=trace_id,
        proposal_id=proposal_id,
        proposal_version_id=proposal_version_id,
        input_snapshot_id=f"{proposal_id}:snap:v1",
        engine_name="RecommendationDecisionEngine",
        engine_version="wave2b-m3-v1",
        policy_version="policy-wave2b-v1",
        strategy_version="balanced-v1",
        execution_identity=f"{proposal_id}:hash:engine:policy:strategy",
        computation_started_at=datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc),
        computation_completed_at=datetime(2026, 7, 28, 10, 0, 1, tzinfo=timezone.utc),
        trace_schema_version="wave2b-trace-v1",
        execution_status=TraceExecutionStatus.COMPLETED,
        is_authoritative=True,
        entries=(entry,),
        created_at=datetime(2026, 7, 28, 10, 0, 1, tzinfo=timezone.utc),
    )


def test_trace_repository_append_only_and_lookup(trace_bundle) -> None:
    proposal_version_id = _seed_foundation(trace_bundle)
    trace = _trace("proposal:p1", proposal_version_id)

    trace_bundle["trace"].create_trace(trace)

    loaded = trace_bundle["trace"].get_trace(trace.trace_id)
    assert loaded is not None
    assert loaded.trace_id == trace.trace_id
    assert trace_bundle["trace"].get_trace_for_proposal_version(proposal_version_id).trace_id == trace.trace_id
    assert trace_bundle["trace"].trace_exists_for_execution_identity(trace.execution_identity)

    entries = trace_bundle["trace"].list_entries(trace.trace_id)
    assert [row.sequence_number for row in entries] == [1]


def test_trace_repository_duplicate_prevention(trace_bundle) -> None:
    proposal_version_id = _seed_foundation(trace_bundle, proposal_id="proposal:p2")
    trace = _trace("proposal:p2", proposal_version_id)
    trace_bundle["trace"].create_trace(trace)

    with pytest.raises(ValueError):
        trace_bundle["trace"].create_trace(trace)


def test_trace_repository_idempotent_execution_identity_guard(trace_bundle) -> None:
    proposal_version_id = _seed_foundation(trace_bundle, proposal_id="proposal:p3")
    trace = _trace("proposal:p3", proposal_version_id)
    trace_bundle["trace"].create_trace(trace)

    other_version_id = _seed_foundation(trace_bundle, proposal_id="proposal:p4")
    conflicting = RecommendationTrace(
        trace_id=f"{other_version_id}:trace:xyz",
        proposal_id="proposal:p4",
        proposal_version_id=other_version_id,
        input_snapshot_id="proposal:p4:snap:v1",
        engine_name=trace.engine_name,
        engine_version=trace.engine_version,
        policy_version=trace.policy_version,
        strategy_version=trace.strategy_version,
        execution_identity=trace.execution_identity,
        computation_started_at=trace.computation_started_at,
        computation_completed_at=trace.computation_completed_at,
        trace_schema_version=trace.trace_schema_version,
        execution_status=trace.execution_status,
        is_authoritative=True,
        entries=(replace_trace_entry_trace_id(trace.entries[0], f"{other_version_id}:trace:xyz"),),
        created_at=trace.created_at,
    )

    with pytest.raises(ValueError):
        trace_bundle["trace"].create_trace(conflicting)


def replace_trace_entry_trace_id(entry: TraceEntry, trace_id: str) -> TraceEntry:
    return TraceEntry(
        entry_id=entry.entry_id.replace(entry.trace_id, trace_id),
        trace_id=trace_id,
        sequence_number=entry.sequence_number,
        entry_type=entry.entry_type,
        component_name=entry.component_name,
        component_version=entry.component_version,
        status=entry.status,
        input_references=entry.input_references,
        output_references=entry.output_references,
        rule_evaluations=entry.rule_evaluations,
        numeric_outputs=entry.numeric_outputs,
        categorical_outputs=entry.categorical_outputs,
        warning_codes=entry.warning_codes,
        created_at=entry.created_at,
    )
