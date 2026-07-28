from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, create_engine

from piios.decision_contracts.application.decision_engine import RecommendationDecisionEngine
from piios.decision_contracts.application.recommendation_reconstruction_service import RecommendationReconstructionService
from piios.decision_contracts.application.recommendation_replay_verification_service import RecommendationReplayVerificationService
from piios.decision_contracts.domain.decision import InvestmentDecision
from piios.decision_contracts.domain.enums import DecisionState
from piios.decision_contracts.infrastructure.in_memory_repositories import (
    InMemoryInvestmentDecisionRepository,
    InMemoryRecommendationProposalRepository,
    InMemoryRecommendationProposalVersionRepository,
    InMemoryRecommendationReasonRepository,
    InMemoryRecommendationSnapshotRepository,
    InMemoryRecommendationTraceRepository,
)
from piios.decision_contracts.infrastructure.sqlmodel_repositories import (
    SQLModelInvestmentDecisionRepository,
    SQLModelRecommendationProposalRepository,
    SQLModelRecommendationProposalVersionRepository,
    SQLModelRecommendationReasonRepository,
    SQLModelRecommendationSnapshotRepository,
    SQLModelRecommendationTraceRepository,
)
from piios.decision_contracts.tests.functional_acceptance_helpers import build_input, scenario_catalog
from piios_backend.core.config import settings


class FailingTraceRepository(SQLModelRecommendationTraceRepository):
    def create_trace_uncommitted(self, trace):
        raise RuntimeError("trace persistence failure")


class FailingCommitProposalRepository(SQLModelRecommendationProposalRepository):
    def commit(self) -> None:
        raise RuntimeError("proposal commit failure")


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
            ) VALUES (:thesis_id, 'NVDA', 'RESEARCHED', 1, :ts, :ts, NULL, NULL)
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

    source_ids: set[str] = set()
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

    conn.execute(sa.text("DELETE FROM decision_recommendation_trace_entries WHERE trace_id IN (SELECT trace_id FROM decision_recommendation_traces WHERE proposal_id = :proposal_id)"), {"proposal_id": proposal_id})
    conn.execute(sa.text("DELETE FROM decision_recommendation_traces WHERE proposal_id = :proposal_id"), {"proposal_id": proposal_id})
    conn.execute(sa.text("DELETE FROM decision_investment_decisions WHERE proposal_version_id IN (SELECT proposal_version_id FROM decision_recommendation_proposal_versions WHERE proposal_id = :proposal_id)"), {"proposal_id": proposal_id})
    conn.execute(sa.text("DELETE FROM decision_recommendation_reasons WHERE proposal_version_id IN (SELECT proposal_version_id FROM decision_recommendation_proposal_versions WHERE proposal_id = :proposal_id)"), {"proposal_id": proposal_id})
    conn.execute(sa.text("DELETE FROM decision_recommendation_claim_links WHERE proposal_version_id IN (SELECT proposal_version_id FROM decision_recommendation_proposal_versions WHERE proposal_id = :proposal_id)"), {"proposal_id": proposal_id})
    conn.execute(sa.text("DELETE FROM decision_recommendation_evidence_links WHERE proposal_version_id IN (SELECT proposal_version_id FROM decision_recommendation_proposal_versions WHERE proposal_id = :proposal_id)"), {"proposal_id": proposal_id})
    conn.execute(sa.text("DELETE FROM decision_recommendation_input_snapshots WHERE proposal_version_id IN (SELECT proposal_version_id FROM decision_recommendation_proposal_versions WHERE proposal_id = :proposal_id)"), {"proposal_id": proposal_id})
    conn.execute(sa.text("DELETE FROM decision_recommendation_proposal_versions WHERE proposal_id = :proposal_id"), {"proposal_id": proposal_id})
    conn.execute(sa.text("DELETE FROM decision_recommendation_proposals WHERE proposal_id = :proposal_id"), {"proposal_id": proposal_id})

    conn.execute(sa.text("DELETE FROM claim_evidence_interpretations WHERE interpretation_id = ANY(:ids)"), {"ids": interp_ids})
    conn.execute(sa.text("DELETE FROM thesis_claims WHERE claim_id = ANY(:ids)"), {"ids": claim_ids})
    conn.execute(sa.text("DELETE FROM evidence_items WHERE evidence_id = ANY(:ids)"), {"ids": evidence_ids})
    conn.execute(sa.text("DELETE FROM evidence_sources WHERE source_id = ANY(:ids)"), {"ids": source_ids})
    conn.execute(sa.text("DELETE FROM thesis_versions WHERE thesis_id = :thesis_id"), {"thesis_id": thesis_id})
    conn.execute(sa.text("DELETE FROM thesis_roots WHERE thesis_id = :thesis_id"), {"thesis_id": thesis_id})


