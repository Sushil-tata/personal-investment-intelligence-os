from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
import sqlalchemy as sa
from sqlmodel import Session, create_engine

from piios.decision_contracts.domain.decision import InvestmentDecision
from piios.decision_contracts.domain.enums import (
    DecisionState,
    Priority,
    ProposalStatus,
    ReasonType,
    RecommendationAction,
)
from piios.decision_contracts.domain.proposal import (
    RecommendationClaimLink,
    RecommendationEvidenceLink,
    RecommendationInputSnapshot,
    RecommendationProposal,
    RecommendationProposalVersion,
    RecommendationReason,
)
from piios.decision_contracts.domain.value_objects import (
    ActionProposal,
    ConfidenceBreakdown,
    RecommendationConfidenceDimensions,
    RecommendationPriority,
    ReasonWeight,
)
from piios.decision_contracts.infrastructure.sqlmodel_repositories import (
    SQLModelInvestmentDecisionRepository,
    SQLModelRecommendationProposalRepository,
    SQLModelRecommendationProposalVersionRepository,
    SQLModelRecommendationReasonRepository,
    SQLModelRecommendationSnapshotRepository,
    SQLModelRecommendationTraceRepository,
)
from piios.thesis_health.domain.entities import ThesisHealthSnapshot
from piios.thesis_health.infrastructure.sqlmodel_repositories import SQLModelThesisHealthRepository
from piios_backend.core.config import settings


