from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from piios.decision_contracts.application.scoring_components import (
    ComponentOrientation,
    ComponentScore,
    RecommendationEngineInput,
    ScoringComponent,
    default_scoring_components,
)
from piios.decision_contracts.application.strategies import (
    StrategyResult,
    WeightedComponentScore,
    WeightedRecommendationStrategy,
    default_recommendation_strategies,
)
from piios.decision_contracts.domain.enums import ProposalStatus, ReasonType
from piios.decision_contracts.domain.proposal import (
    RecommendationClaimLink,
    RecommendationEvidenceLink,
    RecommendationInputSnapshot,
    RecommendationProposal,
    RecommendationProposalVersion,
    RecommendationReason,
)
from piios.decision_contracts.domain.value_objects import (
    ActionProposal,
    ConfidenceBreakdown,
    PositionSizeRange,
    RecommendationConfidenceDimensions,
    RecommendationPriority,
    ReasonWeight,
)
from piios.decision_contracts.infrastructure.repository_protocols import (
    RecommendationProposalRepositoryProtocol,
    RecommendationProposalVersionRepositoryProtocol,
    RecommendationReasonRepositoryProtocol,
    RecommendationSnapshotRepositoryProtocol,
    RecommendationTraceRepositoryProtocol,
)
from piios.thesis.domain.claims import InterpretationRelation


@dataclass(frozen=True)
class RecommendationExplanation:
    recommendation: str
    overall_score: int
    drivers: tuple[str, ...]
    warnings: tuple[str, ...]
    recommendation_confidence: str
    strategy_key: str
    component_breakdown: tuple[WeightedComponentScore, ...]


@dataclass(frozen=True)
class RecommendationDecisionTrace:
    input_hash: str
    canonical_payload_json: str
    component_scores: tuple[ComponentScore, ...]
    applied_rules: tuple[str, ...]
    final_score: float
    final_recommendation: str
    explanation: RecommendationExplanation
    generated_at: datetime
    engine_version: str


@dataclass(frozen=True)
class RecommendationEvaluation:
    component_scores: tuple[ComponentScore, ...]
    strategy_result: StrategyResult
    confidence_breakdown: ConfidenceBreakdown
    explanation: RecommendationExplanation
    trace: RecommendationDecisionTrace


@dataclass(frozen=True)
class RecommendationGenerationResult:
    proposal: RecommendationProposal
    proposal_version: RecommendationProposalVersion
    input_snapshot: RecommendationInputSnapshot
    reasons: tuple[RecommendationReason, ...]
    claim_links: tuple[RecommendationClaimLink, ...]
    evidence_links: tuple[RecommendationEvidenceLink, ...]
    evaluation: RecommendationEvaluation


