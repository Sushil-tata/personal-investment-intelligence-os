from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine

from piios.thesis.application.commands import CreateThesisCommand
from piios.thesis.application.services import ThesisApplicationService
from piios.thesis.domain.claims import ClaimEvidenceInterpretation, ClaimStatus, InterpretationRelation, ThesisClaim
from piios.thesis.domain.evidence import EvidenceItem, EvidenceSource, EvidenceSourceType
from piios.thesis.domain.provenance import ProvenanceRecord
from piios.thesis.infrastructure.sqlmodel_claim_evidence_repositories import (
    SQLModelClaimEvidenceInterpretationRepository,
    SQLModelEvidenceItemRepository,
    SQLModelEvidenceSourceRepository,
    SQLModelProvenanceRepository,
    SQLModelThesisClaimRepository,
)
from piios.thesis.infrastructure.sqlmodel_repositories import SQLModelThesisRootRepository, SQLModelThesisVersionRepository
from piios_backend.models import entities  # noqa: F401


def _seed_thesis_version(session: Session) -> str:
    service = ThesisApplicationService(
        root_repository=SQLModelThesisRootRepository(session),
        version_repository=SQLModelThesisVersionRepository(session),
    )
    created = service.create_thesis(
        CreateThesisCommand(
            ticker="MSFT",
            asset_name="Microsoft",
            theme="Enterprise AI",
            bucket="Strategic Alpha",
            thesis="Base thesis",
            bull_case="Bull",
            bear_case="Bear",
            why_now="Now",
            why_not_now="Not now",
            invalidation_trigger="Trigger",
            valuation_notes="Notes",
            expected_holding_period="3-5 years",
            source_documents=["rd1"],
            confidence_score=70,
        )
    )
    return f"{created.thesis_id}:v1"


def test_sqlmodel_claim_and_evidence_repositories() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        version_id = _seed_thesis_version(session)

        claim_repo = SQLModelThesisClaimRepository(session)
        source_repo = SQLModelEvidenceSourceRepository(session)
        item_repo = SQLModelEvidenceItemRepository(session)
        interp_repo = SQLModelClaimEvidenceInterpretationRepository(session)
        provenance_repo = SQLModelProvenanceRepository(session)

        now = datetime.now(timezone.utc)

        claim = ThesisClaim(
            claim_id="cl_1",
            thesis_version_id=version_id,
            thesis_id="t1",
            claim_key="margin_durability",
            claim_text="Margins remain resilient",
            claim_type="fundamental",
            status=ClaimStatus.DRAFT,
            active_from=now,
            active_to=None,
            created_at=now,
            updated_at=now,
        )
        claim_repo.create(claim)

        source_repo.create(
            EvidenceSource(
                source_id="src_1",
                source_type=EvidenceSourceType.RESEARCH,
                publisher="Research Desk",
                url=None,
                source_system="internal",
                published_at=None,
                retrieved_at=now,
                credibility_tier="A",
                created_at=now,
            )
        )

        item_repo.create(
            EvidenceItem(
                evidence_id="ev_1",
                source_id="src_1",
                title="Report",
                excerpt="Key excerpt",
                content_hash="hash-1",
                as_of_date="2026-07-27",
                metadata_json='{"k":"v"}',
                created_at=now,
            )
        )

        interp = ClaimEvidenceInterpretation(
            interpretation_id="int_1",
            claim_id="cl_1",
            evidence_id="ev_1",
            relation=InterpretationRelation.SUPPORTS,
            strength="medium",
            note=None,
            effective_from=now,
            effective_to=None,
            supersedes_interpretation_id=None,
            superseded_by_interpretation_id=None,
            created_at=now,
        )
        interp_repo.create(interp)

        provenance_repo.create(
            ProvenanceRecord(
                provenance_id="prov_1",
                entity_type="THESIS_CLAIM",
                entity_id="cl_1",
                action="CREATE",
                actor_type="SYSTEM",
                actor_reference="test",
                ingestion_method="manual",
                source_system="piios",
                extraction_method="none",
                model_name=None,
                model_version=None,
                payload_hash=None,
                created_at=now,
            )
        )

        claims = claim_repo.list_for_version(version_id)
        assert len(claims) == 1
        assert claims[0].claim_id == "cl_1"

        items = interp_repo.list_for_claim("cl_1")
        assert len(items) == 1
        assert items[0].relation == InterpretationRelation.SUPPORTS

        provenance = provenance_repo.list_for_entity("THESIS_CLAIM", "cl_1")
        assert len(provenance) == 1


def test_interpretation_repository_enforces_append_only_fields() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        version_id = _seed_thesis_version(session)
        now = datetime.now(timezone.utc)

        claim_repo = SQLModelThesisClaimRepository(session)
        source_repo = SQLModelEvidenceSourceRepository(session)
        item_repo = SQLModelEvidenceItemRepository(session)
        interp_repo = SQLModelClaimEvidenceInterpretationRepository(session)

        claim_repo.create(
            ThesisClaim(
                claim_id="cl_2",
                thesis_version_id=version_id,
                thesis_id="t1",
                claim_key="capex_discipline",
                claim_text="Capex remains disciplined",
                claim_type="fundamental",
                status=ClaimStatus.ACTIVE,
                active_from=now,
                active_to=None,
                created_at=now,
                updated_at=now,
            )
        )

        source_repo.create(
            EvidenceSource(
                source_id="src_2",
                source_type=EvidenceSourceType.FILING,
                publisher="Company",
                url=None,
                source_system="filings",
                published_at=None,
                retrieved_at=now,
                credibility_tier="A",
                created_at=now,
            )
        )
        item_repo.create(
            EvidenceItem(
                evidence_id="ev_2",
                source_id="src_2",
                title="Filing",
                excerpt="Excerpt",
                content_hash="hash-2",
                as_of_date="2026-07-27",
                metadata_json="{}",
                created_at=now,
            )
        )

        interp_repo.create(
            ClaimEvidenceInterpretation(
                interpretation_id="int_2",
                claim_id="cl_2",
                evidence_id="ev_2",
                relation=InterpretationRelation.SUPPORTS,
                strength="medium",
                note="initial",
                effective_from=now,
                effective_to=None,
                supersedes_interpretation_id=None,
                superseded_by_interpretation_id=None,
                created_at=now,
            )
        )

        with pytest.raises(ValueError):
            interp_repo.update(
                ClaimEvidenceInterpretation(
                    interpretation_id="int_2",
                    claim_id="cl_2",
                    evidence_id="ev_2",
                    relation=InterpretationRelation.CONTRADICTS,
                    strength="high",
                    note="changed",
                    effective_from=now,
                    effective_to=None,
                    supersedes_interpretation_id=None,
                    superseded_by_interpretation_id=None,
                    created_at=now,
                )
            )

        closed = ClaimEvidenceInterpretation(
            interpretation_id="int_2",
            claim_id="cl_2",
            evidence_id="ev_2",
            relation=InterpretationRelation.SUPPORTS,
            strength="medium",
            note="initial",
            effective_from=now,
            effective_to=now,
            supersedes_interpretation_id=None,
            superseded_by_interpretation_id="int_3",
            created_at=now,
        )
        updated = interp_repo.update(closed)
        assert updated.superseded_by_interpretation_id == "int_3"
