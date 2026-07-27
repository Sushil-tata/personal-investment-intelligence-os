from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

from piios.decision_contracts.application.scoring_components import (
    PortfolioContextSnapshot,
    RecommendationEngineInput,
)
from piios.thesis.domain.claims import (
    ClaimEvidenceInterpretation,
    ClaimStatus,
    InterpretationRelation,
    ThesisClaim,
)
from piios.thesis.domain.evidence import EvidenceItem
from piios.thesis_health.domain.entities import ThesisHealthSnapshot


@dataclass(frozen=True)
class ScenarioData:
    name: str
    thesis_health: dict[str, float]
    portfolio_context: dict[str, float | bool]
    with_second_evidence: bool
    conflicting: bool


def scenario_catalog() -> dict[str, ScenarioData]:
    base_ctx = {
        "has_existing_position": True,
        "current_weight": 0.03,
        "target_weight": 0.06,
        "max_position_weight": 0.10,
        "concentration_risk": 0.20,
        "liquidity_risk": 0.10,
        "portfolio_underweight_signal": 0.75,
        "opportunity_signal": 0.82,
        "valuation_signal": 0.78,
        "expected_return_signal": 0.74,
        "relationship_signal": 0.60,
    }
    return {
        "A_strong_positive": ScenarioData(
            name="A_strong_positive",
            thesis_health={
                "evidence_freshness": 0.95,
                "evidence_quality": 0.92,
                "supporting_strength": 0.95,
                "contradictory_strength": 0.05,
                "provenance_completeness": 0.95,
                "thesis_health_index": 0.94,
            },
            portfolio_context={
                **base_ctx,
                "has_existing_position": False,
                "current_weight": 0.0,
                "target_weight": 0.07,
                "concentration_risk": 0.08,
                "liquidity_risk": 0.08,
            },
            with_second_evidence=True,
            conflicting=False,
        ),
        "B_strong_negative": ScenarioData(
            name="B_strong_negative",
            thesis_health={
                "evidence_freshness": 0.15,
                "evidence_quality": 0.25,
                "supporting_strength": 0.10,
                "contradictory_strength": 0.95,
                "provenance_completeness": 0.30,
                "thesis_health_index": 0.12,
            },
            portfolio_context={
                **base_ctx,
                "has_existing_position": True,
                "current_weight": 0.09,
                "target_weight": 0.03,
                "concentration_risk": 0.95,
                "liquidity_risk": 0.88,
                "opportunity_signal": 0.10,
                "valuation_signal": 0.20,
                "expected_return_signal": 0.10,
            },
            with_second_evidence=True,
            conflicting=True,
        ),
        "C_mixed_conflicting": ScenarioData(
            name="C_mixed_conflicting",
            thesis_health={
                "evidence_freshness": 0.65,
                "evidence_quality": 0.88,
                "supporting_strength": 0.62,
                "contradictory_strength": 0.45,
                "provenance_completeness": 0.72,
                "thesis_health_index": 0.58,
            },
            portfolio_context={
                **base_ctx,
                "valuation_signal": 0.30,
                "opportunity_signal": 0.70,
                "expected_return_signal": 0.55,
                "concentration_risk": 0.35,
                "liquidity_risk": 0.30,
            },
            with_second_evidence=True,
            conflicting=True,
        ),
        "D_missing_evidence": ScenarioData(
            name="D_missing_evidence",
            thesis_health={
                "evidence_freshness": 0.60,
                "evidence_quality": 0.70,
                "supporting_strength": 0.60,
                "contradictory_strength": 0.35,
                "provenance_completeness": 0.70,
                "thesis_health_index": 0.55,
            },
            portfolio_context={
                **base_ctx,
                "concentration_risk": 0.30,
                "liquidity_risk": 0.25,
                "valuation_signal": 0.55,
            },
            with_second_evidence=False,
            conflicting=False,
        ),
        "E_stale_evidence": ScenarioData(
            name="E_stale_evidence",
            thesis_health={
                "evidence_freshness": 0.05,
                "evidence_quality": 0.78,
                "supporting_strength": 0.55,
                "contradictory_strength": 0.40,
                "provenance_completeness": 0.65,
                "thesis_health_index": 0.50,
            },
            portfolio_context={
                **base_ctx,
                "valuation_signal": 0.60,
                "expected_return_signal": 0.52,
                "opportunity_signal": 0.50,
            },
            with_second_evidence=True,
            conflicting=True,
        ),
    }


