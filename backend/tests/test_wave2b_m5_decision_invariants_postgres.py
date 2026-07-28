from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid

from alembic import command
from alembic.config import Config
import pytest
import sqlalchemy as sa
from sqlmodel import Session, create_engine

from piios.decision_contracts.domain.enums import Priority, ProposalStatus, RecommendationAction
from piios.decision_contracts.domain.proposal import RecommendationProposal, RecommendationProposalVersion
from piios.decision_contracts.domain.value_objects import (
    ActionProposal,
    ConfidenceBreakdown,
    RecommendationConfidenceDimensions,
    RecommendationPriority,
)
from piios.decision_contracts.infrastructure.sqlmodel_repositories import (
    SQLModelRecommendationProposalRepository,
    SQLModelRecommendationProposalVersionRepository,
)
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
    engine = create_engine(settings.db_url)
    return engine


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


def _seed_proposal_and_version(engine, suffix: str) -> str:
    proposal_id = f"p_w2b_m5_{suffix}"
    proposal_version_id = f"pv_w2b_m5_{suffix}"

    with Session(engine) as session:
        proposal_repo = SQLModelRecommendationProposalRepository(session)
        version_repo = SQLModelRecommendationProposalVersionRepository(session)

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
                proposal_version_id=proposal_version_id,
                proposal_id=proposal_id,
                version_number=1,
                status=ProposalStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                snapshot_id=f"snap_{proposal_version_id}",
                action_proposal=ActionProposal(action=RecommendationAction.BUY),
                confidence_breakdown=_confidence(),
                priority=RecommendationPriority(level=Priority.HIGH, score=0.8),
                required_human_review=True,
            )
        )

    return proposal_version_id


def test_wave2b_m5_postgres_rejects_invalid_modified_decision_payload(pg_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    proposal_version_id = _seed_proposal_and_version(pg_engine, suffix)

    with pg_engine.begin() as conn:
        with pytest.raises(sa.exc.IntegrityError):
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
                    "decision_id": f"d_bad_modified_{suffix}",
                    "proposal_version_id": proposal_version_id,
                    "decided_at": datetime.now(timezone.utc).isoformat(),
                },
            )


def test_wave2b_m5_postgres_rejects_invalid_overridden_decision_alternative(pg_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    proposal_version_id = _seed_proposal_and_version(pg_engine, suffix)

    with pg_engine.begin() as conn:
        with pytest.raises(sa.exc.IntegrityError):
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
                        'OVERRIDDEN',
                        'ALTERNATIVE_BETTER',
                        :decided_at,
                        '   ',
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
                    "decision_id": f"d_bad_override_{suffix}",
                    "proposal_version_id": proposal_version_id,
                    "decided_at": datetime.now(timezone.utc).isoformat(),
                },
            )


def test_wave2b_m5_postgres_rejects_non_modified_payload(pg_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    proposal_version_id = _seed_proposal_and_version(pg_engine, suffix)

    with pg_engine.begin() as conn:
        with pytest.raises(sa.exc.IntegrityError):
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
                        'ACCEPTED',
                        'CONFIRMED',
                        :decided_at,
                        NULL,
                        'HOLD',
                        'tampered',
                        NULL,
                        NULL,
                        NULL,
                        NULL
                    )
                    """
                ),
                {
                    "decision_id": f"d_bad_payload_{suffix}",
                    "proposal_version_id": proposal_version_id,
                    "decided_at": datetime.now(timezone.utc).isoformat(),
                },
            )
