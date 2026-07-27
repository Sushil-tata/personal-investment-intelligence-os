from __future__ import annotations

import json
from datetime import datetime, timezone

from piios.decision_contracts.application.decision_engine import RecommendationDecisionEngine
from piios.decision_contracts.application.scoring_components import PortfolioContextSnapshot, RecommendationEngineInput
from piios.decision_contracts.infrastructure.in_memory_repositories import (
    InMemoryRecommendationProposalRepository,
    InMemoryRecommendationProposalVersionRepository,
    InMemoryRecommendationReasonRepository,
    InMemoryRecommendationSnapshotRepository,
    InMemoryRecommendationTraceRepository,
)
from piios.thesis.domain.claims import ClaimEvidenceInterpretation, ClaimStatus, InterpretationRelation, ThesisClaim
from piios.thesis.domain.evidence import EvidenceItem
from piios.thesis_health.domain.entities import ThesisHealthSnapshot


def _build_engine() -> RecommendationDecisionEngine:
    return RecommendationDecisionEngine(
        proposal_repository=InMemoryRecommendationProposalRepository(),
        version_repository=InMemoryRecommendationProposalVersionRepository(),
        snapshot_repository=InMemoryRecommendationSnapshotRepository(),
        reason_repository=InMemoryRecommendationReasonRepository(),
        trace_repository=InMemoryRecommendationTraceRepository(),
    )


def _build_input(strategy_key: str = "balanced-v1") -> RecommendationEngineInput:
    now = datetime(2026, 7, 27, 9, 30, tzinfo=timezone.utc)

    claims = (
        ThesisClaim(
            claim_id="cl1",
            thesis_version_id="thesis:v9",
            thesis_id="thesis",
            claim_key="rev_growth",
            claim_text="Revenue is accelerating",
            claim_type="fundamental",
            status=ClaimStatus.ACTIVE,
            active_from=now,
            active_to=None,
            created_at=now,
            updated_at=now,
        ),
        ThesisClaim(
            claim_id="cl2",
            thesis_version_id="thesis:v9",
            thesis_id="thesis",
            claim_key="margin_expand",
            claim_text="Margins should expand",
            claim_type="fundamental",
            status=ClaimStatus.ACTIVE,
            active_from=now,
            active_to=None,
            created_at=now,
            updated_at=now,
        ),
    )

    evidence = (
        EvidenceItem(
            evidence_id="ev1",
            source_id="src1",
            title="Quarterly filing",
            excerpt="Strong growth",
            content_hash="h1",
            as_of_date="2026-07-25",
            metadata_json='{"quality_score": 0.92}',
            created_at=now,
        ),
        EvidenceItem(
            evidence_id="ev2",
            source_id="src2",
            title="Supplier check",
            excerpt="Input cost pressure",
            content_hash="h2",
            as_of_date="2026-05-20",
            metadata_json='{"quality_score": 0.67}',
            created_at=now,
        ),
    )

    interpretations = (
        ClaimEvidenceInterpretation(
            interpretation_id="int1",
            claim_id="cl1",
            evidence_id="ev1",
            relation=InterpretationRelation.SUPPORTS,
            strength="high",
            note="filing confirms acceleration",
            effective_from=now,
            effective_to=None,
            supersedes_interpretation_id=None,
            superseded_by_interpretation_id=None,
            created_at=now,
        ),
        ClaimEvidenceInterpretation(
            interpretation_id="int2",
            claim_id="cl2",
            evidence_id="ev2",
            relation=InterpretationRelation.CONTRADICTS,
            strength="medium",
            note="cost pressure may delay margin expansion",
            effective_from=now,
            effective_to=None,
            supersedes_interpretation_id=None,
            superseded_by_interpretation_id=None,
            created_at=now,
        ),
    )

    return RecommendationEngineInput(
        proposal_id="proposal:nvda:core",
        target_type="SECURITY",
        target_key="NVDA",
        scope="PORTFOLIO",
        thesis_version_id="thesis:v9",
        generated_at=now,
        thesis_health_snapshot=ThesisHealthSnapshot(
            thesis_version_id="thesis:v9",
            computation_version="wave2b-th-v1",
            computed_at=now,
            evidence_freshness=0.78,
            evidence_quality=0.81,
            supporting_strength=0.9,
            contradictory_strength=0.32,
            provenance_completeness=0.83,
            thesis_health_index=0.8,
        ),
        claims=claims,
        evidence_items=evidence,
        interpretations=interpretations,
        portfolio_context=PortfolioContextSnapshot(
            has_existing_position=True,
            current_weight=0.03,
            target_weight=0.06,
            max_position_weight=0.1,
            concentration_risk=0.25,
            liquidity_risk=0.15,
            portfolio_underweight_signal=0.8,
            opportunity_signal=0.84,
            valuation_signal=0.79,
            expected_return_signal=0.76,
            relationship_signal=0.58,
        ),
        strategy_key=strategy_key,
        metadata={"source": "unit-test"},
    )


