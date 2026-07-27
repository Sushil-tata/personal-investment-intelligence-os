from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol

from piios.thesis.domain.claims import ClaimEvidenceInterpretation, InterpretationRelation, ThesisClaim
from piios.thesis.domain.evidence import EvidenceItem
from piios.thesis_health.domain.entities import ThesisHealthSnapshot


class ComponentOrientation(str, Enum):
    BENEFIT = "BENEFIT"
    PENALTY = "PENALTY"


@dataclass(frozen=True)
class PortfolioContextSnapshot:
    has_existing_position: bool
    current_weight: float
    target_weight: float
    max_position_weight: float
    concentration_risk: float = 0.0
    liquidity_risk: float = 0.0
    portfolio_underweight_signal: float = 0.5
    opportunity_signal: float = 0.5
    valuation_signal: float = 0.5
    expected_return_signal: float = 0.5
    relationship_signal: float = 0.5

    def __post_init__(self) -> None:
        _assert_unit_interval("current_weight", self.current_weight)
        _assert_unit_interval("target_weight", self.target_weight)
        _assert_unit_interval("max_position_weight", self.max_position_weight)
        _assert_unit_interval("concentration_risk", self.concentration_risk)
        _assert_unit_interval("liquidity_risk", self.liquidity_risk)
        _assert_unit_interval("portfolio_underweight_signal", self.portfolio_underweight_signal)
        _assert_unit_interval("opportunity_signal", self.opportunity_signal)
        _assert_unit_interval("valuation_signal", self.valuation_signal)
        _assert_unit_interval("expected_return_signal", self.expected_return_signal)
        _assert_unit_interval("relationship_signal", self.relationship_signal)


@dataclass(frozen=True)
class RecommendationEngineInput:
    proposal_id: str
    target_type: str
    target_key: str
    scope: str
    thesis_version_id: str
    generated_at: datetime
    thesis_health_snapshot: ThesisHealthSnapshot
    claims: tuple[ThesisClaim, ...]
    evidence_items: tuple[EvidenceItem, ...]
    interpretations: tuple[ClaimEvidenceInterpretation, ...]
    portfolio_context: PortfolioContextSnapshot
    strategy_key: str = "balanced-v1"
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name, value in (
            ("proposal_id", self.proposal_id),
            ("target_type", self.target_type),
            ("target_key", self.target_key),
            ("scope", self.scope),
            ("thesis_version_id", self.thesis_version_id),
            ("strategy_key", self.strategy_key),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} must not be empty")


@dataclass(frozen=True)
class ComponentScore:
    component_key: str
    label: str
    orientation: ComponentOrientation
    value: float
    reason_code: str
    detail: dict[str, str]

    def __post_init__(self) -> None:
        if not self.component_key.strip():
            raise ValueError("component_key must not be empty")
        if not self.label.strip():
            raise ValueError("label must not be empty")
        if not self.reason_code.strip():
            raise ValueError("reason_code must not be empty")
        _assert_unit_interval("value", self.value)


class ScoringComponent(Protocol):
    component_key: str
    label: str
    orientation: ComponentOrientation
    reason_code: str

    def score(self, data: RecommendationEngineInput) -> ComponentScore:
        ...


class HealthScoreComponent:
    component_key = "health_score"
    label = "Health Score"
    orientation = ComponentOrientation.BENEFIT
    reason_code = "THESIS_HEALTH_INDEX"

    def score(self, data: RecommendationEngineInput) -> ComponentScore:
        value = round(data.thesis_health_snapshot.thesis_health_index, 6)
        return ComponentScore(
            component_key=self.component_key,
            label=self.label,
            orientation=self.orientation,
            value=value,
            reason_code=self.reason_code,
            detail={"thesis_health_index": f"{value:.6f}"},
        )


class ConfidenceScoreComponent:
    component_key = "confidence_score"
    label = "Confidence Score"
    orientation = ComponentOrientation.BENEFIT
    reason_code = "CONFIDENCE_COMPOSITE"

    def score(self, data: RecommendationEngineInput) -> ComponentScore:
        active = [row for row in data.interpretations if row.effective_to is None]
        contradictory = [row for row in active if row.relation == InterpretationRelation.CONTRADICTS]
        contradiction_ratio = len(contradictory) / len(active) if active else 0.0
        claim_consistency = 1.0 - contradiction_ratio
        raw = (
            data.thesis_health_snapshot.supporting_strength
            + data.thesis_health_snapshot.provenance_completeness
            + claim_consistency
        ) / 3.0
        value = round(_clamp(raw), 6)
        return ComponentScore(
            component_key=self.component_key,
            label=self.label,
            orientation=self.orientation,
            value=value,
            reason_code=self.reason_code,
            detail={
                "supporting_strength": f"{data.thesis_health_snapshot.supporting_strength:.6f}",
                "provenance_completeness": f"{data.thesis_health_snapshot.provenance_completeness:.6f}",
                "claim_consistency": f"{claim_consistency:.6f}",
            },
        )


