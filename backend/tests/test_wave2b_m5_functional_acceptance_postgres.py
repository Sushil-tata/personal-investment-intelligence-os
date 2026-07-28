from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, create_engine

from piios.decision_contracts.application.decision_capture_service import (
    DecisionCaptureRequest,
    DecisionCaptureService,
    DecisionPersistenceError,
    DecisionType,
)
from piios.decision_contracts.application.decision_engine import RecommendationDecisionEngine
from piios.decision_contracts.application.decision_query_service import DecisionQueryService
from piios.decision_contracts.application.diagnostics_service import RecommendationDiagnosticsService
from piios.decision_contracts.application.recommendation_reconstruction_service import RecommendationReconstructionService
from piios.decision_contracts.application.recommendation_replay_verification_service import RecommendationReplayVerificationService
from piios.decision_contracts.infrastructure.sqlmodel_repositories import (
    SQLModelInvestmentDecisionRepository,
    SQLModelRecommendationProposalRepository,
    SQLModelRecommendationProposalVersionRepository,
    SQLModelRecommendationReasonRepository,
    SQLModelRecommendationSnapshotRepository,
    SQLModelRecommendationTraceRepository,
)
from piios.decision_contracts.tests.functional_acceptance_helpers import build_input, scenario_catalog
from piios.thesis.infrastructure.sqlmodel_claim_evidence_repositories import (
    SQLModelEvidenceItemRepository,
    SQLModelThesisClaimRepository,
)
from piios.thesis.infrastructure.sqlmodel_repositories import SQLModelThesisVersionRepository
from piios_backend.core.config import settings


REVISION_HEAD = "head"


def _alembic_config(db_url: str) -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", db_url)
    return config


@pytest.fixture(scope="module")
def pg_engine():
    config = _alembic_config(settings.db_url)
    command.upgrade(config, REVISION_HEAD)
    return create_engine(settings.db_url)


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


class FailingDecisionRepository(SQLModelInvestmentDecisionRepository):
    def create(self, decision):
        raise RuntimeError("decision insert failed")


def _services(session: Session):
    proposal_repo = SQLModelRecommendationProposalRepository(session)
    version_repo = SQLModelRecommendationProposalVersionRepository(session)
    snapshot_repo = SQLModelRecommendationSnapshotRepository(session)
    reason_repo = SQLModelRecommendationReasonRepository(session)
    trace_repo = SQLModelRecommendationTraceRepository(session)
    decision_repo = SQLModelInvestmentDecisionRepository(session)

    reconstruction = RecommendationReconstructionService(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        snapshot_repository=snapshot_repo,
        trace_repository=trace_repo,
        reason_repository=reason_repo,
        decision_repository=decision_repo,
    )
    replay = RecommendationReplayVerificationService(reconstruction)
    diagnostics = RecommendationDiagnosticsService(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        snapshot_repository=snapshot_repo,
        trace_repository=trace_repo,
        decision_repository=decision_repo,
        reconstruction_service=reconstruction,
        replay_verification_service=replay,
        thesis_version_repository=SQLModelThesisVersionRepository(session),
        thesis_claim_repository=SQLModelThesisClaimRepository(session),
        evidence_item_repository=SQLModelEvidenceItemRepository(session),
    )
    capture = DecisionCaptureService(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        decision_repository=decision_repo,
    )
    query = DecisionQueryService(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        decision_repository=decision_repo,
        diagnostics_service=diagnostics,
    )
    return capture, query, diagnostics, decision_repo


