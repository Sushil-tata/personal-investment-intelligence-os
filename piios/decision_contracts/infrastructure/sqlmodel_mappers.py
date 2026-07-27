from __future__ import annotations

from datetime import datetime
import json

from piios.decision_contracts.domain.decision import InvestmentDecision
from piios.decision_contracts.domain.enums import (
    DecisionState,
    Priority,
    ProposalStatus,
    RuleResult,
    RuleSeverity,
    ReasonType,
    RecommendationAction,
    TraceEntryStatus,
    TraceEntryType,
    TraceExecutionStatus,
)
from piios.decision_contracts.domain.proposal import (
    RecommendationClaimLink,
    RecommendationEvidenceLink,
    RecommendationInputSnapshot,
    RecommendationProposal,
    RecommendationProposalVersion,
    RecommendationReason,
)
from piios.decision_contracts.domain.recommendation_trace import (
    ComponentResultReference,
    RecommendationTrace,
    RuleEvaluation,
    TraceEntry,
)
from piios.decision_contracts.domain.value_objects import (
    ActionProposal,
    ConfidenceBreakdown,
    PositionSizeRange,
    RecommendationConfidenceDimensions,
    RecommendationPriority,
    ReasonWeight,
)
from piios.decision_contracts.infrastructure.sqlmodel_entities import (
    InvestmentDecisionEntity,
    RecommendationClaimLinkEntity,
    RecommendationEvidenceLinkEntity,
    RecommendationInputSnapshotEntity,
    RecommendationProposalEntity,
    RecommendationProposalVersionEntity,
    RecommendationReasonEntity,
    RecommendationTraceEntity,
    RecommendationTraceEntryEntity,
)


def proposal_to_row(proposal: RecommendationProposal) -> RecommendationProposalEntity:
    return RecommendationProposalEntity(
        proposal_id=proposal.proposal_id,
        target_type=proposal.target_type,
        target_key=proposal.target_key,
        scope=proposal.scope,
        status=proposal.status.value,
        created_at=proposal.created_at.isoformat(),
        updated_at=proposal.updated_at.isoformat(),
    )


def proposal_from_row(row: RecommendationProposalEntity) -> RecommendationProposal:
    return RecommendationProposal(
        proposal_id=row.proposal_id,
        target_type=row.target_type,
        target_key=row.target_key,
        scope=row.scope,
        status=ProposalStatus(row.status),
        created_at=_parse_dt(row.created_at),
        updated_at=_parse_dt(row.updated_at),
    )


def proposal_version_to_row(version: RecommendationProposalVersion) -> RecommendationProposalVersionEntity:
    min_weight = version.action_proposal.position_size_range.min_weight if version.action_proposal.position_size_range else None
    max_weight = version.action_proposal.position_size_range.max_weight if version.action_proposal.position_size_range else None
    return RecommendationProposalVersionEntity(
        proposal_version_id=version.proposal_version_id,
        proposal_id=version.proposal_id,
        version_number=version.version_number,
        status=version.status.value,
        created_at=version.created_at.isoformat(),
        snapshot_id=version.snapshot_id,
        action=version.action_proposal.action.value,
        action_note=version.action_proposal.note,
        action_min_weight=min_weight,
        action_max_weight=max_weight,
        company_quality=version.confidence_breakdown.dimensions.company_quality,
        valuation_attractiveness=version.confidence_breakdown.dimensions.valuation_attractiveness,
        portfolio_suitability=version.confidence_breakdown.dimensions.portfolio_suitability,
        recommendation_confidence=version.confidence_breakdown.dimensions.recommendation_confidence,
        relationship_confidence=version.confidence_breakdown.dimensions.relationship_confidence,
        expected_return=version.confidence_breakdown.dimensions.expected_return,
        overall_confidence=version.confidence_breakdown.overall_confidence,
        priority_level=version.priority.level.value,
        priority_score=version.priority.score,
        required_human_review=version.required_human_review,
        supersedes_version_id=version.supersedes_version_id,
    )


