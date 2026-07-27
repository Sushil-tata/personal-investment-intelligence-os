from __future__ import annotations

import json
from dataclasses import dataclass

from piios.decision_contracts.domain.explanation_projection import RecommendationExplanation
from piios.decision_contracts.domain.proposal import RecommendationInputSnapshot, RecommendationProposal, RecommendationProposalVersion, RecommendationReason
from piios.decision_contracts.domain.recommendation_trace import RecommendationTrace, TraceEntry
from piios.decision_contracts.infrastructure.repository_protocols import (
    InvestmentDecisionRepositoryProtocol,
    RecommendationProposalRepositoryProtocol,
    RecommendationProposalVersionRepositoryProtocol,
    RecommendationReasonRepositoryProtocol,
    RecommendationSnapshotRepositoryProtocol,
    RecommendationTraceRepositoryProtocol,
)


class ReconstructionError(Exception):
    pass


class MissingTraceError(ReconstructionError):
    pass


class MissingInputSnapshotError(ReconstructionError):
    pass


class IncompleteTraceError(ReconstructionError):
    pass


class FailedTraceError(ReconstructionError):
    pass


class ProposalMismatchError(ReconstructionError):
    pass


class TraceIntegrityError(ReconstructionError):
    pass


class UnknownDecisionProposalVersionError(ReconstructionError):
    pass


class UnsupportedTraceSchemaVersionError(ReconstructionError):
    pass


@dataclass(frozen=True)
class RecommendationDecisionLineage:
    proposal: RecommendationProposal
    proposal_version: RecommendationProposalVersion
    input_snapshot: RecommendationInputSnapshot
    trace: RecommendationTrace
    trace_entries: tuple[TraceEntry, ...]
    reasons: tuple[RecommendationReason, ...]
    investment_decisions: tuple[object, ...]