def test_engine_evaluate_is_deterministic_replayable() -> None:
    engine = _build_engine()
    data = _build_input()

    first = engine.evaluate(data)
    second = engine.evaluate(data)

    assert first.trace.input_hash == second.trace.input_hash
    assert first.strategy_result.overall_score == second.strategy_result.overall_score
    assert first.explanation == second.explanation


def test_engine_generate_recommendation_persists_complete_trace_bundle() -> None:
    engine = _build_engine()
    data = _build_input()

    result = engine.generate_recommendation(data)

    assert result.proposal.proposal_id == "proposal:nvda:core"
    assert result.proposal_version.version_number == 1
    assert result.input_snapshot.proposal_version_id == result.proposal_version.proposal_version_id
    assert result.reasons
    assert result.claim_links
    assert result.evidence_links
    assert result.evaluation.explanation.drivers
    assert result.evaluation.explanation.warnings

    payload = json.loads(result.input_snapshot.canonical_payload_json)
    assert payload["strategy_result"]["overall_score"] == result.evaluation.strategy_result.overall_score
    assert payload["explanation"]["recommendation"] == result.proposal_version.action_proposal.action.value


def test_engine_handles_missing_evidence_and_stale_inputs() -> None:
    engine = _build_engine()
    data = _build_input()

    stale = RecommendationEngineInput(
        proposal_id="proposal:stale:watch",
        target_type=data.target_type,
        target_key=data.target_key,
        scope=data.scope,
        thesis_version_id=data.thesis_version_id,
        generated_at=data.generated_at,
        thesis_health_snapshot=ThesisHealthSnapshot(
            thesis_version_id=data.thesis_health_snapshot.thesis_version_id,
            computation_version=data.thesis_health_snapshot.computation_version,
            computed_at=data.generated_at,
            evidence_freshness=0.05,
            evidence_quality=0.4,
            supporting_strength=0.3,
            contradictory_strength=0.8,
            provenance_completeness=0.25,
            thesis_health_index=0.24,
        ),
        claims=data.claims,
        evidence_items=tuple(),
        interpretations=data.interpretations,
        portfolio_context=PortfolioContextSnapshot(
            has_existing_position=False,
            current_weight=0.0,
            target_weight=0.03,
            max_position_weight=0.08,
            concentration_risk=0.72,
            liquidity_risk=0.66,
            portfolio_underweight_signal=0.4,
            opportunity_signal=0.3,
            valuation_signal=0.25,
            expected_return_signal=0.2,
            relationship_signal=0.3,
        ),
        strategy_key="conservative-v1",
    )

    result = engine.generate_recommendation(stale)

    assert result.proposal_version.required_human_review is True
    assert result.proposal_version.action_proposal.action.value in {"WATCH", "NO_ACTION", "REDUCE", "SELL"}
    assert any("warning" in text.lower() or "risk" in text.lower() for text in result.evaluation.explanation.warnings)


def test_engine_supports_pluggable_strategy_selection() -> None:
    engine = _build_engine()
    balanced = engine.generate_recommendation(_build_input(strategy_key="balanced-v1"))
    aggressive = engine.generate_recommendation(_build_input(strategy_key="aggressive-v1"))

    assert aggressive.evaluation.strategy_result.strategy_key == "aggressive-v1"
    assert balanced.evaluation.strategy_result.strategy_key == "balanced-v1"
    assert aggressive.evaluation.strategy_result.overall_score != balanced.evaluation.strategy_result.overall_score