def _with_seed(engine_sql, data):
    with engine_sql.begin() as conn:
        _seed_postgres_context(conn, data)
    try:
        yield
    finally:
        with engine_sql.begin() as conn:
            _cleanup_postgres_context(conn, data)


def _inmemory_engine_service():
    proposal_repo = InMemoryRecommendationProposalRepository()
    version_repo = InMemoryRecommendationProposalVersionRepository()
    snapshot_repo = InMemoryRecommendationSnapshotRepository()
    reason_repo = InMemoryRecommendationReasonRepository()
    trace_repo = InMemoryRecommendationTraceRepository()
    decision_repo = InMemoryInvestmentDecisionRepository()

    engine = RecommendationDecisionEngine(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        snapshot_repository=snapshot_repo,
        reason_repository=reason_repo,
        trace_repository=trace_repo,
    )
    service = RecommendationReconstructionService(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        snapshot_repository=snapshot_repo,
        trace_repository=trace_repo,
        reason_repository=reason_repo,
        decision_repository=decision_repo,
    )
    return engine, service, decision_repo


def test_scenario_a_reconstruct_from_decision_id_postgres() -> None:
    engine_sql = create_engine(settings.db_url)
    data = build_input(scenario_catalog()["A_strong_positive"])

    for _ in _with_seed(engine_sql, data):
        with Session(engine_sql) as session:
            engine = RecommendationDecisionEngine(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
            )
            generated = engine.generate_recommendation(data)

            decision_repo = SQLModelInvestmentDecisionRepository(session)
            decision_repo.create(
                InvestmentDecision(
                    decision_id=f"decision:m4:pg:{uuid.uuid4().hex[:8]}",
                    proposal_version_id=generated.proposal_version.proposal_version_id,
                    state=DecisionState.ACCEPTED,
                    reason_code="ALIGNED",
                    decided_at=datetime(2026, 7, 28, 14, 0, tzinfo=timezone.utc),
                )
            )
            decision_id = decision_repo.get_latest_for_proposal_version(generated.proposal_version.proposal_version_id).decision_id

            service = RecommendationReconstructionService(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                decision_repository=decision_repo,
            )
            lineage = service.reconstruct_by_investment_decision_id(decision_id)

            assert lineage.trace.proposal_version_id == generated.proposal_version.proposal_version_id
            assert service.compare_reconstructed_proposal_output(generated.proposal_version.proposal_version_id)


def test_scenario_b_replay_and_scenario_c_changed_input_postgres() -> None:
    engine_sql = create_engine(settings.db_url)
    data = build_input(scenario_catalog()["C_mixed_conflicting"])

    for _ in _with_seed(engine_sql, data):
        with Session(engine_sql) as session:
            engine = RecommendationDecisionEngine(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
            )

            first = engine.generate_recommendation(data)
            second = engine.generate_recommendation(data)
            assert first.proposal_version.proposal_version_id == second.proposal_version.proposal_version_id
            assert first.recommendation_trace.trace_id == second.recommendation_trace.trace_id

            changed = replace(data, thesis_health_snapshot=replace(data.thesis_health_snapshot, evidence_quality=0.35))
            third = engine.generate_recommendation(changed)
            assert third.proposal_version.version_number == 2
            assert third.recommendation_trace.trace_id != first.recommendation_trace.trace_id


