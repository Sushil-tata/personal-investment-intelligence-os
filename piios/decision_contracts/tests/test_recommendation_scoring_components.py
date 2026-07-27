from __future__ import annotations

from datetime import datetime, timezone

from piios.decision_contracts.application.scoring_components import (
    ConfidenceScoreComponent,
    ContradictionPenaltyComponent,
    EvidenceFreshnessScoreComponent,
    EvidenceQualityScoreComponent,
    HealthScoreComponent,
    OpportunityBonusComponent,
    PortfolioAlignmentScoreComponent,
    PortfolioContextSnapshot,
    RecommendationEngineInput,
    RiskPenaltyComponent,
)
from piios.thesis.domain.claims import ClaimEvidenceInterpretation, ClaimStatus, InterpretationRelation, ThesisClaim
from piios.thesis.domain.evidence import EvidenceItem
from piios.thesis_health.domain.entities import ThesisHealthSnapshot


def _build_input() -> RecommendationEngineInput:
    now = datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc)
    return RecommendationEngineInput(
        proposal_id="p:rec:nvda",
        target_type="SECURITY",
        target_key="NVDA",
        scope="PORTFOLIO",
        thesis_version_id="thesis:v1",
        generated_at=now,
        thesis_health_snapshot=ThesisHealthSnapshot(
            thesis_version_id="thesis:v1",
            computation_version="wave2b-th-v1",
            computed_at=now,
            evidence_freshness=0.72,
            evidence_quality=0.84,
            supporting_strength=0.91,
            contradictory_strength=0.28,
            provenance_completeness=0.88,
            thesis_health_index=0.81,
        ),
        claims=(
            ThesisClaim(
                claim_id="cl1",
                thesis_version_id="thesis:v1",
                thesis_id="thesis",
                claim_key="growth",
                claim_text="Growth thesis",
                claim_type="fundamental",
                status=ClaimStatus.ACTIVE,
                active_from=now,
                active_to=None,
                created_at=now,
                updated_at=now,
            ),
        ),
        evidence_items=(
            EvidenceItem(
                evidence_id="ev1",
                source_id="src1",
                title="Catalyst",
                excerpt="x",
                content_hash="h1",
                as_of_date="2026-07-20",
                metadata_json='{"quality_score": 0.9}',
                created_at=now,
            ),
        ),
        interpretations=(
            ClaimEvidenceInterpretation(
                interpretation_id="int1",
                claim_id="cl1",
                evidence_id="ev1",
                relation=InterpretationRelation.SUPPORTS,
                strength="high",
                note=None,
                effective_from=now,
                effective_to=None,
                supersedes_interpretation_id=None,
                superseded_by_interpretation_id=None,
                created_at=now,
            ),
        ),
        portfolio_context=PortfolioContextSnapshot(
            has_existing_position=True,
            current_weight=0.03,
            target_weight=0.05,
            max_position_weight=0.08,
            concentration_risk=0.18,
            liquidity_risk=0.11,
            portfolio_underweight_signal=0.7,
            opportunity_signal=0.8,
            valuation_signal=0.76,
            expected_return_signal=0.73,
            relationship_signal=0.6,
        ),
    )


def test_scoring_components_return_bounded_deterministic_values() -> None:
    data = _build_input()

    components = (
        HealthScoreComponent(),
        ConfidenceScoreComponent(),
        EvidenceQualityScoreComponent(),
        EvidenceFreshnessScoreComponent(),
        ContradictionPenaltyComponent(),
        PortfolioAlignmentScoreComponent(),
        RiskPenaltyComponent(),
        OpportunityBonusComponent(),
    )

    first = tuple(component.score(data) for component in components)
    second = tuple(component.score(data) for component in components)

    assert first == second
    assert all(0.0 <= row.value <= 1.0 for row in first)


def test_confidence_component_drops_with_conflicting_interpretations() -> None:
    data = _build_input()
    now = data.generated_at

    conflicting = RecommendationEngineInput(
        proposal_id=data.proposal_id,
        target_type=data.target_type,
        target_key=data.target_key,
        scope=data.scope,
        thesis_version_id=data.thesis_version_id,
        generated_at=data.generated_at,
        thesis_health_snapshot=data.thesis_health_snapshot,
        claims=data.claims,
        evidence_items=data.evidence_items,
        interpretations=(
            data.interpretations[0],
            ClaimEvidenceInterpretation(
                interpretation_id="int2",
                claim_id="cl1",
                evidence_id="ev1",
                relation=InterpretationRelation.CONTRADICTS,
                strength="medium",
                note=None,
                effective_from=now,
                effective_to=None,
                supersedes_interpretation_id=None,
                superseded_by_interpretation_id=None,
                created_at=now,
            ),
        ),
        portfolio_context=data.portfolio_context,
        strategy_key=data.strategy_key,
        metadata=data.metadata,
    )

    component = ConfidenceScoreComponent()
    assert component.score(conflicting).value < component.score(data).value


def test_portfolio_alignment_and_risk_penalty_edge_cases() -> None:
    now = datetime(2026, 7, 27, tzinfo=timezone.utc)
    base = _build_input()

    no_position = RecommendationEngineInput(
        proposal_id=base.proposal_id,
        target_type=base.target_type,
        target_key=base.target_key,
        scope=base.scope,
        thesis_version_id=base.thesis_version_id,
        generated_at=now,
        thesis_health_snapshot=base.thesis_health_snapshot,
        claims=base.claims,
        evidence_items=base.evidence_items,
        interpretations=base.interpretations,
        portfolio_context=PortfolioContextSnapshot(
            has_existing_position=False,
            current_weight=0.0,
            target_weight=0.03,
            max_position_weight=0.08,
            concentration_risk=0.9,
            liquidity_risk=0.2,
            portfolio_underweight_signal=0.95,
            opportunity_signal=0.5,
            valuation_signal=0.5,
            expected_return_signal=0.5,
            relationship_signal=0.5,
        ),
        strategy_key=base.strategy_key,
        metadata=base.metadata,
    )

    alignment = PortfolioAlignmentScoreComponent().score(no_position)
    risk = RiskPenaltyComponent().score(no_position)

    assert alignment.value == 0.95
    assert risk.value == 0.9