class RecommendationDecisionEngine:
    def __init__(
        self,
        proposal_repository: RecommendationProposalRepositoryProtocol,
        version_repository: RecommendationProposalVersionRepositoryProtocol,
        snapshot_repository: RecommendationSnapshotRepositoryProtocol,
        reason_repository: RecommendationReasonRepositoryProtocol,
        trace_repository: RecommendationTraceRepositoryProtocol,
        scoring_components: tuple[ScoringComponent, ...] | None = None,
        strategies: dict[str, WeightedRecommendationStrategy] | None = None,
        default_strategy_key: str = "balanced-v1",
        engine_version: str = "wave2b-m3-v1",
    ) -> None:
        self._proposal_repository = proposal_repository
        self._version_repository = version_repository
        self._snapshot_repository = snapshot_repository
        self._reason_repository = reason_repository
        self._trace_repository = trace_repository
        self._scoring_components = scoring_components or default_scoring_components()
        self._strategies = strategies or default_recommendation_strategies()
        self._default_strategy_key = default_strategy_key
        self._engine_version = engine_version

    def evaluate(self, data: RecommendationEngineInput) -> RecommendationEvaluation:
        scores = tuple(component.score(data) for component in self._scoring_components)
        strategy = self._resolve_strategy(data.strategy_key)
        strategy_result = strategy.evaluate(data, scores)
        confidence = self._build_confidence_breakdown(data, scores, strategy_result)
        explanation = _build_explanation(strategy_result)

        trace_payload = _canonical_trace_payload(
            data=data,
            scores=scores,
            strategy_result=strategy_result,
            confidence=confidence,
            explanation=explanation,
            engine_version=self._engine_version,
            strategy_governance={
                "strategy_key": strategy.strategy_key,
                "strategy_hash": strategy.governance_hash(),
                "strategy_profile": strategy.governance_profile(),
            },
        )
        trace_json = json.dumps(trace_payload, sort_keys=True, separators=(",", ":"))
        trace_hash = hashlib.sha256(trace_json.encode("utf-8")).hexdigest()

        trace = RecommendationDecisionTrace(
            input_hash=trace_hash,
            canonical_payload_json=trace_json,
            component_scores=scores,
            applied_rules=strategy_result.applied_rules,
            final_score=strategy_result.overall_score,
            final_recommendation=strategy_result.action.value,
            explanation=explanation,
            generated_at=data.generated_at,
            engine_version=self._engine_version,
        )

        return RecommendationEvaluation(
            component_scores=scores,
            strategy_result=strategy_result,
            confidence_breakdown=confidence,
            explanation=explanation,
            trace=trace,
        )

    def generate_recommendation(self, data: RecommendationEngineInput) -> RecommendationGenerationResult:
        evaluation = self.evaluate(data)

        proposal = self._proposal_repository.get(data.proposal_id)
        if proposal is None:
            proposal = self._proposal_repository.create(
                RecommendationProposal(
                    proposal_id=data.proposal_id,
                    target_type=data.target_type,
                    target_key=data.target_key,
                    scope=data.scope,
                    status=ProposalStatus.ACTIVE,
                    created_at=data.generated_at,
                    updated_at=data.generated_at,
                )
            )

        existing_version, existing_snapshot = self._find_existing_snapshot_by_hash(
            proposal_id=data.proposal_id,
            input_hash=evaluation.trace.input_hash,
        )
        if existing_version is not None and existing_snapshot is not None:
            return RecommendationGenerationResult(
                proposal=proposal,
                proposal_version=existing_version,
                input_snapshot=existing_snapshot,
                reasons=tuple(self._reason_repository.list_for_proposal_version(existing_version.proposal_version_id)),
                claim_links=tuple(self._trace_repository.list_claim_links(existing_version.proposal_version_id)),
                evidence_links=tuple(self._trace_repository.list_evidence_links(existing_version.proposal_version_id)),
                evaluation=evaluation,
            )

        latest = self._version_repository.get_latest(data.proposal_id)
        version_number = (latest.version_number + 1) if latest else 1
        proposal_version_id = f"{data.proposal_id}:v{version_number}"
        snapshot_id = f"{data.proposal_id}:snap:v{version_number}"

        version = self._version_repository.create(
            RecommendationProposalVersion(
                proposal_version_id=proposal_version_id,
                proposal_id=data.proposal_id,
                version_number=version_number,
                status=ProposalStatus.ACTIVE,
                created_at=data.generated_at,
                snapshot_id=snapshot_id,
                action_proposal=ActionProposal(
                    action=evaluation.strategy_result.action,
                    position_size_range=evaluation.strategy_result.position_size_range,
                    note=(
                        f"strategy={evaluation.strategy_result.strategy_key};"
                        f" score={evaluation.strategy_result.overall_score:.6f}"
                    ),
                ),
                confidence_breakdown=evaluation.confidence_breakdown,
                priority=evaluation.strategy_result.priority,
                required_human_review=evaluation.strategy_result.required_human_review,
                supersedes_version_id=latest.proposal_version_id if latest else None,
            )
        )

        snapshot = self._snapshot_repository.create(
            RecommendationInputSnapshot(
                snapshot_id=snapshot_id,
                proposal_version_id=proposal_version_id,
                captured_at=data.generated_at,
                canonical_payload_json=evaluation.trace.canonical_payload_json,
                input_hash=evaluation.trace.input_hash,
            )
        )

        reasons = _build_reasons(
            proposal_version_id=proposal_version_id,
            component_breakdown=evaluation.strategy_result.component_breakdown,
            explanation=evaluation.explanation,
        )
        if reasons:
            self._reason_repository.create_many(reasons)

        claim_links = _build_claim_links(data, proposal_version_id)
        if claim_links:
            self._trace_repository.create_claim_links(claim_links)

        evidence_links = _build_evidence_links(data, proposal_version_id)
        if evidence_links:
            self._trace_repository.create_evidence_links(evidence_links)

        return RecommendationGenerationResult(
            proposal=proposal,
            proposal_version=version,
            input_snapshot=snapshot,
            reasons=reasons,
            claim_links=claim_links,
            evidence_links=evidence_links,
            evaluation=evaluation,
        )

    def _find_existing_snapshot_by_hash(
        self,
        proposal_id: str,
        input_hash: str,
    ) -> tuple[RecommendationProposalVersion | None, RecommendationInputSnapshot | None]:
        versions = self._version_repository.list_for_proposal(proposal_id)
        for version in reversed(versions):
            snapshot = self._snapshot_repository.get_for_proposal_version(version.proposal_version_id)
            if snapshot is None:
                continue
            if snapshot.input_hash == input_hash:
                return version, snapshot
        return None, None

    def _resolve_strategy(self, strategy_key: str) -> WeightedRecommendationStrategy:
        strategy = self._strategies.get(strategy_key)
        if strategy is None:
            available = ", ".join(sorted(self._strategies.keys()))
            raise ValueError(
                f"unknown strategy_key: {strategy_key}. configured strategies: {available}"
            )
        return strategy

    def _build_confidence_breakdown(
        self,
        data: RecommendationEngineInput,
        scores: tuple[ComponentScore, ...],
        strategy_result: StrategyResult,
    ) -> ConfidenceBreakdown:
        score_map = {row.component_key: row for row in scores}
        portfolio_suitability = score_map["portfolio_alignment_score"].value
        recommendation_confidence = (
            score_map["health_score"].value
            + score_map["confidence_score"].value
            + score_map["evidence_quality_score"].value
            + score_map["evidence_freshness_score"].value
        ) / 4.0

        dimensions = RecommendationConfidenceDimensions(
            company_quality=round(score_map["evidence_quality_score"].value, 6),
            valuation_attractiveness=round(data.portfolio_context.valuation_signal, 6),
            portfolio_suitability=round(portfolio_suitability, 6),
            recommendation_confidence=round(recommendation_confidence, 6),
            relationship_confidence=round(data.portfolio_context.relationship_signal, 6),
            expected_return=round(data.portfolio_context.expected_return_signal, 6),
        )

        overall = round(
            (
                dimensions.company_quality
                + dimensions.valuation_attractiveness
                + dimensions.portfolio_suitability
                + dimensions.recommendation_confidence
                + dimensions.relationship_confidence
                + dimensions.expected_return
            )
            / 6.0,
            6,
        )

        # Penalize confidence when contradiction/risk penalties are high.
        contradiction_penalty = score_map["contradiction_penalty"].value
        risk_penalty = score_map["risk_penalty"].value
        adjusted = max(overall - (0.2 * contradiction_penalty) - (0.15 * risk_penalty), 0.0)

        if strategy_result.required_human_review:
            adjusted = min(adjusted, 0.79)

        return ConfidenceBreakdown(dimensions=dimensions, overall_confidence=round(adjusted, 6))