def test_scenario_d_atomic_rollback_failure_points_postgres() -> None:
    engine_sql = create_engine(settings.db_url)
    data = build_input(scenario_catalog()["B_strong_negative"])

    for _ in _with_seed(engine_sql, data):
        with Session(engine_sql) as session:
            engine_trace_fail = RecommendationDecisionEngine(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                trace_repository=FailingTraceRepository(session),
            )
            with pytest.raises(RuntimeError, match="trace persistence failure"):
                engine_trace_fail.generate_recommendation(data)

        with Session(engine_sql) as session:
            proposal_count = session.execute(sa.text("SELECT COUNT(*) FROM decision_recommendation_proposals WHERE proposal_id=:proposal_id"), {"proposal_id": data.proposal_id}).scalar_one()
            trace_count = session.execute(sa.text("SELECT COUNT(*) FROM decision_recommendation_traces WHERE proposal_id=:proposal_id"), {"proposal_id": data.proposal_id}).scalar_one()
            assert proposal_count == 0
            assert trace_count == 0

        with Session(engine_sql) as session:
            engine_commit_fail = RecommendationDecisionEngine(
                proposal_repository=FailingCommitProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
            )
            with pytest.raises(RuntimeError, match="proposal commit failure"):
                engine_commit_fail.generate_recommendation(data)

        with Session(engine_sql) as session:
            proposal_count = session.execute(sa.text("SELECT COUNT(*) FROM decision_recommendation_proposals WHERE proposal_id=:proposal_id"), {"proposal_id": data.proposal_id}).scalar_one()
            trace_count = session.execute(sa.text("SELECT COUNT(*) FROM decision_recommendation_traces WHERE proposal_id=:proposal_id"), {"proposal_id": data.proposal_id}).scalar_one()
            assert proposal_count == 0
            assert trace_count == 0


def test_scenario_f_parity_inmemory_vs_postgres() -> None:
    engine_sql = create_engine(settings.db_url)
    data = build_input(scenario_catalog()["E_stale_evidence"])

    for _ in _with_seed(engine_sql, data):
        inmem_engine, inmem_service, inmem_decisions = _inmemory_engine_service()
        inmem_result = inmem_engine.generate_recommendation(data)
        inmem_decisions.create(
            InvestmentDecision(
                decision_id="decision:m4:inmem:f",
                proposal_version_id=inmem_result.proposal_version.proposal_version_id,
                state=DecisionState.ACCEPTED,
                reason_code="ALIGNED",
                decided_at=datetime(2026, 7, 28, 14, 30, tzinfo=timezone.utc),
            )
        )
        inmem_expl = inmem_service.retrieve_authoritative_explanation(inmem_result.proposal_version.proposal_version_id)

        with Session(engine_sql) as session:
            pg_engine = RecommendationDecisionEngine(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
            )
            pg_result = pg_engine.generate_recommendation(data)
            pg_decisions = SQLModelInvestmentDecisionRepository(session)
            pg_decisions.create(
                InvestmentDecision(
                    decision_id=f"decision:m4:pg:f:{uuid.uuid4().hex[:8]}",
                    proposal_version_id=pg_result.proposal_version.proposal_version_id,
                    state=DecisionState.ACCEPTED,
                    reason_code="ALIGNED",
                    decided_at=datetime(2026, 7, 28, 14, 30, tzinfo=timezone.utc),
                )
            )

            pg_service = RecommendationReconstructionService(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                decision_repository=pg_decisions,
            )
            pg_expl = pg_service.retrieve_authoritative_explanation(pg_result.proposal_version.proposal_version_id)

        assert inmem_result.proposal_version.action_proposal.action == pg_result.proposal_version.action_proposal.action
        assert [row.entry_type for row in inmem_result.recommendation_trace.entries] == [row.entry_type for row in pg_result.recommendation_trace.entries]
        assert inmem_expl.recommendation_action == pg_expl.recommendation_action
        assert inmem_expl.summary_text == pg_expl.summary_text


