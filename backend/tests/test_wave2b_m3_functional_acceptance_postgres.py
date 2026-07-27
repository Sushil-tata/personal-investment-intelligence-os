from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlmodel import Session, create_engine

from piios.decision_contracts.application.decision_engine import RecommendationDecisionEngine
from piios.decision_contracts.infrastructure.in_memory_repositories import (
    InMemoryRecommendationProposalRepository,
    InMemoryRecommendationProposalVersionRepository,
    InMemoryRecommendationReasonRepository,
    InMemoryRecommendationSnapshotRepository,
    InMemoryRecommendationTraceRepository,
)
from piios.decision_contracts.infrastructure.sqlmodel_repositories import (
    SQLModelRecommendationProposalRepository,
    SQLModelRecommendationProposalVersionRepository,
    SQLModelRecommendationReasonRepository,
    SQLModelRecommendationSnapshotRepository,
    SQLModelRecommendationTraceRepository,
)
from piios.decision_contracts.tests.functional_acceptance_helpers import build_input, scenario_catalog
from piios_backend.core.config import settings


class FailingReasonRepository(SQLModelRecommendationReasonRepository):
    def create_many_uncommitted(self, reasons):
        raise RuntimeError("injected failure")


def _build_inmemory_engine() -> RecommendationDecisionEngine:
    return RecommendationDecisionEngine(
        proposal_repository=InMemoryRecommendationProposalRepository(),
        version_repository=InMemoryRecommendationProposalVersionRepository(),
        snapshot_repository=InMemoryRecommendationSnapshotRepository(),
        reason_repository=InMemoryRecommendationReasonRepository(),
        trace_repository=InMemoryRecommendationTraceRepository(),
    )


def _build_postgres_engine(session: Session, *, fail_reasons: bool = False) -> RecommendationDecisionEngine:
    reason_repo = FailingReasonRepository(session) if fail_reasons else SQLModelRecommendationReasonRepository(session)
    return RecommendationDecisionEngine(
        proposal_repository=SQLModelRecommendationProposalRepository(session),
        version_repository=SQLModelRecommendationProposalVersionRepository(session),
        snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
        reason_repository=reason_repo,
        trace_repository=SQLModelRecommendationTraceRepository(session),
    )