def _build_explanation(strategy_result: StrategyResult) -> RecommendationExplanation:
    drivers: list[str] = []
    warnings: list[str] = []

    for row in strategy_result.component_breakdown:
        if row.contribution >= 0.09:
            drivers.append(_driver_label(row))
        if row.orientation == ComponentOrientation.PENALTY and row.value >= 0.45:
            warnings.append(_warning_label(row))

    if not drivers:
        drivers.append("Balanced evidence profile with moderate support")
    if not warnings:
        warnings.append("No material warning triggered by configured penalty thresholds")

    return RecommendationExplanation(
        recommendation=strategy_result.action.value,
        overall_score=int(round(strategy_result.overall_score * 100, 0)),
        drivers=tuple(drivers[:4]),
        warnings=tuple(warnings[:4]),
        recommendation_confidence=strategy_result.confidence_label,
        strategy_key=strategy_result.strategy_key,
        component_breakdown=strategy_result.component_breakdown,
    )


def _driver_label(row: WeightedComponentScore) -> str:
    label_map = {
        "health_score": "High thesis health",
        "confidence_score": "Strong consistency and provenance confidence",
        "evidence_quality_score": "High evidence quality",
        "evidence_freshness_score": "Recent supporting evidence",
        "portfolio_alignment_score": "Portfolio context supports action",
        "opportunity_bonus": "Opportunity and valuation signals are constructive",
    }
    return label_map.get(row.component_key, f"Positive contribution from {row.component_key}")