def proposal_version_from_row(row: RecommendationProposalVersionEntity) -> RecommendationProposalVersion:
    position_size = None
    if row.action_min_weight is not None and row.action_max_weight is not None:
        position_size = PositionSizeRange(min_weight=row.action_min_weight, max_weight=row.action_max_weight)

    return RecommendationProposalVersion(
        proposal_version_id=row.proposal_version_id,
        proposal_id=row.proposal_id,
        version_number=row.version_number,
        status=ProposalStatus(row.status),
        created_at=_parse_dt(row.created_at),
        snapshot_id=row.snapshot_id,
        action_proposal=ActionProposal(
            action=RecommendationAction(row.action),
            position_size_range=position_size,
            note=row.action_note,
        ),
        confidence_breakdown=ConfidenceBreakdown(
            dimensions=RecommendationConfidenceDimensions(
                company_quality=row.company_quality,
                valuation_attractiveness=row.valuation_attractiveness,
                portfolio_suitability=row.portfolio_suitability,
                recommendation_confidence=row.recommendation_confidence,
                relationship_confidence=row.relationship_confidence,
                expected_return=row.expected_return,
            ),
            overall_confidence=row.overall_confidence,
        ),
        priority=RecommendationPriority(
            level=Priority(row.priority_level),
            score=row.priority_score,
        ),
        required_human_review=row.required_human_review,
        supersedes_version_id=row.supersedes_version_id,
    )


def snapshot_to_row(snapshot: RecommendationInputSnapshot) -> RecommendationInputSnapshotEntity:
    return RecommendationInputSnapshotEntity(
        snapshot_id=snapshot.snapshot_id,
        proposal_version_id=snapshot.proposal_version_id,
        captured_at=snapshot.captured_at.isoformat(),
        canonical_payload_json=snapshot.canonical_payload_json,
        input_hash=snapshot.input_hash,
    )


def snapshot_from_row(row: RecommendationInputSnapshotEntity) -> RecommendationInputSnapshot:
    return RecommendationInputSnapshot(
        snapshot_id=row.snapshot_id,
        proposal_version_id=row.proposal_version_id,
        captured_at=_parse_dt(row.captured_at),
        canonical_payload_json=row.canonical_payload_json,
        input_hash=row.input_hash,
    )


def reason_to_row(reason: RecommendationReason) -> RecommendationReasonEntity:
    return RecommendationReasonEntity(
        reason_id=reason.reason_id,
        proposal_version_id=reason.proposal_version_id,
        rank=reason.rank,
        reason_type=reason.reason_type.value,
        weight=reason.weight.value,
        reason_code=reason.reason_code,
        detail_json=reason.detail_json,
    )


def reason_from_row(row: RecommendationReasonEntity) -> RecommendationReason:
    return RecommendationReason(
        reason_id=row.reason_id,
        proposal_version_id=row.proposal_version_id,
        rank=row.rank,
        reason_type=ReasonType(row.reason_type),
        weight=ReasonWeight(row.weight),
        reason_code=row.reason_code,
        detail_json=row.detail_json,
    )


def claim_link_to_row(link: RecommendationClaimLink) -> RecommendationClaimLinkEntity:
    return RecommendationClaimLinkEntity(
        claim_link_id=link.claim_link_id,
        proposal_version_id=link.proposal_version_id,
        claim_id=link.claim_id,
        contribution_weight=link.contribution_weight.value,
        role=link.role,
    )


def claim_link_from_row(row: RecommendationClaimLinkEntity) -> RecommendationClaimLink:
    return RecommendationClaimLink(
        claim_link_id=row.claim_link_id,
        proposal_version_id=row.proposal_version_id,
        claim_id=row.claim_id,
        contribution_weight=ReasonWeight(row.contribution_weight),
        role=row.role,
    )