class RecommendationReconstructionService:
    SUPPORTED_TRACE_SCHEMA_VERSIONS = {"wave2b-trace-v1"}

    def __init__(
        self,
        proposal_repository: RecommendationProposalRepositoryProtocol,
        version_repository: RecommendationProposalVersionRepositoryProtocol,
        snapshot_repository: RecommendationSnapshotRepositoryProtocol,
        trace_repository: RecommendationTraceRepositoryProtocol,
        reason_repository: RecommendationReasonRepositoryProtocol,
        decision_repository: InvestmentDecisionRepositoryProtocol,
    ) -> None:
        self._proposal_repository = proposal_repository
        self._version_repository = version_repository
        self._snapshot_repository = snapshot_repository
        self._trace_repository = trace_repository
        self._reason_repository = reason_repository
        self._decision_repository = decision_repository

    def reconstruct_by_proposal_version(self, proposal_version_id: str) -> RecommendationDecisionLineage:
        proposal_version = self._version_repository.get(proposal_version_id)
        if proposal_version is None:
            raise ProposalMismatchError(f"unknown proposal_version_id: {proposal_version_id}")

        proposal = self._proposal_repository.get(proposal_version.proposal_id)
        if proposal is None:
            raise ProposalMismatchError(
                f"proposal missing for proposal_version_id={proposal_version_id}: {proposal_version.proposal_id}"
            )

        snapshot = self._snapshot_repository.get_for_proposal_version(proposal_version_id)
        if snapshot is None:
            raise MissingInputSnapshotError(f"missing input snapshot for proposal_version_id: {proposal_version_id}")

        trace = self._trace_repository.get_trace_for_proposal_version(proposal_version_id)
        if trace is None:
            raise MissingTraceError(f"missing trace for proposal_version_id: {proposal_version_id}")

        self._validate_trace(trace)
        entries = tuple(self._trace_repository.list_entries(trace.trace_id))
        reasons = tuple(self._reason_repository.list_for_proposal_version(proposal_version_id))
        decisions = tuple(self._decision_repository.list_for_proposal_version(proposal_version_id))

        return RecommendationDecisionLineage(
            proposal=proposal,
            proposal_version=proposal_version,
            input_snapshot=snapshot,
            trace=trace,
            trace_entries=entries,
            reasons=reasons,
            investment_decisions=decisions,
        )

    def reconstruct_by_trace_id(self, trace_id: str) -> RecommendationDecisionLineage:
        trace = self._trace_repository.get_trace(trace_id)
        if trace is None:
            raise MissingTraceError(f"missing trace_id: {trace_id}")
        return self.reconstruct_by_proposal_version(trace.proposal_version_id)

    def reconstruct_by_investment_decision_id(self, decision_id: str) -> RecommendationDecisionLineage:
        decision = self._decision_repository.get(decision_id)
        if decision is None:
            raise UnknownDecisionProposalVersionError(f"unknown decision_id: {decision_id}")

        proposal_version = self._version_repository.get(decision.proposal_version_id)
        if proposal_version is None:
            raise UnknownDecisionProposalVersionError(
                f"decision references unknown proposal_version_id: {decision.proposal_version_id}"
            )

        return self.reconstruct_by_proposal_version(decision.proposal_version_id)

    def retrieve_authoritative_explanation(self, proposal_version_id: str) -> RecommendationExplanation:
        lineage = self.reconstruct_by_proposal_version(proposal_version_id)

        supporting = _ranked_reasons(lineage.reasons, include_negative=False)
        limiting = _ranked_reasons(lineage.reasons, include_negative=True)

        warnings = _material_warnings(lineage.trace_entries)
        considerations = _derived_references(lineage.trace_entries, "ExecutionConsideration")
        monitoring = _derived_references(lineage.trace_entries, "MonitoringTrigger")

        summary = (
            f"{lineage.proposal_version.action_proposal.action.value} "
            f"priority={lineage.proposal_version.priority.level.value} "
            f"confidence={lineage.proposal_version.confidence_breakdown.overall_confidence:.6f}"
        )

        position_size = None
        if lineage.proposal_version.action_proposal.position_size_range is not None:
            position_size = {
                "min_weight": lineage.proposal_version.action_proposal.position_size_range.min_weight,
                "max_weight": lineage.proposal_version.action_proposal.position_size_range.max_weight,
            }

        confidence = lineage.proposal_version.confidence_breakdown
        dimensions = {
            "company_quality": confidence.dimensions.company_quality,
            "valuation_attractiveness": confidence.dimensions.valuation_attractiveness,
            "portfolio_suitability": confidence.dimensions.portfolio_suitability,
            "recommendation_confidence": confidence.dimensions.recommendation_confidence,
            "relationship_confidence": confidence.dimensions.relationship_confidence,
            "expected_return": confidence.dimensions.expected_return,
        }

        return RecommendationExplanation(
            recommendation_action=lineage.proposal_version.action_proposal.action.value,
            recommendation_priority=lineage.proposal_version.priority.level.value,
            total_confidence=lineage.proposal_version.confidence_breakdown.overall_confidence,
            confidence_dimensions=dimensions,
            primary_supporting_reasons=tuple(supporting[:3]),
            primary_limiting_reasons=tuple(limiting[:3]),
            material_risk_warnings=tuple(warnings),
            portfolio_suitability_summary={
                "scope": lineage.proposal.scope,
                "target_type": lineage.proposal.target_type,
                "target_key": lineage.proposal.target_key,
            },
            position_size_range=position_size,
            execution_considerations=tuple(considerations),
            monitoring_triggers=tuple(monitoring),
            engine_version=lineage.trace.engine_version,
            policy_version=lineage.trace.policy_version,
            input_snapshot_timestamp=lineage.input_snapshot.captured_at.isoformat(),
            trace_id=lineage.trace.trace_id,
            proposal_version_id=lineage.proposal_version.proposal_version_id,
            summary_text=summary,
        )

    def verify_trace_integrity(self, trace_id: str) -> None:
        trace = self._trace_repository.get_trace(trace_id)
        if trace is None:
            raise MissingTraceError(f"missing trace_id: {trace_id}")
        self._validate_trace(trace)

    def compare_reconstructed_proposal_output(self, proposal_version_id: str) -> bool:
        lineage = self.reconstruct_by_proposal_version(proposal_version_id)

        action_entries = [
            row for row in lineage.trace_entries if row.entry_type.value == "ACTION_SELECTION"
        ]
        if not action_entries:
            raise TraceIntegrityError("trace missing ACTION_SELECTION entry")

        action_entry = action_entries[-1]
        trace_action = action_entry.categorical_outputs.get("action")
        trace_priority = action_entry.categorical_outputs.get("priority")

        if trace_action != lineage.proposal_version.action_proposal.action.value:
            raise ProposalMismatchError("trace action does not match proposal action")
        if trace_priority != lineage.proposal_version.priority.level.value:
            raise ProposalMismatchError("trace priority does not match proposal priority")

        return True

    def _validate_trace(self, trace: RecommendationTrace) -> None:
        if trace.trace_schema_version not in self.SUPPORTED_TRACE_SCHEMA_VERSIONS:
            raise UnsupportedTraceSchemaVersionError(
                f"unsupported trace schema version: {trace.trace_schema_version}"
            )

        if trace.execution_status.value == "FAILED":
            raise FailedTraceError(f"trace marked failed: {trace.trace_id}")

        if trace.execution_status.value != "COMPLETED":
            raise IncompleteTraceError(f"trace not completed: {trace.trace_id}")

        entries = self._trace_repository.list_entries(trace.trace_id)
        if not entries:
            raise IncompleteTraceError(f"trace has no entries: {trace.trace_id}")

        expected = 1
        seen_ids: set[str] = set()
        for row in entries:
            if row.trace_id != trace.trace_id:
                raise TraceIntegrityError("entry trace_id mismatch")
            if row.entry_id in seen_ids:
                raise TraceIntegrityError("duplicate entry_id")
            seen_ids.add(row.entry_id)
            if row.sequence_number != expected:
                raise TraceIntegrityError("entry sequence is not contiguous")
            expected += 1