def _warning_label(row: WeightedComponentScore) -> str:
    label_map = {
        "contradiction_penalty": "Emerging contradiction against thesis",
        "risk_penalty": "Portfolio or liquidity risk constraints are elevated",
    }
    return label_map.get(row.component_key, f"Risk warning from {row.component_key}")


def _canonical_trace_payload(
    data: RecommendationEngineInput,
    scores: tuple[ComponentScore, ...],
    strategy_result: StrategyResult,
    confidence: ConfidenceBreakdown,
    explanation: RecommendationExplanation,
    engine_version: str,
    strategy_governance: dict[str, object],
) -> dict[str, object]:
    claims = sorted(
        [
            {
                "claim_id": row.claim_id,
                "claim_key": row.claim_key,
                "claim_type": row.claim_type,
                "status": row.status.value,
            }
            for row in data.claims
            if row.thesis_version_id == data.thesis_version_id
        ],
        key=lambda row: (row["claim_id"], row["claim_key"]),
    )

    evidence = sorted(
        [
            {
                "evidence_id": row.evidence_id,
                "source_id": row.source_id,
                "as_of_date": row.as_of_date or "",
            }
            for row in data.evidence_items
        ],
        key=lambda row: row["evidence_id"],
    )

    interpretations = sorted(
        [
            {
                "interpretation_id": row.interpretation_id,
                "claim_id": row.claim_id,
                "evidence_id": row.evidence_id,
                "relation": row.relation.value,
                "strength": row.strength,
            }
            for row in data.interpretations
            if row.effective_to is None
        ],
        key=lambda row: (row["claim_id"], row["evidence_id"], row["interpretation_id"]),
    )

    component_scores = [
        {
            "component_key": row.component_key,
            "orientation": row.orientation.value,
            "value": _r6(row.value),
            "reason_code": row.reason_code,
            "detail": {key: str(value) for key, value in sorted(row.detail.items(), key=lambda item: item[0])},
        }
        for row in sorted(scores, key=lambda item: item.component_key)
    ]

    return {
        "engine_version": engine_version,
        "proposal": {
            "proposal_id": data.proposal_id,
            "target_type": data.target_type,
            "target_key": data.target_key,
            "scope": data.scope,
            "strategy_key": data.strategy_key,
        },
        "strategy_governance": strategy_governance,
        "generated_at": _canonical_timestamp(data.generated_at),
        "metadata": {key: str(value) for key, value in sorted(data.metadata.items(), key=lambda item: item[0])},
        "thesis_health": {
            "thesis_version_id": data.thesis_health_snapshot.thesis_version_id,
            "computation_version": data.thesis_health_snapshot.computation_version,
            "computed_at": _canonical_timestamp(data.thesis_health_snapshot.computed_at),
            "evidence_freshness": _r6(data.thesis_health_snapshot.evidence_freshness),
            "evidence_quality": _r6(data.thesis_health_snapshot.evidence_quality),
            "supporting_strength": _r6(data.thesis_health_snapshot.supporting_strength),
            "contradictory_strength": _r6(data.thesis_health_snapshot.contradictory_strength),
            "provenance_completeness": _r6(data.thesis_health_snapshot.provenance_completeness),
            "thesis_health_index": _r6(data.thesis_health_snapshot.thesis_health_index),
        },
        "portfolio_context": {
            "has_existing_position": data.portfolio_context.has_existing_position,
            "current_weight": _r6(data.portfolio_context.current_weight),
            "target_weight": _r6(data.portfolio_context.target_weight),
            "max_position_weight": _r6(data.portfolio_context.max_position_weight),
            "concentration_risk": _r6(data.portfolio_context.concentration_risk),
            "liquidity_risk": _r6(data.portfolio_context.liquidity_risk),
            "portfolio_underweight_signal": _r6(data.portfolio_context.portfolio_underweight_signal),
            "opportunity_signal": _r6(data.portfolio_context.opportunity_signal),
            "valuation_signal": _r6(data.portfolio_context.valuation_signal),
            "expected_return_signal": _r6(data.portfolio_context.expected_return_signal),
            "relationship_signal": _r6(data.portfolio_context.relationship_signal),
        },
        "claims": claims,
        "evidence": evidence,
        "interpretations": interpretations,
        "component_scores": component_scores,
        "strategy_result": {
            "strategy_key": strategy_result.strategy_key,
            "overall_score": _r6(strategy_result.overall_score),
            "action": strategy_result.action.value,
            "position_size_range": (
                {
                    "min_weight": _r6(strategy_result.position_size_range.min_weight),
                    "max_weight": _r6(strategy_result.position_size_range.max_weight),
                }
                if strategy_result.position_size_range
                else None
            ),
            "priority": {
                "level": strategy_result.priority.level.value,
                "score": _r6(strategy_result.priority.score),
            },
            "confidence_label": strategy_result.confidence_label,
            "required_human_review": strategy_result.required_human_review,
            "applied_rules": list(strategy_result.applied_rules),
            "component_breakdown": [
                {
                    "component_key": row.component_key,
                    "weight": _r6(row.weight),
                    "value": _r6(row.value),
                    "normalized_value": _r6(row.normalized_value),
                    "contribution": _r6(row.contribution),
                    "orientation": row.orientation.value,
                }
                for row in strategy_result.component_breakdown
            ],
        },
        "confidence_breakdown": {
            "company_quality": _r6(confidence.dimensions.company_quality),
            "valuation_attractiveness": _r6(confidence.dimensions.valuation_attractiveness),
            "portfolio_suitability": _r6(confidence.dimensions.portfolio_suitability),
            "recommendation_confidence": _r6(confidence.dimensions.recommendation_confidence),
            "relationship_confidence": _r6(confidence.dimensions.relationship_confidence),
            "expected_return": _r6(confidence.dimensions.expected_return),
            "overall_confidence": _r6(confidence.overall_confidence),
        },
        "explanation": {
            "recommendation": explanation.recommendation,
            "overall_score": explanation.overall_score,
            "drivers": list(explanation.drivers),
            "warnings": list(explanation.warnings),
            "recommendation_confidence": explanation.recommendation_confidence,
            "strategy_key": explanation.strategy_key,
        },
    }


