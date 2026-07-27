from __future__ import annotations

from dataclasses import dataclass

from piios.decision_contracts.domain.enums import (
    MonitoringTriggerType,
    Priority,
    RecommendationAction,
    RiskSeverity,
)


@dataclass(frozen=True)
class ReasonWeight:
    value: float

    def __post_init__(self) -> None:
        if self.value < 0.0 or self.value > 1.0:
            raise ValueError("ReasonWeight must be within [0.0, 1.0]")


@dataclass(frozen=True)
class PositionSizeRange:
    min_weight: float
    max_weight: float

    def __post_init__(self) -> None:
        if self.min_weight < 0.0 or self.max_weight < 0.0:
            raise ValueError("position weights must be non-negative")
        if self.min_weight > 1.0 or self.max_weight > 1.0:
            raise ValueError("position weights must be <= 1.0")
        if self.min_weight > self.max_weight:
            raise ValueError("min_weight cannot exceed max_weight")


@dataclass(frozen=True)
class ActionProposal:
    action: RecommendationAction
    position_size_range: PositionSizeRange | None = None
    note: str | None = None


@dataclass(frozen=True)
class RecommendationPriority:
    level: Priority
    score: float

    def __post_init__(self) -> None:
        if self.score < 0.0 or self.score > 1.0:
            raise ValueError("priority score must be within [0.0, 1.0]")


@dataclass(frozen=True)
class RecommendationConfidenceDimensions:
    company_quality: float
    valuation_attractiveness: float
    portfolio_suitability: float
    recommendation_confidence: float
    relationship_confidence: float
    expected_return: float

    def __post_init__(self) -> None:
        for field_name, value in (
            ("company_quality", self.company_quality),
            ("valuation_attractiveness", self.valuation_attractiveness),
            ("portfolio_suitability", self.portfolio_suitability),
            ("recommendation_confidence", self.recommendation_confidence),
            ("relationship_confidence", self.relationship_confidence),
            ("expected_return", self.expected_return),
        ):
            if value < 0.0 or value > 1.0:
                raise ValueError(f"{field_name} must be within [0.0, 1.0]")


@dataclass(frozen=True)
class ConfidenceBreakdown:
    dimensions: RecommendationConfidenceDimensions
    overall_confidence: float

    def __post_init__(self) -> None:
        if self.overall_confidence < 0.0 or self.overall_confidence > 1.0:
            raise ValueError("overall_confidence must be within [0.0, 1.0]")


@dataclass(frozen=True)
class PortfolioSuitabilitySummary:
    suitability_score: float
    concentration_ok: bool
    liquidity_ok: bool
    exposure_ok: bool

    def __post_init__(self) -> None:
        if self.suitability_score < 0.0 or self.suitability_score > 1.0:
            raise ValueError("suitability_score must be within [0.0, 1.0]")


@dataclass(frozen=True)
class ExecutionConsideration:
    consideration_type: str
    detail: str

    def __post_init__(self) -> None:
        if not self.consideration_type.strip():
            raise ValueError("consideration_type must not be empty")
        if not self.detail.strip():
            raise ValueError("detail must not be empty")


@dataclass(frozen=True)
class MonitoringTrigger:
    trigger_type: MonitoringTriggerType
    threshold_detail: str

    def __post_init__(self) -> None:
        if not self.threshold_detail.strip():
            raise ValueError("threshold_detail must not be empty")


@dataclass(frozen=True)
class RiskWarning:
    warning_code: str
    severity: RiskSeverity
    message: str

    def __post_init__(self) -> None:
        if not self.warning_code.strip():
            raise ValueError("warning_code must not be empty")
        if not self.message.strip():
            raise ValueError("message must not be empty")