def _seed_claim_evidence_context(conn: sa.Connection, suffix: str) -> tuple[str, str, str]:
    thesis_id = f"t_w2b_m2_{suffix}"
    version_id = f"{thesis_id}:v1"
    claim_id = f"cl_w2b_m2_{suffix}"
    source_id = f"src_w2b_m2_{suffix}"
    evidence_id = f"ev_w2b_m2_{suffix}"
    interpretation_id = f"int_w2b_m2_{suffix}"

    conn.execute(
        sa.text(
            """
            INSERT INTO thesis_roots (
                thesis_id, ticker, lifecycle_status, current_version_number,
                created_at, updated_at, closed_reason, closed_at
            ) VALUES (
                :thesis_id, 'NVDA', 'RESEARCHED', 1,
                '2026-07-27T00:00:00+00:00', '2026-07-27T00:00:00+00:00', NULL, NULL
            )
            """
        ),
        {"thesis_id": thesis_id},
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
                'NVIDIA', 'AI', 'Strategic Alpha', 'Base',
                'Bull', 'Bear', 'Now', 'Not now',
                'Trigger', 'Notes', '2-5 years',
                '["rd"]', 75.0, 'RESEARCHED', '2026-07-27T00:00:00+00:00'
            )
            """
        ),
        {"version_id": version_id, "thesis_id": thesis_id},
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO thesis_claims (
                claim_id, thesis_version_id, thesis_id, claim_key, claim_text,
                claim_type, status, active_from, active_to, created_at, updated_at
            ) VALUES (
                :claim_id, :version_id, :thesis_id, 'core', 'Claim text',
                'fundamental', 'ACTIVE', '2026-07-27T00:00:00+00:00', NULL,
                '2026-07-27T00:00:00+00:00', '2026-07-27T00:00:00+00:00'
            )
            """
        ),
        {"claim_id": claim_id, "version_id": version_id, "thesis_id": thesis_id},
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO evidence_sources (
                source_id, source_type, publisher, url, source_system,
                published_at, retrieved_at, credibility_tier, created_at
            ) VALUES (
                :source_id, 'RESEARCH', 'Desk', 'https://example.com', 'test',
                '2026-07-27T00:00:00+00:00', '2026-07-27T00:00:00+00:00', 'A',
                '2026-07-27T00:00:00+00:00'
            )
            """
        ),
        {"source_id": source_id},
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO evidence_items (
                evidence_id, source_id, title, excerpt, content_hash, as_of_date, metadata_json, created_at
            ) VALUES (
                :evidence_id, :source_id, 'Evidence', 'Excerpt', 'hash', '2026-07-27', '{"quality":"high"}',
                '2026-07-27T00:00:00+00:00'
            )
            """
        ),
        {"evidence_id": evidence_id, "source_id": source_id},
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO claim_evidence_interpretations (
                interpretation_id, claim_id, evidence_id, relation, strength, note,
                effective_from, effective_to, supersedes_interpretation_id,
                superseded_by_interpretation_id, created_at
            ) VALUES (
                :interpretation_id, :claim_id, :evidence_id, 'SUPPORTS', 'medium', NULL,
                '2026-07-27T00:00:00+00:00', NULL, NULL, NULL, '2026-07-27T00:00:00+00:00'
            )
            """
        ),
        {"interpretation_id": interpretation_id, "claim_id": claim_id, "evidence_id": evidence_id},
    )

    return version_id, claim_id, evidence_id


def _confidence() -> ConfidenceBreakdown:
    return ConfidenceBreakdown(
        dimensions=RecommendationConfidenceDimensions(
            company_quality=0.8,
            valuation_attractiveness=0.7,
            portfolio_suitability=0.6,
            recommendation_confidence=0.65,
            relationship_confidence=0.55,
            expected_return=0.5,
        ),
        overall_confidence=0.64,
    )


def test_wave2b_m2_postgres_persistence_and_ordering() -> None:
    engine = create_engine(settings.db_url)
    suffix = uuid.uuid4().hex[:8]

    with engine.begin() as conn:
        thesis_version_id, claim_id, evidence_id = _seed_claim_evidence_context(conn, suffix)

    with Session(engine) as session:
        proposal_repo = SQLModelRecommendationProposalRepository(session)
        version_repo = SQLModelRecommendationProposalVersionRepository(session)
        snapshot_repo = SQLModelRecommendationSnapshotRepository(session)
        reason_repo = SQLModelRecommendationReasonRepository(session)
        trace_repo = SQLModelRecommendationTraceRepository(session)
        decision_repo = SQLModelInvestmentDecisionRepository(session)
        health_repo = SQLModelThesisHealthRepository(session)

        proposal_id = f"p_w2b_m2_{suffix}"
        pv1 = f"pv_w2b_m2_1_{suffix}"
        pv2 = f"pv_w2b_m2_2_{suffix}"

        proposal_repo.create(
            RecommendationProposal(
                proposal_id=proposal_id,
                target_type="SECURITY",
                target_key="NVDA",
                scope="PORTFOLIO",
                status=ProposalStatus.DRAFT,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )

        version_repo.create(
            RecommendationProposalVersion(
                proposal_version_id=pv1,
                proposal_id=proposal_id,
                version_number=1,
                status=ProposalStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                snapshot_id=f"snap_{pv1}",
                action_proposal=ActionProposal(action=RecommendationAction.BUY),
                confidence_breakdown=_confidence(),
                priority=RecommendationPriority(level=Priority.HIGH, score=0.8),
                required_human_review=True,
            )
        )
        version_repo.create(
            RecommendationProposalVersion(
                proposal_version_id=pv2,
                proposal_id=proposal_id,
                version_number=2,
                status=ProposalStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                snapshot_id=f"snap_{pv2}",
                action_proposal=ActionProposal(action=RecommendationAction.HOLD),
                confidence_breakdown=_confidence(),
                priority=RecommendationPriority(level=Priority.MEDIUM, score=0.6),
                required_human_review=False,
                supersedes_version_id=pv1,
            )
        )

        rows = version_repo.list_for_proposal(proposal_id)
        assert [row.version_number for row in rows] == [1, 2]
        assert version_repo.get_latest(proposal_id).proposal_version_id == pv2

        snapshot_repo.create(
            RecommendationInputSnapshot(
                snapshot_id=f"snap_input_{suffix}",
                proposal_version_id=pv1,
                captured_at=datetime.now(timezone.utc),
                canonical_payload_json='{"ticker":"NVDA"}',
                input_hash=f"hash_{suffix}",
            )
        )
        assert snapshot_repo.get_for_proposal_version(pv1) is not None

        reason_repo.create_many(
            (
                RecommendationReason(
                    reason_id=f"r2_{suffix}",
                    proposal_version_id=pv1,
                    rank=2,
                    reason_type=ReasonType.RISK_CONTROL,
                    weight=ReasonWeight(0.4),
                    reason_code="risk",
                    detail_json="{}",
                ),
                RecommendationReason(
                    reason_id=f"r1_{suffix}",
                    proposal_version_id=pv1,
                    rank=1,
                    reason_type=ReasonType.THESIS_SUPPORT,
                    weight=ReasonWeight(0.8),
                    reason_code="support",
                    detail_json="{}",
                ),
            )
        )
        assert [row.rank for row in reason_repo.list_for_proposal_version(pv1)] == [1, 2]

        trace_repo.create_claim_links(
            (
                RecommendationClaimLink(
                    claim_link_id=f"clink_{suffix}",
                    proposal_version_id=pv1,
                    claim_id=claim_id,
                    contribution_weight=ReasonWeight(0.6),
                    role="supporting",
                ),
            )
        )
        trace_repo.create_evidence_links(
            (
                RecommendationEvidenceLink(
                    evidence_link_id=f"elink_{suffix}",
                    proposal_version_id=pv1,
                    evidence_id=evidence_id,
                    interpretation_id=f"int_w2b_m2_{suffix}",
                    freshness_days=10,
                    quality_score=0.9,
                    conflict_flag=False,
                ),
            )
        )
        assert len(trace_repo.list_claim_links(pv1)) == 1
        assert len(trace_repo.list_evidence_links(pv1)) == 1

        decision_repo.create(
            InvestmentDecision(
                decision_id=f"d1_{suffix}",
                proposal_version_id=pv1,
                state=DecisionState.DEFERRED,
                reason_code="need_more_data",
                decided_at=datetime(2026, 7, 27, 10, 0, 0, tzinfo=timezone.utc),
            )
        )
        decision_repo.create(
            InvestmentDecision(
                decision_id=f"d2_{suffix}",
                proposal_version_id=pv1,
                state=DecisionState.ACCEPTED,
                reason_code="approved",
                decided_at=datetime(2026, 7, 27, 10, 1, 0, tzinfo=timezone.utc),
            )
        )
        assert decision_repo.get_latest_for_proposal_version(pv1).decision_id == f"d2_{suffix}"

        health_repo.create(
            ThesisHealthSnapshot(
                thesis_version_id=thesis_version_id,
                computation_version="wave2b-th-v1",
                computed_at=datetime.now(timezone.utc),
                evidence_freshness=0.8,
                evidence_quality=0.9,
                supporting_strength=0.7,
                contradictory_strength=0.2,
                provenance_completeness=1.0,
                thesis_health_index=0.84,
            )
        )
        assert health_repo.get_latest(thesis_version_id) is not None


def test_wave2b_m2_postgres_duplicate_rejection_and_rollback() -> None:
    engine = create_engine(settings.db_url)
    suffix = uuid.uuid4().hex[:8]

    with Session(engine) as session:
        proposal_repo = SQLModelRecommendationProposalRepository(session)
        proposal = RecommendationProposal(
            proposal_id=f"p_dup_{suffix}",
            target_type="SECURITY",
            target_key="AVGO",
            scope="PORTFOLIO",
            status=ProposalStatus.DRAFT,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        proposal_repo.create(proposal)
        with pytest.raises(ValueError):
            proposal_repo.create(proposal)

        # Transactional consistency after rollback from duplicate insert.
        proposal_repo.create(
            RecommendationProposal(
                proposal_id=f"p_dup_ok_{suffix}",
                target_type="SECURITY",
                target_key="TSMC",
                scope="PORTFOLIO",
                status=ProposalStatus.DRAFT,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        assert proposal_repo.get(f"p_dup_ok_{suffix}") is not None


def test_wave2b_m2_postgres_concurrent_write_conflict() -> None:
    engine = create_engine(settings.db_url)
    suffix = uuid.uuid4().hex[:8]
    proposal_id = f"p_conc_{suffix}"

    with Session(engine) as s1:
        repo1 = SQLModelRecommendationProposalRepository(s1)
        repo1.create(
            RecommendationProposal(
                proposal_id=proposal_id,
                target_type="SECURITY",
                target_key="MSFT",
                scope="PORTFOLIO",
                status=ProposalStatus.DRAFT,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )

    with Session(engine) as s2:
        repo2 = SQLModelRecommendationProposalRepository(s2)
        with pytest.raises(ValueError):
            repo2.create(
                RecommendationProposal(
                    proposal_id=proposal_id,
                    target_type="SECURITY",
                    target_key="MSFT",
                    scope="PORTFOLIO",
                    status=ProposalStatus.DRAFT,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
