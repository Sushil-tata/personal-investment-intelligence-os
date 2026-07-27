from __future__ import annotations

from datetime import datetime, timezone

import pytest

from piios.decision_contracts.application.decision_engine import RecommendationDecisionEngine
from piios.decision_contracts.application.scoring_components import ComponentOrientation, ComponentScore, RecommendationEngineInput
from piios.decision_contracts.application.strategies import default_recommendation_strategies
from piios.decision_contracts.infrastructure.in_memory_repositories import (
    InMemoryRecommendationProposalRepository,
    InMemoryRecommendationProposalVersionRepository,
    InMemoryRecommendationReasonRepository,
    InMemoryRecommendationSnapshotRepository,
    InMemoryRecommendationTraceRepository,
)
from piios.thesis_health.domain.entities import ThesisHealthSnapshot

from piios.decision_contracts.tests.functional_acceptance_helpers import ScenarioData, build_input, scenario_catalog


def _build_engine_with_repos():
    proposal_repo = InMemoryRecommendationProposalRepository()
    version_repo = InMemoryRecommendationProposalVersionRepository()
    snapshot_repo = InMemoryRecommendationSnapshotRepository()
    reason_repo = InMemoryRecommendationReasonRepository()
    trace_repo = InMemoryRecommendationTraceRepository()
    engine = RecommendationDecisionEngine(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        snapshot_repository=snapshot_repo,
        reason_repository=reason_repo,
        trace_repository=trace_repo,
    )
    return engine, version_repo


@pytest.mark.parametrize(
    ("scenario_key", "expected_action"),
    (
        ("A_strong_positive", "BUY"),
        ("B_strong_negative", "SELL"),
        ("C_mixed_conflicting", "ADD"),
        ("D_missing_evidence", "ADD"),
        ("E_stale_evidence", "HOLD"),
    ),
)
def test_functional_scenarios_produce_expected_actions_and_traces_inmemory(scenario_key: str, expected_action: str) -> None:
    scenarios = scenario_catalog()
    data = build_input(scenarios[scenario_key])
    engine, _ = _build_engine_with_repos()

    result = engine.generate_recommendation(data)

    assert result.proposal_version.action_proposal.action.value == expected_action
    assert 0.0 <= result.evaluation.strategy_result.overall_score <= 1.0
    assert 0.0 <= result.proposal_version.confidence_breakdown.overall_confidence <= 1.0
    assert result.reasons
    assert result.claim_links
    if scenario_key == "D_missing_evidence":
        assert len(result.evidence_links) == 1
    else:
        assert len(result.evidence_links) >= 2
    assert result.input_snapshot.input_hash
    assert result.input_snapshot.canonical_payload_json


def test_threshold_boundaries_and_malformed_inputs() -> None:
    strategies = default_recommendation_strategies()
    balanced = strategies["balanced-v1"]

    base = build_input(scenario_catalog()["C_mixed_conflicting"])

    def _scores(v: float) -> tuple[ComponentScore, ...]:
        return (
            ComponentScore("health_score", "Health", ComponentOrientation.BENEFIT, v, "H", {}),
            ComponentScore("confidence_score", "Conf", ComponentOrientation.BENEFIT, v, "C", {}),
            ComponentScore("evidence_quality_score", "EQ", ComponentOrientation.BENEFIT, v, "E", {}),
            ComponentScore("evidence_freshness_score", "EF", ComponentOrientation.BENEFIT, v, "F", {}),
            ComponentScore("contradiction_penalty", "CP", ComponentOrientation.PENALTY, 1 - v, "CP", {}),
            ComponentScore("portfolio_alignment_score", "PA", ComponentOrientation.BENEFIT, v, "PA", {}),
            ComponentScore("risk_penalty", "RP", ComponentOrientation.PENALTY, 1 - v, "RP", {}),
            ComponentScore("opportunity_bonus", "OB", ComponentOrientation.BENEFIT, v, "OB", {}),
        )

    threshold_expectations = {
        0.0: "SELL",
        0.3: "WATCH",
        0.46: "HOLD",
        0.62: "ADD",
        0.76: "ADD",
        1.0: "ADD",
    }
    for score, expected_action in threshold_expectations.items():
        result = balanced.evaluate(base, _scores(score))
        assert result.action.value == expected_action

    with pytest.raises(ValueError, match="proposal_id must not be empty"):
        RecommendationEngineInput(
            proposal_id=" ",
            target_type="SECURITY",
            target_key="NVDA",
            scope="PORTFOLIO",
            thesis_version_id="thesis:v1",
            generated_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
            thesis_health_snapshot=ThesisHealthSnapshot(
                thesis_version_id="thesis:v1",
                computation_version="wave2b-th-v1",
                computed_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
                evidence_freshness=0.5,
                evidence_quality=0.5,
                supporting_strength=0.5,
                contradictory_strength=0.5,
                provenance_completeness=0.5,
                thesis_health_index=0.5,
            ),
            claims=tuple(),
            evidence_items=tuple(),
            interpretations=tuple(),
            portfolio_context=base.portfolio_context,
        )


