from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from piios_backend.prospective_ledger.capture import ProspectiveLedgerCaptureService
from piios_backend.prospective_ledger.models import canonical_hash
from piios_backend.prospective_ledger.store import ProspectiveLedgerStore
from piios_backend.schemas.recommendation import (
    AllocationRecommendation,
    PortfolioObservation,
    PortfolioRecommendationResponse,
    RecommendationEvidence,
    RecommendationLimitation,
    RecommendationScoreComponent,
)


def _response(as_of_timestamp: str) -> PortfolioRecommendationResponse:
    components = [
        RecommendationScoreComponent(name="quality", value=70.0, weight=0.28, status="AVAILABLE", explanation="q"),
        RecommendationScoreComponent(name="growth", value=65.0, weight=0.17, status="AVAILABLE", explanation="g"),
        RecommendationScoreComponent(name="valuation", value=60.0, weight=0.20, status="AVAILABLE", explanation="v"),
        RecommendationScoreComponent(name="momentum", value=55.0, weight=0.20, status="AVAILABLE", explanation="m"),
        RecommendationScoreComponent(name="risk", value=80.0, weight=0.15, status="AVAILABLE", explanation="r"),
    ]
    evidence = [RecommendationEvidence(code="EVIDENCE_COVERAGE", detail="0.9", source="test")]
    rec = AllocationRecommendation(
        action="BUY",
        ticker="AAA.NS",
        instrument_name="AAA",
        portfolio_role="UNAVAILABLE",
        current_value=0.0,
        current_weight=0.0,
        proposed_allocation=1000.0,
        proposed_total_value=1000.0,
        post_weight=0.2,
        score=72.5,
        confidence=0.8,
        market_data_provider="yfinance",
        market_data_mode="LIVE",
        market_data_as_of=as_of_timestamp,
        is_stale=False,
        fallback_reason=None,
        seeded_input=False,
        rationale="test",
        diversification_contribution="test",
        risks=[],
        unavailable_inputs=[],
        conditions_to_change=[],
        components=components,
        evidence=evidence,
        diagnostics={
            "trace": "ok",
            "fundamental_source_retrieval_timestamp": as_of_timestamp,
        },
    )
    return PortfolioRecommendationResponse(
        recommendation_id="r1",
        status="READY",
        as_of_timestamp=as_of_timestamp,
        market_data_provider="yfinance",
        market_data_mode="LIVE",
        input_freshness="fresh",
        investable_amount=5000.0,
        allocation_total=1000.0,
        allocation_difference=4000.0,
        overall_confidence=0.8,
        advisory_only=True,
        portfolio_observations=[PortfolioObservation(code="x", severity="INFO", detail="ok")],
        recommendations=[rec],
        top_ranked_candidates=[
            {
                "ticker": "AAA.NS",
                "discovery_score": 77.0,
                "security_attractiveness_score": 70.0,
                "portfolio_suitability_score": 74.0,
                "evidence_coverage": 0.9,
            }
        ],
        assumptions=[],
        limitations=[RecommendationLimitation(code="ADVISORY_ONLY", detail="advisory", severity="INFO")],
    )


def test_hash_determinism_and_order_invariance() -> None:
    payload_a = {"a": 1, "b": 2, "nested": {"x": 1, "y": 2}}
    payload_b = {"nested": {"y": 2, "x": 1}, "b": 2, "a": 1}
    assert canonical_hash(payload_a) == canonical_hash(payload_b)


def test_hash_changes_when_payload_changes() -> None:
    payload_a = {"a": 1}
    payload_b = {"a": 2}
    assert canonical_hash(payload_a) != canonical_hash(payload_b)


def test_immutable_append_and_later_decision_new_record(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger.db"
    store = ProspectiveLedgerStore(db_path)
    capture = ProspectiveLedgerCaptureService(store)

    first = capture.capture_response(
        response=_response("2026-08-12T10:00:00Z"),
        strategy_id="PIIOS_CORE",
        engine_version="WAVE_3_1_RECOMMENDATION_MVP",
        git_commit_sha="abc123",
        config_version="cfg-v1",
        universe_version="u-v1",
    )
    second = capture.capture_response(
        response=_response("2026-08-13T10:00:00Z"),
        strategy_id="PIIOS_CORE",
        engine_version="WAVE_3_1_RECOMMENDATION_MVP",
        git_commit_sha="abc123",
        config_version="cfg-v1",
        universe_version="u-v1",
    )

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].decision_id != second[0].decision_id
    assert first[0].ticker == second[0].ticker == "AAA.NS"

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM prospective_decisions").fetchone()[0]
        rows = conn.execute(
            "SELECT decision_id, strategy_id, engine_version, git_commit_sha, market_source_retrieval_timestamp, fundamental_source_retrieval_timestamp, factor_payload_hash FROM prospective_decisions ORDER BY run_timestamp ASC"
        ).fetchall()

    assert count == 2
    assert rows[0][1] == "PIIOS_CORE"
    assert rows[0][2] == "WAVE_3_1_RECOMMENDATION_MVP"
    assert rows[0][3] == "abc123"
    assert rows[0][4] == "2026-08-12T10:00:00Z"
    assert rows[0][5] == "2026-08-12T10:00:00Z"
    assert rows[0][6] is not None
    assert rows[0][0] != rows[1][0]