def evidence_link_to_row(link: RecommendationEvidenceLink) -> RecommendationEvidenceLinkEntity:
    return RecommendationEvidenceLinkEntity(
        evidence_link_id=link.evidence_link_id,
        proposal_version_id=link.proposal_version_id,
        evidence_id=link.evidence_id,
        interpretation_id=link.interpretation_id,
        freshness_days=link.freshness_days,
        quality_score=link.quality_score,
        conflict_flag=link.conflict_flag,
    )


def evidence_link_from_row(row: RecommendationEvidenceLinkEntity) -> RecommendationEvidenceLink:
    return RecommendationEvidenceLink(
        evidence_link_id=row.evidence_link_id,
        proposal_version_id=row.proposal_version_id,
        evidence_id=row.evidence_id,
        interpretation_id=row.interpretation_id,
        freshness_days=row.freshness_days,
        quality_score=row.quality_score,
        conflict_flag=row.conflict_flag,
    )


def decision_to_row(decision: InvestmentDecision) -> InvestmentDecisionEntity:
    modified_action = decision.modified_action.action.value if decision.modified_action else None
    modified_action_note = decision.modified_action.note if decision.modified_action else None
    modified_action_min = (
        decision.modified_action.position_size_range.min_weight
        if decision.modified_action and decision.modified_action.position_size_range
        else None
    )
    modified_action_max = (
        decision.modified_action.position_size_range.max_weight
        if decision.modified_action and decision.modified_action.position_size_range
        else None
    )
    modified_position_min = decision.modified_position_size.min_weight if decision.modified_position_size else None
    modified_position_max = decision.modified_position_size.max_weight if decision.modified_position_size else None

    return InvestmentDecisionEntity(
        decision_id=decision.decision_id,
        proposal_version_id=decision.proposal_version_id,
        state=decision.state.value,
        reason_code=decision.reason_code,
        decided_at=decision.decided_at.isoformat(),
        reason_text=decision.reason_text,
        decided_by=decision.decided_by,
        preferred_alternative_target_key=decision.preferred_alternative_target_key,
        modified_action=modified_action,
        modified_action_note=modified_action_note,
        modified_action_min_weight=modified_action_min,
        modified_action_max_weight=modified_action_max,
        modified_position_min_weight=modified_position_min,
        modified_position_max_weight=modified_position_max,
    )


def decision_from_row(row: InvestmentDecisionEntity) -> InvestmentDecision:
    modified_action = None
    if row.modified_action is not None:
        position_size = None
        if row.modified_action_min_weight is not None and row.modified_action_max_weight is not None:
            position_size = PositionSizeRange(
                min_weight=row.modified_action_min_weight,
                max_weight=row.modified_action_max_weight,
            )
        modified_action = ActionProposal(
            action=RecommendationAction(row.modified_action),
            position_size_range=position_size,
            note=row.modified_action_note,
        )

    modified_position = None
    if row.modified_position_min_weight is not None and row.modified_position_max_weight is not None:
        modified_position = PositionSizeRange(
            min_weight=row.modified_position_min_weight,
            max_weight=row.modified_position_max_weight,
        )

    return InvestmentDecision(
        decision_id=row.decision_id,
        proposal_version_id=row.proposal_version_id,
        state=DecisionState(row.state),
        reason_code=row.reason_code,
        decided_at=_parse_dt(row.decided_at),
        reason_text=row.reason_text,
        decided_by=row.decided_by,
        preferred_alternative_target_key=row.preferred_alternative_target_key,
        modified_action=modified_action,
        modified_position_size=modified_position,
    )


def trace_to_row(trace: RecommendationTrace) -> RecommendationTraceEntity:
    return RecommendationTraceEntity(
        trace_id=trace.trace_id,
        proposal_id=trace.proposal_id,
        proposal_version_id=trace.proposal_version_id,
        input_snapshot_id=trace.input_snapshot_id,
        engine_name=trace.engine_name,
        engine_version=trace.engine_version,
        policy_version=trace.policy_version,
        strategy_version=trace.strategy_version,
        execution_identity=trace.execution_identity,
        computation_started_at=trace.computation_started_at.isoformat(),
        computation_completed_at=trace.computation_completed_at.isoformat(),
        trace_schema_version=trace.trace_schema_version,
        execution_status=trace.execution_status.value,
        is_authoritative=trace.is_authoritative,
        created_at=trace.created_at.isoformat(),
    )


