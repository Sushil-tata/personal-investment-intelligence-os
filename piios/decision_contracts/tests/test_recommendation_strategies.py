from __future__ import annotations

from datetime import datetime, timezone

from piios.decision_contracts.application.scoring_components import (
    ComponentOrientation,
    ComponentScore,
    PortfolioContextSnapshot,
    RecommendationEngineInput,
)
from piios.decision_contracts.application.strategies import default_recommendation_strategies
from piios.thesis_health.domain.entities import ThesisHealthSnapshot


def _input(has_position: bool) -> RecommendationEngineInput:
    now = datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc)
    return RecommendationEngineInput(
        proposal_id="p:rec:msft",
        target_type="SECURITY",
        target_key="MSFT",
        scope="PORTFOLIO",
        thesis_version_id="thesis:v2",
        generated_at=now,
        thesis_health_snapshot=ThesisHealthSnapshot(
            thesis_version_id="thesis:v2",
            computation_version="wave2b-th-v1",
            computed_at=now,
            evidence_freshness=0.7,
            evidence_quality=0.8,
            supporting_strength=0.85,
            contradictory_strength=0.2,
            provenance_completeness=0.9,
            thesis_health_index=0.79,
        ),
        claims=tuple(),
        evidence_items=tuple(),
        interpretations=tuple(),
        portfolio_context=PortfolioContextSnapshot(
            has_existing_position=has_position,
            current_weight=0.02 if has_position else 0.0,
            target_weight=0.05,
            max_position_weight=0.1,
            concentration_risk=0.2,
            liquidity_risk=0.1,
            portfolio_underweight_signal=0.85,
            opportunity_signal=0.8,
            valuation_signal=0.75,
            expected_return_signal=0.78,
            relationship_signal=0.6,
        ),
    )


def _component_scores() -> tuple[ComponentScore, ...]:
    return (
        ComponentScore("health_score", "Health Score", ComponentOrientation.BENEFIT, 0.82, "HEALTH", {}),
        ComponentScore("confidence_score", "Confidence Score", ComponentOrientation.BENEFIT, 0.78, "CONF", {}),
        ComponentScore("evidence_quality_score", "Evidence Quality", ComponentOrientation.BENEFIT, 0.8, "EVID_Q", {}),
        ComponentScore("evidence_freshness_score", "Evidence Freshness", ComponentOrientation.BENEFIT, 0.75, "EVID_F", {}),
        ComponentScore("contradiction_penalty", "Contradiction", ComponentOrientation.PENALTY, 0.2, "CONTRA", {}),
        ComponentScore("portfolio_alignment_score", "Portfolio", ComponentOrientation.BENEFIT, 0.85, "PORT", {}),
        ComponentScore("risk_penalty", "Risk", ComponentOrientation.PENALTY, 0.15, "RISK", {}),
        ComponentScore("opportunity_bonus", "Opportunity", ComponentOrientation.BENEFIT, 0.88, "OPP", {}),
    )


def test_strategy_profiles_produce_different_scores() -> None:
    data = _input(has_position=True)
    scores = _component_scores()
    strategies = default_recommendation_strategies()

    conservative = strategies["conservative-v1"].evaluate(data, scores)
    balanced = strategies["balanced-v1"].evaluate(data, scores)
    aggressive = strategies["aggressive-v1"].evaluate(data, scores)

    assert conservative.overall_score != aggressive.overall_score
    assert conservative.overall_score <= balanced.overall_score <= aggressive.overall_score


def test_strategy_action_uses_existing_position_state() -> None:
    strategies = default_recommendation_strategies()
    result_with_position = strategies["balanced-v1"].evaluate(_input(has_position=True), _component_scores())
    result_without_position = strategies["balanced-v1"].evaluate(_input(has_position=False), _component_scores())

    assert result_with_position.action.value in {"ADD", "HOLD", "REDUCE", "SELL", "WATCH", "NO_ACTION"}
    assert result_without_position.action.value in {"BUY", "WATCH", "NO_ACTION"}

    if result_with_position.action.value == "ADD":
        assert result_with_position.position_size_range is not None


def test_strategy_flags_human_review_for_high_penalty() -> None:
    data = _input(has_position=True)
    strategies = default_recommendation_strategies()

    severe_scores = list(_component_scores())
    severe_scores[4] = ComponentScore(
        "contradiction_penalty",
        "Contradiction",
        ComponentOrientation.PENALTY,
        0.9,
        "CONTRA",
        {},
    )

    result = strategies["conservative-v1"].evaluate(data, tuple(severe_scores))
    assert result.required_human_review is True