def _seed_postgres_context(conn: sa.Connection, data) -> None:
    thesis_id = data.claims[0].thesis_id
    version_id = data.thesis_version_id
    ts = data.generated_at.isoformat()

    conn.execute(
        sa.text(
            """
            INSERT INTO thesis_roots (
                thesis_id, ticker, lifecycle_status, current_version_number,
                created_at, updated_at, closed_reason, closed_at
            ) VALUES (
                :thesis_id, 'NVDA', 'RESEARCHED', 1,
                :ts, :ts, NULL, NULL
            )
            """
        ),
        {"thesis_id": thesis_id, "ts": ts},
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO thesis_versions (
                version_id, thesis_id, version_number,
                asset_name, theme, bucket, thesis,
                bull_case, bear_case, why_now, why_not_now,
                invalidation_trigger, valuation_notes, expected_holding_period,
                source_documents, confidence_score, status, created_at
            ) VALUES (
                :version_id, :thesis_id, 1,
                'NVIDIA', 'AI', 'Strategic Alpha', 'Core',
                'Bull', 'Bear', 'Now', 'Not now',
                'Trigger', 'Valuation', '2-5 years',
                '["rd"]', 75.0, 'RESEARCHED', :ts
            )
            """
        ),
        {"version_id": version_id, "thesis_id": thesis_id, "ts": ts},
    )

    for claim in data.claims:
        conn.execute(
            sa.text(
                """
                INSERT INTO thesis_claims (
                    claim_id, thesis_version_id, thesis_id, claim_key, claim_text,
                    claim_type, status, active_from, active_to, created_at, updated_at
                ) VALUES (
                    :claim_id, :version_id, :thesis_id, :claim_key, :claim_text,
                    :claim_type, 'ACTIVE', :ts, NULL, :ts, :ts
                )
                """
            ),
            {
                "claim_id": claim.claim_id,
                "version_id": claim.thesis_version_id,
                "thesis_id": claim.thesis_id,
                "claim_key": claim.claim_key,
                "claim_text": claim.claim_text,
                "claim_type": claim.claim_type,
                "ts": claim.created_at.isoformat(),
            },
        )

    source_ids: set[str] = set()
    for evidence in data.evidence_items:
        if evidence.source_id not in source_ids:
            source_ids.add(evidence.source_id)
            conn.execute(
                sa.text(
                    """
                    INSERT INTO evidence_sources (
                        source_id, source_type, publisher, url, source_system,
                        published_at, retrieved_at, credibility_tier, created_at
                    ) VALUES (
                        :source_id, 'RESEARCH', 'Desk', 'https://example.com', 'functional_acceptance_test',
                        :ts, :ts, 'A', :ts
                    )
                    """
                ),
                {"source_id": evidence.source_id, "ts": ts},
            )

        conn.execute(
            sa.text(
                """
                INSERT INTO evidence_items (
                    evidence_id, source_id, title, excerpt, content_hash, as_of_date, metadata_json, created_at
                ) VALUES (
                    :evidence_id, :source_id, :title, :excerpt, :content_hash, :as_of_date, :metadata_json, :ts
                )
                """
            ),
            {
                "evidence_id": evidence.evidence_id,
                "source_id": evidence.source_id,
                "title": evidence.title,
                "excerpt": evidence.excerpt,
                "content_hash": evidence.content_hash,
                "as_of_date": evidence.as_of_date,
                "metadata_json": evidence.metadata_json,
                "ts": evidence.created_at.isoformat(),
            },
        )

    for interp in data.interpretations:
        conn.execute(
            sa.text(
                """
                INSERT INTO claim_evidence_interpretations (
                    interpretation_id, claim_id, evidence_id, relation, strength, note,
                    effective_from, effective_to, supersedes_interpretation_id,
                    superseded_by_interpretation_id, created_at
                ) VALUES (
                    :interpretation_id, :claim_id, :evidence_id, :relation, :strength, :note,
                    :ts, NULL, NULL, NULL, :ts
                )
                """
            ),
            {
                "interpretation_id": interp.interpretation_id,
                "claim_id": interp.claim_id,
                "evidence_id": interp.evidence_id,
                "relation": interp.relation.value,
                "strength": interp.strength,
                "note": interp.note,
                "ts": interp.created_at.isoformat(),
            },
        )


def _cleanup_postgres_context(conn: sa.Connection, data) -> None:
    proposal_id = data.proposal_id
    thesis_id = data.claims[0].thesis_id
    source_ids = [e.source_id for e in data.evidence_items]
    evidence_ids = [e.evidence_id for e in data.evidence_items]
    claim_ids = [c.claim_id for c in data.claims]
    interp_ids = [i.interpretation_id for i in data.interpretations]

    conn.execute(
        sa.text(
            """
            DELETE FROM decision_recommendation_reasons
            WHERE proposal_version_id IN (
                SELECT proposal_version_id FROM decision_recommendation_proposal_versions WHERE proposal_id = :proposal_id
            )
            """
        ),
        {"proposal_id": proposal_id},
    )
    conn.execute(
        sa.text(
            """
            DELETE FROM decision_recommendation_claim_links
            WHERE proposal_version_id IN (
                SELECT proposal_version_id FROM decision_recommendation_proposal_versions WHERE proposal_id = :proposal_id
            )
            """
        ),
        {"proposal_id": proposal_id},
    )
    conn.execute(
        sa.text(
            """
            DELETE FROM decision_recommendation_evidence_links
            WHERE proposal_version_id IN (
                SELECT proposal_version_id FROM decision_recommendation_proposal_versions WHERE proposal_id = :proposal_id
            )
            """
        ),
        {"proposal_id": proposal_id},
    )
    conn.execute(
        sa.text(
            """
            DELETE FROM decision_recommendation_input_snapshots
            WHERE proposal_version_id IN (
                SELECT proposal_version_id FROM decision_recommendation_proposal_versions WHERE proposal_id = :proposal_id
            )
            """
        ),
        {"proposal_id": proposal_id},
    )
    conn.execute(
        sa.text("DELETE FROM decision_recommendation_proposal_versions WHERE proposal_id = :proposal_id"),
        {"proposal_id": proposal_id},
    )
    conn.execute(
        sa.text("DELETE FROM decision_recommendation_proposals WHERE proposal_id = :proposal_id"),
        {"proposal_id": proposal_id},
    )

    conn.execute(sa.text("DELETE FROM claim_evidence_interpretations WHERE interpretation_id = ANY(:ids)"), {"ids": interp_ids})
    conn.execute(sa.text("DELETE FROM thesis_claims WHERE claim_id = ANY(:ids)"), {"ids": claim_ids})
    conn.execute(sa.text("DELETE FROM evidence_items WHERE evidence_id = ANY(:ids)"), {"ids": evidence_ids})
    conn.execute(sa.text("DELETE FROM evidence_sources WHERE source_id = ANY(:ids)"), {"ids": source_ids})
    conn.execute(sa.text("DELETE FROM thesis_versions WHERE thesis_id = :thesis_id"), {"thesis_id": thesis_id})
    conn.execute(sa.text("DELETE FROM thesis_roots WHERE thesis_id = :thesis_id"), {"thesis_id": thesis_id})


def _seed_and_cleanup_wrapper(engine, data):
    with engine.begin() as conn:
        _seed_postgres_context(conn, data)
    try:
        yield
    finally:
        with engine.begin() as conn:
            _cleanup_postgres_context(conn, data)


def test_repository_parity_across_functional_scenarios_postgres_vs_inmemory() -> None:
    engine_sql = create_engine(settings.db_url)
    scenarios = scenario_catalog()

    for scenario_key in (
        "A_strong_positive",
        "B_strong_negative",
        "C_mixed_conflicting",
        "D_missing_evidence",
        "E_stale_evidence",
    ):
        data = build_input(scenarios[scenario_key])
        for _ in _seed_and_cleanup_wrapper(engine_sql, data):
            inmem_engine = _build_inmemory_engine()
            inmem_result = inmem_engine.generate_recommendation(data)

            with Session(engine_sql) as session:
                pg_engine = _build_postgres_engine(session)
                pg_result = pg_engine.generate_recommendation(data)

            assert inmem_result.proposal_version.action_proposal.action == pg_result.proposal_version.action_proposal.action
            assert inmem_result.evaluation.strategy_result.overall_score == pg_result.evaluation.strategy_result.overall_score
            assert inmem_result.proposal_version.priority == pg_result.proposal_version.priority
            assert inmem_result.proposal_version.required_human_review == pg_result.proposal_version.required_human_review


def test_deterministic_replay_and_idempotency_in_postgres() -> None:
    engine_sql = create_engine(settings.db_url)
    data = build_input(scenario_catalog()["C_mixed_conflicting"])

    for _ in _seed_and_cleanup_wrapper(engine_sql, data):
        with Session(engine_sql) as session:
            engine = _build_postgres_engine(session)

            eval_one = engine.evaluate(data)
            eval_two = engine.evaluate(data)
            assert eval_one.trace.input_hash == eval_two.trace.input_hash
            assert eval_one.explanation == eval_two.explanation

            first = engine.generate_recommendation(data)
            second = engine.generate_recommendation(data)
            assert first.proposal_version.proposal_version_id == second.proposal_version.proposal_version_id

            changed = data.__class__(
                proposal_id=data.proposal_id,
                target_type=data.target_type,
                target_key=data.target_key,
                scope=data.scope,
                thesis_version_id=data.thesis_version_id,
                generated_at=data.generated_at,
                thesis_health_snapshot=data.thesis_health_snapshot.__class__(
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
            assert third.input_snapshot.input_hash != first.input_snapshot.input_hash


def test_atomic_rollback_on_injected_failure_in_postgres() -> None:
    engine_sql = create_engine(settings.db_url)
    data = build_input(scenario_catalog()["A_strong_positive"])

    for _ in _seed_and_cleanup_wrapper(engine_sql, data):
        with Session(engine_sql) as session:
            failing_engine = _build_postgres_engine(session, fail_reasons=True)
            with pytest.raises(RuntimeError, match="injected failure"):
                failing_engine.generate_recommendation(data)

        with Session(engine_sql) as session:
            proposal_count = session.execute(
                sa.text("SELECT COUNT(*) FROM decision_recommendation_proposals WHERE proposal_id=:proposal_id"),
                {"proposal_id": data.proposal_id},
            ).scalar_one()
            version_count = session.execute(
                sa.text("SELECT COUNT(*) FROM decision_recommendation_proposal_versions WHERE proposal_id=:proposal_id"),
                {"proposal_id": data.proposal_id},
            ).scalar_one()
            snapshot_count = session.execute(
                sa.text(
                    """
                    SELECT COUNT(*)
                    FROM decision_recommendation_input_snapshots s
                    JOIN decision_recommendation_proposal_versions v
                      ON s.proposal_version_id = v.proposal_version_id
                    WHERE v.proposal_id=:proposal_id
                    """
                ),
                {"proposal_id": data.proposal_id},
            ).scalar_one()

            assert proposal_count == 0
            assert version_count == 0
            assert snapshot_count == 0

        with Session(engine_sql) as session:
            success_engine = _build_postgres_engine(session)
            retry_result = success_engine.generate_recommendation(data)
            assert retry_result.proposal_version.version_number == 1