def _ranked_reasons(reasons: tuple[RecommendationReason, ...], include_negative: bool) -> list[dict[str, str]]:
    limited_types = {"THESIS_CONTRADICTION", "RISK_CONTROL", "PORTFOLIO_CONSTRAINT"}
    rows: list[dict[str, str]] = []

    for reason in sorted(reasons, key=lambda row: (row.rank, row.reason_id)):
        is_negative = reason.reason_type.value in limited_types
        if include_negative != is_negative:
            continue

        detail = {}
        try:
            detail = json.loads(reason.detail_json)
        except Exception:
            detail = {}

        rows.append(
            {
                "reason_code": reason.reason_code,
                "reason_type": reason.reason_type.value,
                "weight": f"{reason.weight.value:.6f}",
                "detail": json.dumps(detail, sort_keys=True),
            }
        )

    return rows


def _material_warnings(entries: tuple[TraceEntry, ...]) -> list[dict[str, str]]:
    warning_codes: list[str] = []
    for entry in entries:
        warning_codes.extend(entry.warning_codes)

    deduped = sorted(set(warning_codes))
    return [
        {
            "code": code,
            "severity": "WARNING",
        }
        for code in deduped
    ]


def _derived_references(entries: tuple[TraceEntry, ...], reference_type: str) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for entry in entries:
        for ref in entry.output_references:
            if ref.reference_type == reference_type:
                refs.append(
                    {
                        "reference_id": ref.reference_id,
                        "source": ref.source,
                    }
                )
    refs.sort(key=lambda row: (row["reference_id"], row["source"]))
    return refs
