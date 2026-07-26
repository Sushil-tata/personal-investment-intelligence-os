import pytest

from piios.thesis.application.claim_commands import (
    AddClaimEvidenceInterpretationCommand,
    CreateClaimCommand,
)
from piios.thesis.application.claim_queries import ListClaimInterpretationsQuery, ListClaimsForVersionQuery
from piios.thesis.application.claim_services import ThesisClaimApplicationService
from piios.thesis.application.commands import CreateThesisCommand
from piios.thesis.application.evidence_commands import CreateEvidenceItemCommand, CreateEvidenceSourceCommand
from piios.thesis.application.services import ThesisApplicationService
from piios.thesis.domain.claims import InterpretationRelation
from piios.thesis.domain.evidence import EvidenceItem, EvidenceSource, EvidenceSourceType
from piios.thesis.domain.exceptions import ClaimInterpretationConflictError, ClaimVersionBindingError
from piios.thesis.infrastructure.in_memory_claim_evidence_repositories import (
    InMemoryClaimEvidenceInterpretationRepository,
    InMemoryEvidenceItemRepository,
    InMemoryEvidenceSourceRepository,
    InMemoryProvenanceRepository,
    InMemoryThesisClaimRepository,
)
from piios.thesis.infrastructure.in_memory_repositories import InMemoryThesisRootRepository, InMemoryThesisVersionRepository


def _build_services() -> tuple[ThesisApplicationService, ThesisClaimApplicationService, InMemoryEvidenceItemRepository]:
    root_repo = InMemoryThesisRootRepository()
    version_repo = InMemoryThesisVersionRepository()
    thesis_service = ThesisApplicationService(root_repo, version_repo)

    evidence_items = InMemoryEvidenceItemRepository()
    claim_service = ThesisClaimApplicationService(
        claim_repo=InMemoryThesisClaimRepository(),
        interpretation_repo=InMemoryClaimEvidenceInterpretationRepository(),
        evidence_item_repo=evidence_items,
        thesis_version_repo=version_repo,
        provenance_repo=InMemoryProvenanceRepository(),
    )
    return thesis_service, claim_service, evidence_items


def test_claim_binds_to_specific_thesis_version() -> None:
    thesis_service, claim_service, _ = _build_services()
    thesis = thesis_service.create_thesis(
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

    created = claim_service.create_claim(
        CreateClaimCommand(
            claim_id="cl_1",
            thesis_version_id=f"{thesis.thesis_id}:v1",
            thesis_id=thesis.thesis_id,
            claim_key="margin_durability",
            claim_text="Margins remain resilient",
            claim_type="fundamental",
        )
    )

    rows = claim_service.list_claims_for_version(ListClaimsForVersionQuery(thesis_version_id=f"{thesis.thesis_id}:v1"))
    assert created.claim_id == "cl_1"
    assert len(rows) == 1


def test_claim_rejects_mismatched_thesis_id_and_version() -> None:
    thesis_service, claim_service, _ = _build_services()
    first = thesis_service.create_thesis(
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
    second = thesis_service.create_thesis(
        CreateThesisCommand(
            ticker="AAPL",
            asset_name="Apple",
            theme="Consumer Platform",
            bucket="Strategic Alpha",
            thesis="Base thesis",
            bull_case="Bull",
            bear_case="Bear",
            why_now="Now",
            why_not_now="Not now",
            invalidation_trigger="Trigger",
            valuation_notes="Notes",
            expected_holding_period="3-5 years",
            source_documents=["rd2"],
            confidence_score=68,
        )
    )

    with pytest.raises(ClaimVersionBindingError):
        claim_service.create_claim(
            CreateClaimCommand(
                claim_id="cl_x",
                thesis_version_id=f"{first.thesis_id}:v1",
                thesis_id=second.thesis_id,
                claim_key="bad_link",
                claim_text="Incorrect ownership link",
                claim_type="risk",
            )
        )


def test_interpretation_requires_explicit_supersession() -> None:
    thesis_service, claim_service, evidence_items = _build_services()
    thesis = thesis_service.create_thesis(
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
    claim_service.create_claim(
        CreateClaimCommand(
            claim_id="cl_1",
            thesis_version_id=f"{thesis.thesis_id}:v1",
            thesis_id=thesis.thesis_id,
            claim_key="margin_durability",
            claim_text="Margins remain resilient",
            claim_type="fundamental",
        )
    )

    evidence_items.create(
        EvidenceItem(
            evidence_id="ev_1",
            source_id="src_1",
            title="Quarterly report",
            excerpt="Margins stable",
            content_hash=None,
            as_of_date="2026-07-26",
            metadata_json="{}",
            created_at=thesis_service.list_versions(thesis.thesis_id)[0].created_at,
        )
    )

    first = claim_service.add_interpretation(
        AddClaimEvidenceInterpretationCommand(
            interpretation_id="int_1",
            claim_id="cl_1",
            evidence_id="ev_1",
            relation=InterpretationRelation.SUPPORTS,
            strength="medium",
        )
    )
    assert first.supersedes_interpretation_id is None

    with pytest.raises(ClaimInterpretationConflictError):
        claim_service.add_interpretation(
            AddClaimEvidenceInterpretationCommand(
                interpretation_id="int_2",
                claim_id="cl_1",
                evidence_id="ev_1",
                relation=InterpretationRelation.CONTRADICTS,
                strength="high",
            )
        )

    second = claim_service.add_interpretation(
        AddClaimEvidenceInterpretationCommand(
            interpretation_id="int_3",
            claim_id="cl_1",
            evidence_id="ev_1",
            relation=InterpretationRelation.CONTRADICTS,
            strength="high",
            supersedes_interpretation_id="int_1",
        )
    )
    rows = claim_service.list_interpretations(ListClaimInterpretationsQuery(claim_id="cl_1"))
    assert second.supersedes_interpretation_id == "int_1"
    assert len(rows) == 2
    assert rows[0].superseded_by_interpretation_id == "int_3"