def trace_from_row(row: RecommendationTraceEntity, entries: list[TraceEntry]) -> RecommendationTrace:
    return RecommendationTrace(
        trace_id=row.trace_id,
        proposal_id=row.proposal_id,
        proposal_version_id=row.proposal_version_id,
        input_snapshot_id=row.input_snapshot_id,
        engine_name=row.engine_name,
        engine_version=row.engine_version,
        policy_version=row.policy_version,
        strategy_version=row.strategy_version,
        execution_identity=row.execution_identity,
        computation_started_at=_parse_dt(row.computation_started_at),
        computation_completed_at=_parse_dt(row.computation_completed_at),
        trace_schema_version=row.trace_schema_version,
        execution_status=TraceExecutionStatus(row.execution_status),
        is_authoritative=row.is_authoritative,
        entries=tuple(entries),
        created_at=_parse_dt(row.created_at),
    )


def trace_entry_to_row(entry: TraceEntry) -> RecommendationTraceEntryEntity:
    return RecommendationTraceEntryEntity(
        entry_id=entry.entry_id,
        trace_id=entry.trace_id,
        sequence_number=entry.sequence_number,
        entry_type=entry.entry_type.value,
        component_name=entry.component_name,
        component_version=entry.component_version,
        status=entry.status.value,
        input_references_json=json.dumps([row.deterministic_dict() for row in entry.input_references], sort_keys=True),
        output_references_json=json.dumps([row.deterministic_dict() for row in entry.output_references], sort_keys=True),
        rule_evaluations_json=json.dumps([row.deterministic_dict() for row in entry.rule_evaluations], sort_keys=True),
        numeric_outputs_json=json.dumps(entry.numeric_outputs, sort_keys=True),
        categorical_outputs_json=json.dumps(entry.categorical_outputs, sort_keys=True),
        warning_codes_json=json.dumps(list(entry.warning_codes), sort_keys=True),
        created_at=entry.created_at.isoformat(),
    )


def trace_entry_from_row(row: RecommendationTraceEntryEntity) -> TraceEntry:
    input_references = tuple(
        ComponentResultReference(
            reference_type=item["reference_type"],
            reference_id=item["reference_id"],
            source=item["source"],
        )
        for item in json.loads(row.input_references_json)
    )
    output_references = tuple(
        ComponentResultReference(
            reference_type=item["reference_type"],
            reference_id=item["reference_id"],
            source=item["source"],
        )
        for item in json.loads(row.output_references_json)
    )
    rule_evaluations = tuple(
        RuleEvaluation(
            rule_id=item["rule_id"],
            rule_version=item["rule_version"],
            rule_name=item["rule_name"],
            result=RuleResult(item["result"]),
            observed_value=item["observed_value"],
            comparison_operator=item["comparison_operator"],
            threshold_value=item["threshold_value"],
            reason_code=item["reason_code"],
            severity=RuleSeverity(item["severity"]),
            source_reference=item["source_reference"],
        )
        for item in json.loads(row.rule_evaluations_json)
    )
    return TraceEntry(
        entry_id=row.entry_id,
        trace_id=row.trace_id,
        sequence_number=row.sequence_number,
        entry_type=TraceEntryType(row.entry_type),
        component_name=row.component_name,
        component_version=row.component_version,
        status=TraceEntryStatus(row.status),
        input_references=input_references,
        output_references=output_references,
        rule_evaluations=rule_evaluations,
        numeric_outputs={key: float(value) for key, value in json.loads(row.numeric_outputs_json).items()},
        categorical_outputs={key: str(value) for key, value in json.loads(row.categorical_outputs_json).items()},
        warning_codes=tuple(str(value) for value in json.loads(row.warning_codes_json)),
        created_at=_parse_dt(row.created_at),
    )


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)