def test_replay_verification_pass_and_determinism_postgres() -> None:
    engine_sql = create_engine(settings.db_url)
    data = build_input(scenario_catalog()["A_strong_positive"])

    for _ in _with_seed(engine_sql, data):
        with Session(engine_sql) as session:
            engine = RecommendationDecisionEngine(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
            )
            generated = engine.generate_recommendation(data)

            reconstruction = RecommendationReconstructionService(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                decision_repository=SQLModelInvestmentDecisionRepository(session),
            )
            replay = RecommendationReplayVerificationService(reconstruction)

            first = replay.verify_by_proposal_version(generated.proposal_version.proposal_version_id)
            second = replay.verify_by_proposal_version(generated.proposal_version.proposal_version_id)

            assert first.status == "PASS"
            assert first.differences == tuple()
            assert first == second


def test_replay_verification_failure_reports_differences_postgres() -> None:
    engine_sql = create_engine(settings.db_url)
    data = build_input(scenario_catalog()["B_strong_negative"])

    for _ in _with_seed(engine_sql, data):
        with Session(engine_sql) as session:
            engine = RecommendationDecisionEngine(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
            )
            generated = engine.generate_recommendation(data)

            snapshot_json = session.execute(
                sa.text(
                    """
                    SELECT canonical_payload_json
                    FROM decision_recommendation_input_snapshots
                    WHERE snapshot_id=:snapshot_id
                    """
                ),
                {"snapshot_id": generated.input_snapshot.snapshot_id},
            ).scalar_one()
            payload = json.loads(snapshot_json)
            payload["thesis_health"]["thesis_health_index"] = 0.95
            payload["thesis_health"]["evidence_quality"] = 0.95
            payload["thesis_health"]["contradictory_strength"] = 0.01
            session.execute(
                sa.text(
                    """
                    UPDATE decision_recommendation_input_snapshots
                    SET canonical_payload_json=:payload
                    WHERE snapshot_id=:snapshot_id
                    """
                ),
                {
                    "snapshot_id": generated.input_snapshot.snapshot_id,
                    "payload": json.dumps(payload, sort_keys=True, separators=(",", ":")),
                },
            )
            session.commit()

            reconstruction = RecommendationReconstructionService(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                decision_repository=SQLModelInvestmentDecisionRepository(session),
            )
            replay = RecommendationReplayVerificationService(reconstruction)
            report = replay.verify_by_proposal_version(generated.proposal_version.proposal_version_id)

            assert report.status == "FAIL"
            assert report.differences
            assert any(row.field in {"action", "overall_score", "deterministic_input_hash"} for row in report.differences)


def test_replay_verification_failure_reports_persisted_proposal_differences_postgres() -> None:
    engine_sql = create_engine(settings.db_url)
    data = build_input(scenario_catalog()["A_strong_positive"])

    for _ in _with_seed(engine_sql, data):
        with Session(engine_sql) as session:
            engine = RecommendationDecisionEngine(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
            )
            generated = engine.generate_recommendation(data)

            session.execute(
                sa.text(
                    """
                    UPDATE decision_recommendation_proposal_versions
                    SET action='SELL', action_note='strategy=balanced-v1; score=0.111111'
                    WHERE proposal_version_id=:proposal_version_id
                    """
                ),
                {"proposal_version_id": generated.proposal_version.proposal_version_id},
            )
            session.commit()

            reconstruction = RecommendationReconstructionService(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                decision_repository=SQLModelInvestmentDecisionRepository(session),
            )
            replay = RecommendationReplayVerificationService(reconstruction)
            report = replay.verify_by_proposal_version(generated.proposal_version.proposal_version_id)

            assert report.status == "FAIL"
            assert any(row.field == "persisted_proposal.action" for row in report.differences)
            assert any(row.field == "persisted_proposal.overall_score" for row in report.differences)