class EvidenceQualityScoreComponent:
    component_key = "evidence_quality_score"
    label = "Evidence Quality Score"
    orientation = ComponentOrientation.BENEFIT
    reason_code = "EVIDENCE_QUALITY"

    def score(self, data: RecommendationEngineInput) -> ComponentScore:
        value = round(data.thesis_health_snapshot.evidence_quality, 6)
        return ComponentScore(
            component_key=self.component_key,
            label=self.label,
            orientation=self.orientation,
            value=value,
            reason_code=self.reason_code,
            detail={"evidence_quality": f"{value:.6f}"},
        )


class EvidenceFreshnessScoreComponent:
    component_key = "evidence_freshness_score"
    label = "Evidence Freshness Score"
    orientation = ComponentOrientation.BENEFIT
    reason_code = "EVIDENCE_FRESHNESS"

    def score(self, data: RecommendationEngineInput) -> ComponentScore:
        value = round(data.thesis_health_snapshot.evidence_freshness, 6)
        return ComponentScore(
            component_key=self.component_key,
            label=self.label,
            orientation=self.orientation,
            value=value,
            reason_code=self.reason_code,
            detail={"evidence_freshness": f"{value:.6f}"},
        )


class ContradictionPenaltyComponent:
    component_key = "contradiction_penalty"
    label = "Contradiction Penalty"
    orientation = ComponentOrientation.PENALTY
    reason_code = "THESIS_CONTRADICTION"

    def score(self, data: RecommendationEngineInput) -> ComponentScore:
        value = round(data.thesis_health_snapshot.contradictory_strength, 6)
        return ComponentScore(
            component_key=self.component_key,
            label=self.label,
            orientation=self.orientation,
            value=value,
            reason_code=self.reason_code,
            detail={"contradictory_strength": f"{value:.6f}"},
        )


class PortfolioAlignmentScoreComponent:
    component_key = "portfolio_alignment_score"
    label = "Portfolio Alignment Score"
    orientation = ComponentOrientation.BENEFIT
    reason_code = "PORTFOLIO_ALIGNMENT"

    def score(self, data: RecommendationEngineInput) -> ComponentScore:
        ctx = data.portfolio_context
        if ctx.has_existing_position:
            gap = ctx.target_weight - ctx.current_weight
            raw = 0.5 + gap
        else:
            raw = ctx.portfolio_underweight_signal
        value = round(_clamp(raw), 6)
        return ComponentScore(
            component_key=self.component_key,
            label=self.label,
            orientation=self.orientation,
            value=value,
            reason_code=self.reason_code,
            detail={
                "has_existing_position": str(ctx.has_existing_position),
                "current_weight": f"{ctx.current_weight:.6f}",
                "target_weight": f"{ctx.target_weight:.6f}",
            },
        )


class RiskPenaltyComponent:
    component_key = "risk_penalty"
    label = "Risk Penalty"
    orientation = ComponentOrientation.PENALTY
    reason_code = "RISK_CONSTRAINT"

    def score(self, data: RecommendationEngineInput) -> ComponentScore:
        ctx = data.portfolio_context
        value = round(max(ctx.concentration_risk, ctx.liquidity_risk), 6)
        return ComponentScore(
            component_key=self.component_key,
            label=self.label,
            orientation=self.orientation,
            value=value,
            reason_code=self.reason_code,
            detail={
                "concentration_risk": f"{ctx.concentration_risk:.6f}",
                "liquidity_risk": f"{ctx.liquidity_risk:.6f}",
            },
        )


class OpportunityBonusComponent:
    component_key = "opportunity_bonus"
    label = "Opportunity Bonus"
    orientation = ComponentOrientation.BENEFIT
    reason_code = "OPPORTUNITY_SIGNAL"

    def score(self, data: RecommendationEngineInput) -> ComponentScore:
        ctx = data.portfolio_context
        value = round(
            _clamp((ctx.opportunity_signal + ctx.valuation_signal + ctx.expected_return_signal) / 3.0),
            6,
        )
        return ComponentScore(
            component_key=self.component_key,
            label=self.label,
            orientation=self.orientation,
            value=value,
            reason_code=self.reason_code,
            detail={
                "opportunity_signal": f"{ctx.opportunity_signal:.6f}",
                "valuation_signal": f"{ctx.valuation_signal:.6f}",
                "expected_return_signal": f"{ctx.expected_return_signal:.6f}",
            },
        )


def default_scoring_components() -> tuple[ScoringComponent, ...]:
    return (
        HealthScoreComponent(),
        ConfidenceScoreComponent(),
        EvidenceQualityScoreComponent(),
        EvidenceFreshnessScoreComponent(),
        ContradictionPenaltyComponent(),
        PortfolioAlignmentScoreComponent(),
        RiskPenaltyComponent(),
        OpportunityBonusComponent(),
    )


def _assert_unit_interval(field_name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{field_name} must be within [0.0, 1.0]")


def _clamp(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value
