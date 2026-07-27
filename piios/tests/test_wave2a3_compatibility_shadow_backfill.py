from __future__ import annotations

import pytest
from sqlmodel import SQLModel, Session, create_engine, select

from piios_backend.models.entities import (
    ClaimEvidenceInterpretationEntity,
    EvidenceItemEntity,
    EvidenceSourceEntity,
    InvestmentThesisEntity,
    ProvenanceRecordEntity,
    ResearchDocument,
    ThesisClaimEntity,
    ThesisVersionEntity,
)
from piios_backend.schemas.enums import Bucket, RecommendationStatus
from piios_backend.schemas.operations import ResearchDocumentResponse
from piios_backend.schemas.thesis import InvestmentThesis
from piios_backend.services.claims_evidence_backfill import run_claims_evidence_backfill
from piios_backend.services.claims_evidence_compatibility import (
    project_claims_evidence_overlap_for_thesis,
    project_evidence_to_legacy_research_documents,
)
from piios_backend.services.claims_evidence_shadow import run_claims_evidence_shadow_diagnostics


@pytest.fixture
def db_engine(tmp_path):
    db_path = tmp_path / "wave2a3_m3.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_m3_fixture(session: Session) -> None:
    thesis = InvestmentThesisEntity(
        thesis_id="t_m3",
        ticker="NVDA",
        asset_name="NVIDIA",
        theme="AI Infrastructure",
        bucket=Bucket.STRATEGIC_ALPHA.value,
        thesis="Core demand thesis",
        bull_case="Upside if demand compounds",
        bear_case="Downside if pricing compresses",
        why_now="Execution momentum",
        why_not_now="Rich valuation",
        invalidation_trigger="Sustained margin decline",
        valuation_notes="Premium multiple",
        expected_holding_period="2-5 years",
        source_documents='["rd901", "rdBAD"]',
        confidence_score=78,
        status=RecommendationStatus.RESEARCHED,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    version = ThesisVersionEntity(
        version_id="t_m3:v1",
        thesis_id="t_m3",
        version_number=1,
        asset_name="NVIDIA",
        theme="AI Infrastructure",
        bucket=Bucket.STRATEGIC_ALPHA.value,
        thesis="Core demand thesis",
        bull_case="Upside if demand compounds",
        bear_case="Downside if pricing compresses",
        why_now="Execution momentum",
        why_not_now="Rich valuation",
        invalidation_trigger="Sustained margin decline",
        valuation_notes="Premium multiple",
        expected_holding_period="2-5 years",
        source_documents='["rd901"]',
        confidence_score=78,
        status="ACTIVE",
        created_at="2026-01-01T00:00:00+00:00",
    )
    rd = ResearchDocument(
        id=901,
        title="NVDA demand note",
        source="Independent Research",
        timestamp="2026-01-10T00:00:00+00:00",
        url="https://example.com/rd901",
        content="Demand remains healthy",
        credibility_score=84,
        related_ticker_theme="NVDA",
        extracted_entities='["NVDA"]',
    )
    session.add(thesis)
    session.add(version)
    session.add(rd)
    session.commit()


def test_wave2a3_compatibility_projection_preserves_legacy_and_maps_overlap() -> None:
    thesis = InvestmentThesis(
        thesis_id="t_m3",
        ticker="NVDA",
        asset_name="NVIDIA",
        theme="AI Infrastructure",
        bucket=Bucket.STRATEGIC_ALPHA,
        thesis="Core demand thesis",
        bull_case="Bull",
        bear_case="Bear",
        why_now="Why now",
        why_not_now="Why not",
        invalidation_trigger="Invalidate",
        valuation_notes="Valuation",
        expected_holding_period="2-5 years",
        source_documents=["rd901"],
        confidence_score=80,
        status=RecommendationStatus.RESEARCHED,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    claims = [
        {
            "claim_id": "cl1",
            "claim_key": "core_thesis",
            "claim_text": "Core demand thesis",
            "status": "ACTIVE",
        }
    ]
    interpretations = [
        {
            "interpretation_id": "i1",
            "claim_id": "cl1",
            "evidence_id": "ev1",
            "relation": "SUPPORTS",
            "effective_to": None,
        }
    ]
    evidence_items = [
        {
            "evidence_id": "ev1",
            "source_id": "src1",
            "title": "NVDA demand note",
            "as_of_date": "2026-01-10T00:00:00+00:00",
        }
    ]
    evidence_sources = [
        {
            "source_id": "src1",
            "publisher": "Independent Research",
            "source_system": "legacy_research_document",
            "url": "https://example.com/rd901",
        }
    ]

    payload = project_claims_evidence_overlap_for_thesis(
        thesis=thesis,
        claims=claims,
        interpretations=interpretations,
        evidence_items=evidence_items,
        evidence_sources=evidence_sources,
    )

    assert payload["thesis_id"] == "t_m3"
    assert payload["legacy_rationale"] == "Core demand thesis"
    assert payload["legacy_source_documents"] == ["rd901"]
    assert payload["claims_overlap"][0]["supports_evidence_ids"] == ["ev1"]
    assert payload["evidence_overlap"][0]["title"] == "NVDA demand note"


def test_wave2a3_compatibility_evidence_projection_shape() -> None:
    docs = project_evidence_to_legacy_research_documents(
        evidence_items=[
            {
                "evidence_id": "ev1",
                "source_id": "src1",
                "title": "NVDA demand note",
                "created_at": "2026-01-11T00:00:00+00:00",
            }
        ],
        evidence_sources=[
            {
                "source_id": "src1",
                "publisher": "Independent Research",
                "url": "https://example.com/rd901",
                "published_at": "2026-01-10T00:00:00+00:00",
            }
        ],
    )
    assert len(docs) == 1
    assert isinstance(docs[0], ResearchDocumentResponse)
    assert docs[0].title == "NVDA demand note"
    assert docs[0].source == "Independent Research"


def test_wave2a3_backfill_dry_run_and_apply_idempotency_and_conflict_preservation(db_engine) -> None:
    with Session(db_engine) as session:
        _seed_m3_fixture(session)

    with Session(db_engine) as session:
        dry = run_claims_evidence_backfill(session, dry_run=True)
    assert dry.dry_run is True
    assert dry.created_claims >= 1
    assert dry.created_interpretations >= 1
    assert any(item.reason_code == "INCOMPLETE_PROVENANCE" for item in dry.owner_review_items)

    with Session(db_engine) as session:
        apply1 = run_claims_evidence_backfill(session, dry_run=False)
    assert apply1.dry_run is False
    assert apply1.created_claims >= 1
    assert apply1.created_interpretations >= 1

    with Session(db_engine) as session:
        apply2 = run_claims_evidence_backfill(session, dry_run=False)
    assert apply2.created_claims == 0
    assert apply2.created_sources == 0
    assert apply2.created_evidence_items == 0
    assert apply2.created_interpretations == 0

    with Session(db_engine) as session:
        claims = list(session.exec(select(ThesisClaimEntity).where(ThesisClaimEntity.thesis_id == "t_m3")).all())
        assert len(claims) >= 1
        for claim in claims:
            assert claim.thesis_version_id == "t_m3:v1"

        interpretations = list(
            session.exec(
                select(ClaimEvidenceInterpretationEntity).where(
                    ClaimEvidenceInterpretationEntity.claim_id.like("cl:t_m3:v1:%")
                )
            ).all()
        )
        assert all(row.relation == "SUPPORTS" for row in interpretations)

        provenance = list(session.exec(select(ProvenanceRecordEntity)).all())
        assert len(provenance) >= 1


def test_wave2a3_shadow_diagnostics_flags_gaps_conflicts_and_bindings(db_engine) -> None:
    with Session(db_engine) as session:
        _seed_m3_fixture(session)
        # Seed a conflict and a broken thesis/version binding for diagnostics.
        session.add(
            ThesisClaimEntity(
                claim_id="cl_conflict",
                thesis_version_id="t_m3:v1",
                thesis_id="t_m3",
                claim_key="conflict",
                claim_text="Conflicted claim",
                claim_type="manual",
                status="ACTIVE",
                active_from="2026-01-01T00:00:00+00:00",
                active_to=None,
                created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-01T00:00:00+00:00",
            )
        )
        session.add(
            ThesisClaimEntity(
                claim_id="cl_bad_bind",
                thesis_version_id="does_not_exist:v1",
                thesis_id="t_m3",
                claim_key="bad_bind",
                claim_text="Broken binding",
                claim_type="manual",
                status="ACTIVE",
                active_from="2026-01-01T00:00:00+00:00",
                active_to=None,
                created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-01T00:00:00+00:00",
            )
        )
        session.add(
            EvidenceSourceEntity(
                source_id="src_conflict",
                source_type="RESEARCH",
                publisher="Conflict Source",
                url="https://example.com/conflict",
                source_system="manual",
                published_at="2026-01-05T00:00:00+00:00",
                retrieved_at="2026-01-06T00:00:00+00:00",
                credibility_tier="B",
                created_at="2026-01-06T00:00:00+00:00",
            )
        )
        session.add(
            EvidenceItemEntity(
                evidence_id="ev_conflict",
                source_id="src_conflict",
                title="Conflict evidence",
                excerpt="",
                content_hash="h1",
                as_of_date="2026-01-05T00:00:00+00:00",
                metadata_json="{}",
                created_at="2026-01-06T00:00:00+00:00",
            )
        )
        session.add(
            ClaimEvidenceInterpretationEntity(
                interpretation_id="i_conflict_supports",
                claim_id="cl_conflict",
                evidence_id="ev_conflict",
                relation="SUPPORTS",
                strength="medium",
                note="",
                effective_from="2026-01-06T00:00:00+00:00",
                effective_to=None,
                supersedes_interpretation_id=None,
                superseded_by_interpretation_id=None,
                created_at="2026-01-06T00:00:00+00:00",
            )
        )
        session.add(
            ClaimEvidenceInterpretationEntity(
                interpretation_id="i_conflict_contradicts",
                claim_id="cl_conflict",
                evidence_id="ev_conflict",
                relation="CONTRADICTS",
                strength="medium",
                note="",
                effective_from="2026-01-06T00:00:00+00:00",
                effective_to=None,
                supersedes_interpretation_id=None,
                superseded_by_interpretation_id=None,
                created_at="2026-01-06T00:00:00+00:00",
            )
        )
        session.add(
            ProvenanceRecordEntity(
                provenance_id="prov_incomplete",
                entity_type="THESIS_CLAIM",
                entity_id="cl_conflict",
                action="MANUAL_EDIT",
                actor_type="SYSTEM",
                actor_reference="",
                ingestion_method="",
                source_system="",
                extraction_method="",
                model_name=None,
                model_version=None,
                payload_hash=None,
                created_at="2026-01-06T00:00:00+00:00",
            )
        )
        session.commit()

    with Session(db_engine) as session:
        report = run_claims_evidence_shadow_diagnostics(session)

    assert report["enabled"] is True
    assert any(item["claim_id"] == "cl_conflict" for item in report["conflicting_evidence"])
    assert any(item["claim_id"] == "cl_bad_bind" for item in report["thesis_version_binding_failures"])
    assert any(item["provenance_id"] == "prov_incomplete" for item in report["incomplete_provenance"])