def test_audit_trace_is_not_deleted_by_parent_delete_postgres() -> None:
    engine_sql = create_engine(settings.db_url)
    data = build_input(scenario_catalog()["C_mixed_conflicting"])

    for _ in _with_seed(engine_sql, data):
        with Session(engine_sql) as session:
            engine = RecommendationDecisionEngine(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
            )
            generated = engine.generate_recommendation(data)
            proposal_id = generated.proposal.proposal_id
            proposal_version_id = generated.proposal_version.proposal_version_id
            snapshot_id = generated.input_snapshot.snapshot_id
            trace_id = generated.recommendation_trace.trace_id

            with pytest.raises(IntegrityError):
                session.execute(
                    sa.text(
                        "DELETE FROM decision_recommendation_proposals WHERE proposal_id=:proposal_id"
                    ),
                    {"proposal_id": proposal_id},
                )
                session.commit()
            session.rollback()

            _assert_parent_and_trace_integrity(
                session,
                proposal_id=proposal_id,
                proposal_version_id=proposal_version_id,
                snapshot_id=snapshot_id,
                trace_id=trace_id,
            )

            reconstruction = RecommendationReconstructionService(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                decision_repository=SQLModelInvestmentDecisionRepository(session),
            )
            lineage = reconstruction.reconstruct_by_proposal_version(proposal_version_id)
            assert lineage.trace.trace_id == trace_id


def _assert_parent_and_trace_integrity(session: Session, *, proposal_id: str, proposal_version_id: str, snapshot_id: str, trace_id: str) -> None:
    proposal_count = session.execute(
        sa.text("SELECT COUNT(*) FROM decision_recommendation_proposals WHERE proposal_id=:proposal_id"),
        {"proposal_id": proposal_id},
    ).scalar_one()
    proposal_version_count = session.execute(
        sa.text(
            "SELECT COUNT(*) FROM decision_recommendation_proposal_versions WHERE proposal_version_id=:proposal_version_id"
        ),
        {"proposal_version_id": proposal_version_id},
    ).scalar_one()
    snapshot_count = session.execute(
        sa.text("SELECT COUNT(*) FROM decision_recommendation_input_snapshots WHERE snapshot_id=:snapshot_id"),
        {"snapshot_id": snapshot_id},
    ).scalar_one()
    trace_count = session.execute(
        sa.text("SELECT COUNT(*) FROM decision_recommendation_traces WHERE trace_id=:trace_id"),
        {"trace_id": trace_id},
    ).scalar_one()
    trace_entries_count = session.execute(
        sa.text("SELECT COUNT(*) FROM decision_recommendation_trace_entries WHERE trace_id=:trace_id"),
        {"trace_id": trace_id},
    ).scalar_one()

    assert proposal_count == 1
    assert proposal_version_count == 1
    assert snapshot_count == 1
    assert trace_count == 1
    assert trace_entries_count > 0