def build_input(spec: ScenarioData, *, strategy_key: str = "balanced-v1") -> RecommendationEngineInput:
    suffix = uuid.uuid4().hex[:10]
    now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
    thesis_id = f"t_{spec.name}_{suffix}"
    thesis_version_id = f"{thesis_id}:v1"
    claim_id = f"cl_{suffix}"
    evidence1 = f"ev1_{suffix}"
    evidence2 = f"ev2_{suffix}"

    claims = (
        ThesisClaim(
            claim_id=claim_id,
            thesis_version_id=thesis_version_id,
            thesis_id=thesis_id,
            claim_key="core",
            claim_text="Core investment thesis",
            claim_type="fundamental",
            status=ClaimStatus.ACTIVE,
            active_from=now,
            active_to=None,
            created_at=now,
            updated_at=now,
        ),
    )

    evidence = [
        EvidenceItem(
            evidence_id=evidence1,
            source_id=f"src1_{suffix}",
            title="Primary evidence",
            excerpt="primary",
            content_hash=f"h_{evidence1}",
            as_of_date="2026-07-25",
            metadata_json='{"quality_score": 0.92}',
            created_at=now,
        )
    ]
    if spec.with_second_evidence:
        evidence.append(
            EvidenceItem(
                evidence_id=evidence2,
                source_id=f"src2_{suffix}",
                title="Secondary evidence",
                excerpt="secondary",
                content_hash=f"h_{evidence2}",
                as_of_date="2026-05-25",
                metadata_json='{"quality_score": 0.55}',
                created_at=now,
            )
        )

    interpretations = [
        ClaimEvidenceInterpretation(
            interpretation_id=f"int1_{suffix}",
            claim_id=claim_id,
            evidence_id=evidence1,
            relation=InterpretationRelation.SUPPORTS,
            strength="high",
            note=None,
            effective_from=now,
            effective_to=None,
            supersedes_interpretation_id=None,
            superseded_by_interpretation_id=None,
            created_at=now,
        )
    ]
    if spec.with_second_evidence:
        relation = InterpretationRelation.CONTRADICTS if spec.conflicting else InterpretationRelation.SUPPORTS
        interpretations.append(
            ClaimEvidenceInterpretation(
                interpretation_id=f"int2_{suffix}",
                claim_id=claim_id,
                evidence_id=evidence2,
                relation=relation,
                strength="medium",
                note=None,
                effective_from=now,
                effective_to=None,
                supersedes_interpretation_id=None,
                superseded_by_interpretation_id=None,
                created_at=now,
            )
        )

    return RecommendationEngineInput(
        proposal_id=f"proposal:{spec.name}:{suffix}",
        target_type="SECURITY",
        target_key="NVDA",
        scope="PORTFOLIO",
        thesis_version_id=thesis_version_id,
        generated_at=now,
        thesis_health_snapshot=ThesisHealthSnapshot(
            thesis_version_id=thesis_version_id,
            computation_version="wave2b-th-v1",
            computed_at=now,
            evidence_freshness=spec.thesis_health["evidence_freshness"],
            evidence_quality=spec.thesis_health["evidence_quality"],
            supporting_strength=spec.thesis_health["supporting_strength"],
            contradictory_strength=spec.thesis_health["contradictory_strength"],
            provenance_completeness=spec.thesis_health["provenance_completeness"],
            thesis_health_index=spec.thesis_health["thesis_health_index"],
        ),
        claims=claims,
        evidence_items=tuple(evidence),
        interpretations=tuple(interpretations),
        portfolio_context=PortfolioContextSnapshot(**spec.portfolio_context),
        strategy_key=strategy_key,
        metadata={"scenario": spec.name},
    )
