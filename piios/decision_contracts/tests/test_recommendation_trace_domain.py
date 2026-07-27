from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from piios.decision_contracts.domain.enums import (
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


def _rule() -> RuleEvaluation:
    return RuleEvaluation(
        rule_id="r.score",
        rule_version="balanced-v1",
        rule_name="overall_score",
        result=RuleResult.PASSED,
        observed_value="0.72",
        comparison_operator=">=",
        threshold_value="0.62",
        reason_code="RULE_SCORE",
        severity=RuleSeverity.INFO,
        source_reference="strategy.applied_rules",
    )


def _entry(sequence: int, trace_id: str = "trace-1") -> TraceEntry:
    return TraceEntry(
        entry_id=f"{trace_id}:e:{sequence:02d}",
        trace_id=trace_id,
        sequence_number=sequence,
        entry_type=TraceEntryType.STRATEGY_EVALUATION,
        component_name="weighted_strategy",
        component_version="balanced-v1",
        status=TraceEntryStatus.APPLIED,
        input_references=(
            ComponentResultReference(
                reference_type="RecommendationInputSnapshot",
                reference_id="snap-1",
                source="decision_recommendation_input_snapshots",
            ),
        ),
        output_references=tuple(),
        rule_evaluations=(_rule(),),
        numeric_outputs={"overall_score": 0.72},
        categorical_outputs={"action": "ADD"},
        warning_codes=("RISK_PENALTY",),
        created_at=datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc),
    )


def _trace(entries: tuple[TraceEntry, ...]) -> RecommendationTrace:
    return RecommendationTrace(
        trace_id="trace-1",
        proposal_id="proposal-1",
        proposal_version_id="proposal-1:v1",
        input_snapshot_id="proposal-1:snap:v1",
        engine_name="RecommendationDecisionEngine",
        engine_version="wave2b-m3-v1",
        policy_version="policy-wave2b-v1",
        strategy_version="balanced-v1",
        execution_identity="proposal-1:hash:wave2b-m3-v1:policy-wave2b-v1:balanced-v1",
        computation_started_at=datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc),
        computation_completed_at=datetime(2026, 7, 28, 10, 0, 1, tzinfo=timezone.utc),
        trace_schema_version="wave2b-trace-v1",
        execution_status=TraceExecutionStatus.COMPLETED,
        is_authoritative=True,
        entries=entries,
        created_at=datetime(2026, 7, 28, 10, 0, 1, tzinfo=timezone.utc),
    )


def test_trace_domain_immutability() -> None:
    trace = _trace((_entry(1),))
    with pytest.raises(FrozenInstanceError):
        trace.trace_id = "other"


def test_trace_rejects_duplicate_sequence_numbers() -> None:
    with pytest.raises(ValueError, match="sequence"):
        _trace((_entry(1), _entry(1)))


def test_trace_rejects_non_monotonic_order() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        _trace((_entry(2), _entry(1)))


def test_trace_rejects_invalid_timestamps() -> None:
    with pytest.raises(ValueError, match="cannot be before"):
        RecommendationTrace(
            trace_id="trace-1",
            proposal_id="proposal-1",
            proposal_version_id="proposal-1:v1",
            input_snapshot_id="proposal-1:snap:v1",
            engine_name="RecommendationDecisionEngine",
            engine_version="wave2b-m3-v1",
            policy_version="policy-wave2b-v1",
            strategy_version="balanced-v1",
            execution_identity="id",
            computation_started_at=datetime(2026, 7, 28, 10, 0, 1, tzinfo=timezone.utc),
            computation_completed_at=datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc),
            trace_schema_version="wave2b-trace-v1",
            execution_status=TraceExecutionStatus.COMPLETED,
            is_authoritative=True,
            entries=(_entry(1),),
            created_at=datetime(2026, 7, 28, 10, 0, 1, tzinfo=timezone.utc),
        )


def test_trace_rejects_failed_authoritative_status() -> None:
    with pytest.raises(ValueError, match="only completed traces"):
        RecommendationTrace(
            trace_id="trace-1",
            proposal_id="proposal-1",
            proposal_version_id="proposal-1:v1",
            input_snapshot_id="proposal-1:snap:v1",
            engine_name="RecommendationDecisionEngine",
            engine_version="wave2b-m3-v1",
            policy_version="policy-wave2b-v1",
            strategy_version="balanced-v1",
            execution_identity="id",
            computation_started_at=datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc),
            computation_completed_at=datetime(2026, 7, 28, 10, 0, 1, tzinfo=timezone.utc),
            trace_schema_version="wave2b-trace-v1",
            execution_status=TraceExecutionStatus.FAILED,
            is_authoritative=True,
            entries=(_entry(1),),
            created_at=datetime(2026, 7, 28, 10, 0, 1, tzinfo=timezone.utc),
        )


def test_rule_evaluation_validation_and_deterministic_serialisation() -> None:
    rule = _rule()
    assert list(rule.deterministic_dict().keys()) == sorted(rule.deterministic_dict().keys())

    with pytest.raises(ValueError):
        RuleEvaluation(
            rule_id="",
            rule_version="v1",
            rule_name="name",
            result=RuleResult.PASSED,
            observed_value="1",
            comparison_operator=">",
            threshold_value="0",
            reason_code="R",
            severity=RuleSeverity.INFO,
            source_reference="source",
        )


def test_trace_entry_rejects_invalid_component_version_and_type_data() -> None:
    with pytest.raises(ValueError, match="component_version"):
        TraceEntry(
            entry_id="e1",
            trace_id="t1",
            sequence_number=1,
            entry_type=TraceEntryType.INPUT_SNAPSHOT_REFERENCE,
            component_name="input",
            component_version="",
            status=TraceEntryStatus.APPLIED,
            input_references=tuple(),
            output_references=tuple(),
            rule_evaluations=tuple(),
            numeric_outputs={},
            categorical_outputs={},
            warning_codes=tuple(),
            created_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
        )


def test_trace_rejects_entry_with_different_trace_id() -> None:
    with pytest.raises(ValueError, match="same trace"):
        _trace((_entry(1, "trace-1"), _entry(2, "trace-2")))
