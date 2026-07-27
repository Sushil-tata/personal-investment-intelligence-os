from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from piios.decision_contracts.domain.enums import (
    RuleResult,
    RuleSeverity,
    TraceEntryStatus,
    TraceEntryType,
    TraceExecutionStatus,
)


@dataclass(frozen=True)
class RuleEvaluation:
    rule_id: str
    rule_version: str
    rule_name: str
    result: RuleResult
    observed_value: str
    comparison_operator: str
    threshold_value: str
    reason_code: str
    severity: RuleSeverity
    source_reference: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("rule_id", self.rule_id),
            ("rule_version", self.rule_version),
            ("rule_name", self.rule_name),
            ("observed_value", self.observed_value),
            ("comparison_operator", self.comparison_operator),
            ("threshold_value", self.threshold_value),
            ("reason_code", self.reason_code),
            ("source_reference", self.source_reference),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} must not be empty")

    def deterministic_dict(self) -> dict[str, str]:
        return {
            "comparison_operator": self.comparison_operator,
            "observed_value": self.observed_value,
            "reason_code": self.reason_code,
            "result": self.result.value,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "rule_version": self.rule_version,
            "severity": self.severity.value,
            "source_reference": self.source_reference,
            "threshold_value": self.threshold_value,
        }


@dataclass(frozen=True)
class ComponentResultReference:
    reference_type: str
    reference_id: str
    source: str

    def __post_init__(self) -> None:
        if not self.reference_type.strip():
            raise ValueError("reference_type must not be empty")
        if not self.reference_id.strip():
            raise ValueError("reference_id must not be empty")
        if not self.source.strip():
            raise ValueError("source must not be empty")

    def deterministic_dict(self) -> dict[str, str]:
        return {
            "reference_id": self.reference_id,
            "reference_type": self.reference_type,
            "source": self.source,
        }


@dataclass(frozen=True)
class TraceEntry:
    entry_id: str
    trace_id: str
    sequence_number: int
    entry_type: TraceEntryType
    component_name: str
    component_version: str
    status: TraceEntryStatus
    input_references: tuple[ComponentResultReference, ...]
    output_references: tuple[ComponentResultReference, ...]
    rule_evaluations: tuple[RuleEvaluation, ...]
    numeric_outputs: dict[str, float]
    categorical_outputs: dict[str, str]
    warning_codes: tuple[str, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.entry_id.strip():
            raise ValueError("entry_id must not be empty")
        if not self.trace_id.strip():
            raise ValueError("trace_id must not be empty")
        if self.sequence_number <= 0:
            raise ValueError("sequence_number must be > 0")
        if not self.component_name.strip():
            raise ValueError("component_name must not be empty")
        if not self.component_version.strip():
            raise ValueError("component_version must not be empty")

        for key, value in self.numeric_outputs.items():
            if not key.strip():
                raise ValueError("numeric_outputs keys must not be empty")
            float(value)
        for key, value in self.categorical_outputs.items():
            if not key.strip() or not value.strip():
                raise ValueError("categorical_outputs keys and values must not be empty")
        for code in self.warning_codes:
            if not code.strip():
                raise ValueError("warning_codes must not contain empty values")

    def deterministic_dict(self) -> dict[str, object]:
        return {
            "categorical_outputs": {
                key: self.categorical_outputs[key]
                for key in sorted(self.categorical_outputs.keys())
            },
            "component_name": self.component_name,
            "component_version": self.component_version,
            "created_at": self.created_at.isoformat(),
            "entry_id": self.entry_id,
            "entry_type": self.entry_type.value,
            "input_references": [row.deterministic_dict() for row in self.input_references],
            "numeric_outputs": {
                key: round(float(self.numeric_outputs[key]), 6)
                for key in sorted(self.numeric_outputs.keys())
            },
            "output_references": [row.deterministic_dict() for row in self.output_references],
            "rule_evaluations": [row.deterministic_dict() for row in self.rule_evaluations],
            "sequence_number": self.sequence_number,
            "status": self.status.value,
            "trace_id": self.trace_id,
            "warning_codes": list(self.warning_codes),
        }


@dataclass(frozen=True)
class RecommendationTrace:
    trace_id: str
    proposal_id: str
    proposal_version_id: str
    input_snapshot_id: str
    engine_name: str
    engine_version: str
    policy_version: str
    strategy_version: str
    execution_identity: str
    computation_started_at: datetime
    computation_completed_at: datetime
    trace_schema_version: str
    execution_status: TraceExecutionStatus
    is_authoritative: bool
    entries: tuple[TraceEntry, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        for field_name, value in (
            ("trace_id", self.trace_id),
            ("proposal_id", self.proposal_id),
            ("proposal_version_id", self.proposal_version_id),
            ("input_snapshot_id", self.input_snapshot_id),
            ("engine_name", self.engine_name),
            ("engine_version", self.engine_version),
            ("policy_version", self.policy_version),
            ("strategy_version", self.strategy_version),
            ("execution_identity", self.execution_identity),
            ("trace_schema_version", self.trace_schema_version),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} must not be empty")

        if self.computation_completed_at < self.computation_started_at:
            raise ValueError("computation_completed_at cannot be before computation_started_at")

        if self.execution_status == TraceExecutionStatus.COMPLETED and not self.entries:
            raise ValueError("completed trace must include entries")

        if self.execution_status != TraceExecutionStatus.COMPLETED and self.is_authoritative:
            raise ValueError("only completed traces can be authoritative")

        sequence_numbers: set[int] = set()
        previous = 0
        for entry in self.entries:
            if entry.trace_id != self.trace_id:
                raise ValueError("all entries must belong to the same trace")
            if entry.sequence_number in sequence_numbers:
                raise ValueError("entry sequence numbers must be unique")
            sequence_numbers.add(entry.sequence_number)
            if entry.sequence_number <= previous:
                raise ValueError("entry ordering must be deterministic and strictly increasing")
            previous = entry.sequence_number

    def deterministic_dict(self) -> dict[str, object]:
        return {
            "computation_completed_at": self.computation_completed_at.isoformat(),
            "computation_started_at": self.computation_started_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "engine_name": self.engine_name,
            "engine_version": self.engine_version,
            "entries": [row.deterministic_dict() for row in self.entries],
            "execution_identity": self.execution_identity,
            "execution_status": self.execution_status.value,
            "input_snapshot_id": self.input_snapshot_id,
            "is_authoritative": self.is_authoritative,
            "policy_version": self.policy_version,
            "proposal_id": self.proposal_id,
            "proposal_version_id": self.proposal_version_id,
            "strategy_version": self.strategy_version,
            "trace_id": self.trace_id,
            "trace_schema_version": self.trace_schema_version,
        }