def _canonical_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _r6(value: float) -> float:
    return round(float(value), 6)


def _build_reasons(
    proposal_version_id: str,
    component_breakdown: tuple[WeightedComponentScore, ...],
    explanation: RecommendationExplanation,
) -> tuple[RecommendationReason, ...]:
    reasons: list[RecommendationReason] = []

    for rank, row in enumerate(component_breakdown[:6], start=1):
        if row.weight <= 0.0:
            continue
        reason_type = _reason_type_for_component(row.component_key, row.orientation)
        reason = RecommendationReason(
            reason_id=f"{proposal_version_id}:reason:{rank}",
            proposal_version_id=proposal_version_id,
            rank=rank,
            reason_type=reason_type,
            weight=ReasonWeight(round(min(max(row.contribution, 0.0), 1.0), 6)),
            reason_code=row.component_key.upper(),
            detail_json=json.dumps(
                {
                    "value": row.value,
                    "weight": row.weight,
                    "normalized_value": row.normalized_value,
                    "contribution": row.contribution,
                },
                sort_keys=True,
            ),
        )
        reasons.append(reason)

    summary = RecommendationReason(
        reason_id=f"{proposal_version_id}:reason:summary",
        proposal_version_id=proposal_version_id,
        rank=len(reasons) + 1,
        reason_type=ReasonType.MONITORING,
        weight=ReasonWeight(min(max(explanation.overall_score / 100.0, 0.0), 1.0)),
        reason_code="RECOMMENDATION_EXPLANATION",
        detail_json=json.dumps(
            {
                "recommendation": explanation.recommendation,
                "overall_score": explanation.overall_score,
                "drivers": list(explanation.drivers),
                "warnings": list(explanation.warnings),
                "confidence": explanation.recommendation_confidence,
            },
            sort_keys=True,
        ),
    )
    reasons.append(summary)

    return tuple(reasons)