def test_portfolio_context_sensitivity_changes_outcome() -> None:
    health = {
        "evidence_freshness": 0.80,
        "evidence_quality": 0.85,
        "supporting_strength": 0.85,
        "contradictory_strength": 0.20,
        "provenance_completeness": 0.88,
        "thesis_health_index": 0.82,
    }

    concentrated_input = build_input(
        ScenarioData(
            name="G_concentrated_low_cash",
            thesis_health=health,
            portfolio_context={
                "has_existing_position": True,
                "current_weight": 0.09,
                "target_weight": 0.05,
                "max_position_weight": 0.10,
                "concentration_risk": 0.92,
                "liquidity_risk": 0.70,
                "portfolio_underweight_signal": 0.20,
                "opportunity_signal": 0.75,
                "valuation_signal": 0.72,
                "expected_return_signal": 0.70,
                "relationship_signal": 0.55,
            },
            with_second_evidence=True,
            conflicting=False,
        )
    )
    diversified_input = build_input(
        ScenarioData(
            name="G_diversified_high_cash",
            thesis_health=health,
            portfolio_context={
                "has_existing_position": False,
                "current_weight": 0.00,
                "target_weight": 0.06,
                "max_position_weight": 0.12,
                "concentration_risk": 0.10,
                "liquidity_risk": 0.10,
                "portfolio_underweight_signal": 0.95,
                "opportunity_signal": 0.75,
                "valuation_signal": 0.72,
                "expected_return_signal": 0.70,
                "relationship_signal": 0.55,
            },
            with_second_evidence=True,
            conflicting=False,
        )
    )

    engine, _ = _build_engine_with_repos()
    concentrated_result = engine.generate_recommendation(concentrated_input)
    diversified_result = engine.generate_recommendation(diversified_input)

    assert concentrated_result.proposal_version.action_proposal.action.value != diversified_result.proposal_version.action_proposal.action.value
    assert concentrated_result.evaluation.strategy_result.overall_score != diversified_result.evaluation.strategy_result.overall_score


def test_determinism_idempotency_and_material_change_versioning() -> None:
    data = build_input(scenario_catalog()["C_mixed_conflicting"])
    engine, version_repo = _build_engine_with_repos()

    eval_one = engine.evaluate(data)
    eval_two = engine.evaluate(data)
    assert eval_one.trace.input_hash == eval_two.trace.input_hash
    assert eval_one.explanation == eval_two.explanation

    first = engine.generate_recommendation(data)
    second = engine.generate_recommendation(data)
    assert first.proposal_version.proposal_version_id == second.proposal_version.proposal_version_id
    assert len(version_repo.list_for_proposal(data.proposal_id)) == 1

    changed = RecommendationEngineInput(
        proposal_id=data.proposal_id,
        target_type=data.target_type,
        target_key=data.target_key,
        scope=data.scope,
        thesis_version_id=data.thesis_version_id,
        generated_at=data.generated_at,
        thesis_health_snapshot=ThesisHealthSnapshot(
            thesis_version_id=data.thesis_health_snapshot.thesis_version_id,
            computation_version=data.thesis_health_snapshot.computation_version,
            computed_at=data.thesis_health_snapshot.computed_at,
            evidence_freshness=data.thesis_health_snapshot.evidence_freshness,
            evidence_quality=0.40,
            supporting_strength=data.thesis_health_snapshot.supporting_strength,
            contradictory_strength=data.thesis_health_snapshot.contradictory_strength,
            provenance_completeness=data.thesis_health_snapshot.provenance_completeness,
            thesis_health_index=data.thesis_health_snapshot.thesis_health_index,
        ),
        claims=data.claims,
        evidence_items=data.evidence_items,
        interpretations=data.interpretations,
        portfolio_context=data.portfolio_context,
        strategy_key=data.strategy_key,
        metadata=data.metadata,
    )

    third = engine.generate_recommendation(changed)
    versions = version_repo.list_for_proposal(data.proposal_id)

    assert third.input_snapshot.input_hash != first.input_snapshot.input_hash
    assert len(versions) == 2
    assert versions[0].proposal_version_id == first.proposal_version.proposal_version_id


def test_strategy_governance_hash_behavior() -> None:
    base = default_recommendation_strategies()["balanced-v1"]
    base_hash = base.governance_hash()

    weight_change = default_recommendation_strategies()["balanced-v1"]
    weight_change.component_weights["opportunity_bonus"] += 0.01

    threshold_change = default_recommendation_strategies()["balanced-v1"]
    threshold_change.buy_threshold += 0.01

    reorder_only = default_recommendation_strategies()["balanced-v1"]
    reorder_only.component_weights = dict(reversed(list(reorder_only.component_weights.items())))

    assert weight_change.governance_hash() != base_hash
    assert threshold_change.governance_hash() != base_hash
    assert reorder_only.governance_hash() == base_hash
