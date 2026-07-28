from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json

from piios.decision_contracts.application.decision_engine import RecommendationDecisionEngine
from piios.decision_contracts.application.scoring_components import PortfolioContextSnapshot, RecommendationEngineInput
from piios.decision_contracts.application.strategies import default_recommendation_strategies
from piios.decision_contracts.application.recommendation_reconstruction_service import RecommendationReconstructionService
from piios.decision_contracts.infrastructure.in_memory_repositories import (
    InMemoryRecommendationProposalRepository,
    InMemoryRecommendationProposalVersionRepository,
    InMemoryRecommendationReasonRepository,
    InMemoryRecommendationSnapshotRepository,
    InMemoryRecommendationTraceRepository,
)
from piios.thesis.domain.claims import ClaimStatus, ClaimEvidenceInterpretation, InterpretationRelation, ThesisClaim
from piios.thesis.domain.evidence import EvidenceItem
from piios.thesis_health.domain.entities import ThesisHealthSnapshot


@dataclass(frozen=True)
class ReplayDifference:
    field: str
    expected: str
    actual: str


@dataclass(frozen=True)
class ReplayVerificationReport:
    status: str
    proposal_version_id: str
    persisted_trace_id: str
    recomputed_trace_id: str
    persisted_input_hash: str
    recomputed_input_hash: str
    differences: tuple[ReplayDifference, ...]


class RecommendationReplayVerificationService:
    """Read-only replay verifier over persisted recommendation artifacts."""

    def __init__(self, reconstruction_service: RecommendationReconstructionService) -> None:
        self._reconstruction_service = reconstruction_service

    def verify_by_proposal_version(self, proposal_version_id: str) -> ReplayVerificationReport:
        lineage = self._reconstruction_service.reconstruct_by_proposal_version(proposal_version_id)
        replay_input = _input_from_snapshot_payload(lineage.input_snapshot.canonical_payload_json)
        engine = _read_only_engine()
        evaluation = engine.evaluate(replay_input)

        payload = json.loads(lineage.input_snapshot.canonical_payload_json)
        persisted_component_scores = {
            str(row["component_key"]): float(row["value"])
            for row in payload.get("component_scores", [])
        }
        recomputed_component_scores = {
            row.component_key: row.value
            for row in evaluation.component_scores
        }

        persisted_action = str(payload.get("strategy_result", {}).get("action", ""))
        persisted_overall_score = float(payload.get("strategy_result", {}).get("overall_score", 0.0))

        persisted_explanation = {
            "recommendation": str(payload.get("explanation", {}).get("recommendation", "")),
            "overall_score": int(payload.get("explanation", {}).get("overall_score", 0)),
            "drivers": [str(item) for item in payload.get("explanation", {}).get("drivers", [])],
            "warnings": [str(item) for item in payload.get("explanation", {}).get("warnings", [])],
            "recommendation_confidence": str(
                payload.get("explanation", {}).get("recommendation_confidence", "")
            ),
            "strategy_key": str(payload.get("explanation", {}).get("strategy_key", "")),
        }
        recomputed_explanation = {
            "recommendation": evaluation.explanation.recommendation,
            "overall_score": evaluation.explanation.overall_score,
            "drivers": list(evaluation.explanation.drivers),
            "warnings": list(evaluation.explanation.warnings),
            "recommendation_confidence": evaluation.explanation.recommendation_confidence,
            "strategy_key": evaluation.explanation.strategy_key,
        }

        persisted_trace_id = lineage.trace.trace_id
        recomputed_trace_id = f"{proposal_version_id}:trace:{evaluation.trace.input_hash[:12]}"

        differences: list[ReplayDifference] = []
        _append_diff(
            differences,
            "action",
            persisted_action,
            evaluation.strategy_result.action.value,
        )
        _append_diff(
            differences,
            "overall_score",
            f"{persisted_overall_score:.6f}",
            f"{evaluation.strategy_result.overall_score:.6f}",
        )
        _append_diff(
            differences,
            "deterministic_input_hash",
            lineage.input_snapshot.input_hash,
            evaluation.trace.input_hash,
        )
        _append_diff(
            differences,
            "trace_hash",
            lineage.input_snapshot.input_hash,
            evaluation.trace.input_hash,
        )
        _append_diff(
            differences,
            "trace_id",
            persisted_trace_id,
            recomputed_trace_id,
        )

        for key in sorted(set(persisted_component_scores.keys()) | set(recomputed_component_scores.keys())):
            expected = persisted_component_scores.get(key)
            actual = recomputed_component_scores.get(key)
            if expected is None:
                differences.append(
                    ReplayDifference(
                        field=f"component_scores.{key}",
                        expected="<missing>",
                        actual=f"{actual:.6f}",
                    )
                )
                continue
            if actual is None:
                differences.append(
                    ReplayDifference(
                        field=f"component_scores.{key}",
                        expected=f"{expected:.6f}",
                        actual="<missing>",
                    )
                )
                continue
            if round(expected, 6) != round(actual, 6):
                differences.append(
                    ReplayDifference(
                        field=f"component_scores.{key}",
                        expected=f"{expected:.6f}",
                        actual=f"{actual:.6f}",
                    )
                )

        if persisted_explanation != recomputed_explanation:
            differences.append(
                ReplayDifference(
                    field="explanation",
                    expected=json.dumps(persisted_explanation, sort_keys=True),
                    actual=json.dumps(recomputed_explanation, sort_keys=True),
                )
            )

        status = "PASS" if not differences else "FAIL"
        return ReplayVerificationReport(
            status=status,
            proposal_version_id=proposal_version_id,
            persisted_trace_id=persisted_trace_id,
            recomputed_trace_id=recomputed_trace_id,
            persisted_input_hash=lineage.input_snapshot.input_hash,
            recomputed_input_hash=evaluation.trace.input_hash,
            differences=tuple(differences),
        )