def test_wave2b_m5_postgres_functional_acceptance_flow(pg_engine) -> None:
    data = build_input(scenario_catalog()["A_strong_positive"])

    with pg_engine.begin() as conn:
        _seed_postgres_context(conn, data)

    try:
        with Session(pg_engine) as session:
            engine = RecommendationDecisionEngine(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
            )
            generated = engine.generate_recommendation(data)

            capture, query, _, decision_repo = _services(session)

            first = capture.capture(
                DecisionCaptureRequest(
                    proposal_version_id=generated.proposal_version.proposal_version_id,
                    decision_type=DecisionType.ACCEPT,
                    reviewer="rm_001",
                    reason_code="APPROVED",
                    client_request_id="req-1",
                )
            )
            second = capture.capture(
                DecisionCaptureRequest(
                    proposal_version_id=generated.proposal_version.proposal_version_id,
                    decision_type=DecisionType.ACCEPT,
                    reviewer="rm_001",
                    reason_code="APPROVED",
                    client_request_id="req-1",
                )
            )
            third = capture.capture(
                DecisionCaptureRequest(
                    proposal_version_id=generated.proposal_version.proposal_version_id,
                    decision_type=DecisionType.MODIFIED,
                    reviewer="rm_001",
                    reason_code="ADJUST_SIZE",
                    modified_action=generated.proposal_version.action_proposal.action,
                    modified_position_min_weight=0.01,
                    modified_position_max_weight=0.03,
                    client_request_id="req-2",
                )
            )

            assert first.decision_id == second.decision_id
            assert first.decision_id != third.decision_id
            assert len(decision_repo.list_for_proposal_version(generated.proposal_version.proposal_version_id)) == 2

            proposal_detail = query.get_recommendation_proposal_detail(generated.proposal.proposal_id)
            version_detail = query.get_proposal_version_detail(generated.proposal_version.proposal_version_id)
            latest = query.get_latest_decision_for_proposal_version(generated.proposal_version.proposal_version_id)
            traceability = query.get_traceability_diagnostic(generated.proposal_version.proposal_version_id)
            confidence = query.get_confidence_diagnostic(generated.proposal_version.proposal_version_id)
            lineage = query.get_decision_lineage_diagnostic(third.decision_id)
            backlog = query.get_governance_review_backlog(generated.proposal_version.proposal_version_id)

            assert proposal_detail.proposal_id == generated.proposal.proposal_id
            assert version_detail.proposal_version_id == generated.proposal_version.proposal_version_id
            assert latest is not None and latest.decision_id == third.decision_id
            assert traceability.proposal_version_id == generated.proposal_version.proposal_version_id
            assert confidence.authoritative_confidence == generated.proposal_version.confidence_breakdown.overall_confidence
            assert lineage.decision_state == "MODIFIED"
            assert any(row.reason_code == "MODIFIED_RECOMMENDATION" for row in backlog.items)
    finally:
        with pg_engine.begin() as conn:
            _cleanup_postgres_context(conn, data)


def test_wave2b_m5_postgres_transaction_rollback_on_capture_failure(pg_engine) -> None:
    data = build_input(scenario_catalog()["A_strong_positive"])

    with pg_engine.begin() as conn:
        _seed_postgres_context(conn, data)

    try:
        with Session(pg_engine) as session:
            engine = RecommendationDecisionEngine(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
            )
            generated = engine.generate_recommendation(data)

            capture = DecisionCaptureService(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                decision_repository=FailingDecisionRepository(session),
            )

            with pytest.raises(DecisionPersistenceError):
                capture.capture(
                    DecisionCaptureRequest(
                        proposal_version_id=generated.proposal_version.proposal_version_id,
                        decision_type=DecisionType.ACCEPT,
                        reviewer="rm_001",
                        reason_code="APPROVED",
                        client_request_id="req-fail",
                    )
                )

            persisted = SQLModelInvestmentDecisionRepository(session)
            assert persisted.list_for_proposal_version(generated.proposal_version.proposal_version_id) == []
    finally:
        with pg_engine.begin() as conn:
            _cleanup_postgres_context(conn, data)


def test_wave2b_m5_postgres_constraint_enforcement_still_blocks_invalid_rows(pg_engine) -> None:
    data = build_input(scenario_catalog()["A_strong_positive"])

    with pg_engine.begin() as conn:
        _seed_postgres_context(conn, data)

    try:
        with Session(pg_engine) as session:
            engine = RecommendationDecisionEngine(
                proposal_repository=SQLModelRecommendationProposalRepository(session),
                version_repository=SQLModelRecommendationProposalVersionRepository(session),
                snapshot_repository=SQLModelRecommendationSnapshotRepository(session),
                reason_repository=SQLModelRecommendationReasonRepository(session),
                trace_repository=SQLModelRecommendationTraceRepository(session),
            )
            generated = engine.generate_recommendation(data)

        with pg_engine.begin() as conn:
            with pytest.raises(IntegrityError):
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO decision_investment_decisions (
                            decision_id,
                            proposal_version_id,
                            state,
                            reason_code,
                            decided_at,
                            preferred_alternative_target_key,
                            modified_action,
                            modified_action_note,
                            modified_action_min_weight,
                            modified_action_max_weight,
                            modified_position_min_weight,
                            modified_position_max_weight
                        ) VALUES (
                            :decision_id,
                            :proposal_version_id,
                            'MODIFIED',
                            'ADJUST_SIZE',
                            :decided_at,
                            NULL,
                            NULL,
                            NULL,
                            NULL,
                            NULL,
                            NULL,
                            NULL
                        )
                        """
                    ),
                    {
                        "decision_id": "decision:invalid:m5",
                        "proposal_version_id": generated.proposal_version.proposal_version_id,
                        "decided_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
    finally:
        with pg_engine.begin() as conn:
            _cleanup_postgres_context(conn, data)