def test_audit_trace_is_not_deleted_by_proposal_version_delete_postgres() -> None:
    engine_sql = create_engine(settings.db_url)
    data = build_input(scenario_catalog()["A_strong_positive"])

    for _ in _with_seed(engine_sql, data):
        with Session(engine_sql) as session:
            engine = RecommendationDecisionEngine(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
            )
            generated = engine.generate_recommendation(data)

            proposal_id = generated.proposal.proposal_id
            proposal_version_id = generated.proposal_version.proposal_version_id
            snapshot_id = generated.input_snapshot.snapshot_id
            trace_id = generated.recommendation_trace.trace_id

            with pytest.raises(IntegrityError):
                session.execute(
                    sa.text(
                        """
                        DELETE FROM decision_recommendation_proposal_versions
                        WHERE proposal_version_id=:proposal_version_id
                        """
                    ),
                    {"proposal_version_id": proposal_version_id},
                )
                session.commit()
            session.rollback()

            _assert_parent_and_trace_integrity(
                session,
                proposal_id=proposal_id,
                proposal_version_id=proposal_version_id,
                snapshot_id=snapshot_id,
                trace_id=trace_id,
            )

            reconstruction = RecommendationReconstructionService(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                decision_repository=SQLModelInvestmentDecisionRepository(session),
            )
            lineage = reconstruction.reconstruct_by_proposal_version(proposal_version_id)
            assert lineage.trace.trace_id == trace_id


def test_audit_trace_is_not_deleted_by_snapshot_delete_postgres() -> None:
    engine_sql = create_engine(settings.db_url)
    data = build_input(scenario_catalog()["B_strong_negative"])

    for _ in _with_seed(engine_sql, data):
        with Session(engine_sql) as session:
            engine = RecommendationDecisionEngine(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
            )
            generated = engine.generate_recommendation(data)

            proposal_id = generated.proposal.proposal_id
            proposal_version_id = generated.proposal_version.proposal_version_id
            snapshot_id = generated.input_snapshot.snapshot_id
            trace_id = generated.recommendation_trace.trace_id

            with pytest.raises(IntegrityError):
                session.execute(
                    sa.text(
                        "DELETE FROM decision_recommendation_input_snapshots WHERE snapshot_id=:snapshot_id"
                    ),
                    {"snapshot_id": snapshot_id},
                )
                session.commit()
            session.rollback()

            _assert_parent_and_trace_integrity(
                session,
                proposal_id=proposal_id,
                proposal_version_id=proposal_version_id,
                snapshot_id=snapshot_id,
                trace_id=trace_id,
            )

            reconstruction = RecommendationReconstructionService(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                decision_repository=SQLModelInvestmentDecisionRepository(session),
            )
            lineage = reconstruction.reconstruct_by_proposal_version(proposal_version_id)
            assert lineage.trace.trace_id == trace_id


def test_direct_trace_deletion_cascades_only_owned_trace_entries_postgres() -> None:
    engine_sql = create_engine(settings.db_url)
    data = build_input(scenario_catalog()["D_missing_evidence"])

    for _ in _with_seed(engine_sql, data):
        with Session(engine_sql) as session:
            engine = RecommendationDecisionEngine(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
            )
            generated = engine.generate_recommendation(data)
            trace_id = generated.recommendation_trace.trace_id

            entries_before = session.execute(
                sa.text("SELECT COUNT(*) FROM decision_recommendation_trace_entries WHERE trace_id=:trace_id"),
                {"trace_id": trace_id},
            ).scalar_one()
            assert entries_before > 0

            session.execute(
                sa.text("DELETE FROM decision_recommendation_traces WHERE trace_id=:trace_id"),
                {"trace_id": trace_id},
            )
            session.commit()

            trace_after = session.execute(
                sa.text("SELECT COUNT(*) FROM decision_recommendation_traces WHERE trace_id=:trace_id"),
                {"trace_id": trace_id},
            ).scalar_one()
            entries_after = session.execute(
                sa.text("SELECT COUNT(*) FROM decision_recommendation_trace_entries WHERE trace_id=:trace_id"),
                {"trace_id": trace_id},
            ).scalar_one()
            proposal_after = session.execute(
                sa.text("SELECT COUNT(*) FROM decision_recommendation_proposals WHERE proposal_id=:proposal_id"),
                {"proposal_id": generated.proposal.proposal_id},
            ).scalar_one()

            assert trace_after == 0
            assert entries_after == 0
            assert proposal_after == 1