def _append_diff(differences: list[ReplayDifference], field: str, expected: str, actual: str) -> None:
    if expected != actual:
        differences.append(ReplayDifference(field=field, expected=expected, actual=actual))


def _read_only_engine() -> RecommendationDecisionEngine:
    # Evaluate-only engine: repositories are in-memory and not persisted.
    return RecommendationDecisionEngine(
        proposal_repository=InMemoryRecommendationProposalRepository(),
        version_repository=InMemoryRecommendationProposalVersionRepository(),
        snapshot_repository=InMemoryRecommendationSnapshotRepository(),
        reason_repository=InMemoryRecommendationReasonRepository(),
        trace_repository=InMemoryRecommendationTraceRepository(),
        strategies=default_recommendation_strategies(),
    )


def _input_from_snapshot_payload(canonical_payload_json: str) -> RecommendationEngineInput:
    payload = json.loads(canonical_payload_json)

    generated_at = _parse_dt(payload["generated_at"])
    proposal = payload["proposal"]
    thesis_health = payload["thesis_health"]
    portfolio = payload["portfolio_context"]

    claims = tuple(
        ThesisClaim(
            claim_id=str(row["claim_id"]),
            thesis_version_id=str(thesis_health["thesis_version_id"]),
            thesis_id=None,
            claim_key=str(row["claim_key"]),
            claim_text=f"replay:{row['claim_key']}",
            claim_type=str(row["claim_type"]),
            status=ClaimStatus(str(row["status"])),
            active_from=generated_at,
            active_to=None,
            created_at=generated_at,
            updated_at=generated_at,
        )
        for row in payload.get("claims", [])
    )

    evidence_items = tuple(
        EvidenceItem(
            evidence_id=str(row["evidence_id"]),
            source_id=str(row["source_id"]),
            title=f"replay:{row['evidence_id']}",
            excerpt="replay",
            content_hash=None,
            as_of_date=str(row.get("as_of_date") or ""),
            metadata_json="{}",
            created_at=generated_at,
        )
        for row in payload.get("evidence", [])
    )

    interpretations = tuple(
        ClaimEvidenceInterpretation(
            interpretation_id=str(row["interpretation_id"]),
            claim_id=str(row["claim_id"]),
            evidence_id=str(row["evidence_id"]),
            relation=InterpretationRelation(str(row["relation"])),
            strength=str(row["strength"]),
            note=None,
            effective_from=generated_at,
            effective_to=None,
            supersedes_interpretation_id=None,
            superseded_by_interpretation_id=None,
            created_at=generated_at,
        )
        for row in payload.get("interpretations", [])
    )

    return RecommendationEngineInput(
        proposal_id=str(proposal["proposal_id"]),
        target_type=str(proposal["target_type"]),
        target_key=str(proposal["target_key"]),
        scope=str(proposal["scope"]),
        thesis_version_id=str(thesis_health["thesis_version_id"]),
        generated_at=generated_at,
        thesis_health_snapshot=ThesisHealthSnapshot(
            thesis_version_id=str(thesis_health["thesis_version_id"]),
            computation_version=str(thesis_health["computation_version"]),
            computed_at=_parse_dt(thesis_health["computed_at"]),
            evidence_freshness=float(thesis_health["evidence_freshness"]),
            evidence_quality=float(thesis_health["evidence_quality"]),
            supporting_strength=float(thesis_health["supporting_strength"]),
            contradictory_strength=float(thesis_health["contradictory_strength"]),
            provenance_completeness=float(thesis_health["provenance_completeness"]),
            thesis_health_index=float(thesis_health["thesis_health_index"]),
        ),
        claims=claims,
        evidence_items=evidence_items,
        interpretations=interpretations,
        portfolio_context=PortfolioContextSnapshot(
            has_existing_position=bool(portfolio["has_existing_position"]),
            current_weight=float(portfolio["current_weight"]),
            target_weight=float(portfolio["target_weight"]),
            max_position_weight=float(portfolio["max_position_weight"]),
            concentration_risk=float(portfolio["concentration_risk"]),
            liquidity_risk=float(portfolio["liquidity_risk"]),
            portfolio_underweight_signal=float(portfolio["portfolio_underweight_signal"]),
            opportunity_signal=float(portfolio["opportunity_signal"]),
            valuation_signal=float(portfolio["valuation_signal"]),
            expected_return_signal=float(portfolio["expected_return_signal"]),
            relationship_signal=float(portfolio["relationship_signal"]),
        ),
        strategy_key=str(proposal["strategy_key"]),
        metadata={str(key): str(value) for key, value in payload.get("metadata", {}).items()},
    )


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)