def _reason_type_for_component(component_key: str, orientation: ComponentOrientation) -> ReasonType:
    if component_key in {"health_score", "confidence_score"}:
        return ReasonType.THESIS_SUPPORT if orientation == ComponentOrientation.BENEFIT else ReasonType.THESIS_CONTRADICTION
    if component_key in {"evidence_quality_score", "evidence_freshness_score"}:
        return ReasonType.DATA_QUALITY
    if component_key == "portfolio_alignment_score":
        return ReasonType.PORTFOLIO_CONSTRAINT
    if component_key == "risk_penalty":
        return ReasonType.RISK_CONTROL
    if component_key == "opportunity_bonus":
        return ReasonType.OPPORTUNITY_SIGNAL
    if component_key == "contradiction_penalty":
        return ReasonType.THESIS_CONTRADICTION
    return ReasonType.MONITORING


def _build_claim_links(
    data: RecommendationEngineInput,
    proposal_version_id: str,
) -> tuple[RecommendationClaimLink, ...]:
    interpretations = [row for row in data.interpretations if row.effective_to is None]
    by_claim: dict[str, list[str]] = {}
    for row in interpretations:
        by_claim.setdefault(row.claim_id, []).append(row.relation.value)

    links: list[RecommendationClaimLink] = []
    claim_rows = [row for row in data.claims if row.thesis_version_id == data.thesis_version_id]
    claim_rows = sorted(claim_rows, key=lambda row: row.claim_id)

    for idx, claim in enumerate(claim_rows, start=1):
        relations = by_claim.get(claim.claim_id, [])
        supports = sum(1 for relation in relations if relation == InterpretationRelation.SUPPORTS.value)
        contradicts = sum(1 for relation in relations if relation == InterpretationRelation.CONTRADICTS.value)
        total = supports + contradicts
        if total == 0:
            weight = 0.5
            role = "neutral"
        elif supports > contradicts:
            weight = supports / total
            role = "supporting"
        elif contradicts > supports:
            weight = contradicts / total
            role = "contradicting"
        else:
            weight = 0.5
            role = "mixed"

        links.append(
            RecommendationClaimLink(
                claim_link_id=f"{proposal_version_id}:claim:{idx}",
                proposal_version_id=proposal_version_id,
                claim_id=claim.claim_id,
                contribution_weight=ReasonWeight(round(min(max(weight, 0.0), 1.0), 6)),
                role=role,
            )
        )

    return tuple(links)


def _build_evidence_links(
    data: RecommendationEngineInput,
    proposal_version_id: str,
) -> tuple[RecommendationEvidenceLink, ...]:
    active = [row for row in data.interpretations if row.effective_to is None]
    relations_by_evidence: dict[str, set[InterpretationRelation]] = {}
    interp_id_by_evidence: dict[str, str] = {}
    for row in active:
        relations_by_evidence.setdefault(row.evidence_id, set()).add(row.relation)
        interp_id_by_evidence.setdefault(row.evidence_id, row.interpretation_id)

    links: list[RecommendationEvidenceLink] = []
    evidence_rows = sorted(data.evidence_items, key=lambda row: row.evidence_id)

    for idx, evidence in enumerate(evidence_rows, start=1):
        freshness_days = _freshness_days(evidence=evidence, generated_at=data.generated_at)
        quality_score = _quality_score(evidence.metadata_json)
        relation_set = relations_by_evidence.get(evidence.evidence_id, set())
        conflict_flag = (
            InterpretationRelation.SUPPORTS in relation_set
            and InterpretationRelation.CONTRADICTS in relation_set
        )

        links.append(
            RecommendationEvidenceLink(
                evidence_link_id=f"{proposal_version_id}:evidence:{idx}",
                proposal_version_id=proposal_version_id,
                evidence_id=evidence.evidence_id,
                interpretation_id=interp_id_by_evidence.get(evidence.evidence_id),
                freshness_days=freshness_days,
                quality_score=quality_score,
                conflict_flag=conflict_flag,
            )
        )

    return tuple(links)


def _freshness_days(evidence, generated_at: datetime) -> int:
    if evidence.as_of_date:
        as_of_raw = evidence.as_of_date
        if len(as_of_raw) == 10:
            as_of_raw = f"{as_of_raw}T00:00:00+00:00"
        as_of = datetime.fromisoformat(as_of_raw)
    else:
        as_of = evidence.created_at
    age_days = (generated_at - as_of).days
    return max(age_days, 0)


def _quality_score(metadata_json: str) -> float:
    try:
        payload = json.loads(metadata_json)
    except Exception:
        return 0.5

    raw = payload.get("quality_score")
    if raw is None:
        return 0.5
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.5
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return round(value, 6)
