from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from piios.decision_contracts.domain.enums import DecisionState, MonitoringTriggerType, Priority, RecommendationAction, RiskSeverity
from piios.decision_contracts.domain.value_objects import (
    ActionProposal,
    ConfidenceBreakdown,
    ExecutionConsideration,
    MonitoringTrigger,
    PortfolioSuitabilitySummary,
    PositionSizeRange,
    RecommendationConfidenceDimensions,
    RecommendationPriority,
    ReasonWeight,
    RiskWarning,
)


def test_reason_weight_range_validation() -> None:
    with pytest.raises(ValueError):
        ReasonWeight(-0.01)
    with pytest.raises(ValueError):
        ReasonWeight(1.01)
    assert ReasonWeight(0.8).value == 0.8


def test_position_size_range_validation() -> None:
    with pytest.raises(ValueError):
        PositionSizeRange(-0.1, 0.2)
    with pytest.raises(ValueError):
        PositionSizeRange(0.3, 0.2)
    assert PositionSizeRange(0.1, 0.3).max_weight == 0.3


def test_recommendation_priority_score_validation() -> None:
    with pytest.raises(ValueError):
        RecommendationPriority(level=Priority.HIGH, score=1.5)
    assert RecommendationPriority(level=Priority.HIGH, score=0.9).level == Priority.HIGH


def test_confidence_dimensions_validation() -> None:
    with pytest.raises(ValueError):
        RecommendationConfidenceDimensions(
            company_quality=1.1,
            valuation_attractiveness=0.8,
            portfolio_suitability=0.7,
            recommendation_confidence=0.6,
            relationship_confidence=0.5,
            expected_return=0.4,
        )


def test_confidence_breakdown_validation() -> None:
    dims = RecommendationConfidenceDimensions(
        company_quality=0.8,
        valuation_attractiveness=0.7,
        portfolio_suitability=0.6,
        recommendation_confidence=0.65,
        relationship_confidence=0.55,
        expected_return=0.5,
    )
    with pytest.raises(ValueError):
        ConfidenceBreakdown(dimensions=dims, overall_confidence=1.2)


def test_risk_warning_and_execution_validation() -> None:
    with pytest.raises(ValueError):
        RiskWarning(warning_code="", severity=RiskSeverity.HIGH, message="x")
    with pytest.raises(ValueError):
        ExecutionConsideration(consideration_type="", detail="x")
    with pytest.raises(ValueError):
        MonitoringTrigger(trigger_type=MonitoringTriggerType.PRICE_MOVE, threshold_detail="")


def test_value_objects_are_immutable() -> None:
    obj = ActionProposal(action=RecommendationAction.BUY)
    with pytest.raises(FrozenInstanceError):
        obj.note = "changed"


def test_portfolio_suitability_summary_validation() -> None:
    with pytest.raises(ValueError):
        PortfolioSuitabilitySummary(
            suitability_score=1.1,
            concentration_ok=True,
            liquidity_ok=True,
            exposure_ok=True,
        )
