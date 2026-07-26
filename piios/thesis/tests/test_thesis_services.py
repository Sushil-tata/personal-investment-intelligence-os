from piios.thesis.application.commands import CreateThesisCommand, CreateThesisVersionCommand, UpdateThesisStatusCommand
from piios.thesis.application.queries import GetThesisQuery
from piios.thesis.domain.enums import ThesisStatus
from piios.thesis.infrastructure.in_memory_repositories import InMemoryThesisRootRepository, InMemoryThesisVersionRepository
from piios.thesis.application.services import ThesisApplicationService


def _service() -> ThesisApplicationService:
    return ThesisApplicationService(InMemoryThesisRootRepository(), InMemoryThesisVersionRepository())


def _create_payload() -> CreateThesisCommand:
    return CreateThesisCommand(
        ticker="MSFT",
        asset_name="Microsoft",
        theme="Enterprise AI",
        bucket="Strategic Alpha",
        thesis="Durable enterprise software moat with AI monetization upside.",
        bull_case="Cloud leadership supports sustained earnings growth.",
        bear_case="Competition can compress cloud economics.",
        why_now="AI cycle supports spending intensity.",
        why_not_now="Valuation can re-rate lower during macro shocks.",
        invalidation_trigger="Two quarters of large Azure growth deceleration.",
        valuation_notes="Premium multiple supported by cash flow quality.",
        expected_holding_period="3-5 years",
        source_documents=["rd_msft_1"],
        confidence_score=73,
    )


def test_create_thesis_sets_version_one() -> None:
    service = _service()
    created = service.create_thesis(_create_payload())

    assert created.thesis_id == "t1"
    assert created.current_version_number == 1
    assert created.status == ThesisStatus.DRAFT


def test_status_update_creates_new_version_without_mutating_previous() -> None:
    service = _service()
    created = service.create_thesis(_create_payload())

    updated = service.update_status(UpdateThesisStatusCommand(thesis_id=created.thesis_id, status=ThesisStatus.RESEARCHED))
    versions = service.list_versions(created.thesis_id)

    assert updated.status == ThesisStatus.RESEARCHED
    assert updated.current_version_number == 2
    assert [item.version_number for item in versions] == [1, 2]
    assert versions[0].status == ThesisStatus.DRAFT
    assert versions[1].status == ThesisStatus.RESEARCHED


def test_material_update_creates_new_version() -> None:
    service = _service()
    created = service.create_thesis(_create_payload())

    updated = service.create_new_version(
        CreateThesisVersionCommand(
            thesis_id=created.thesis_id,
            asset_name="Microsoft Corp",
            theme="Enterprise AI",
            bucket="Strategic Alpha",
            thesis="Updated thesis text",
            bull_case="Updated bull case",
            bear_case="Updated bear case",
            why_now="Updated why now",
            why_not_now="Updated why not now",
            invalidation_trigger="Updated trigger",
            valuation_notes="Updated valuation",
            expected_holding_period="3-5 years",
            source_documents=["rd_msft_1", "rd_msft_2"],
            confidence_score=75,
        )
    )

    fetched = service.get_thesis(GetThesisQuery(thesis_id=created.thesis_id))

    assert updated.current_version_number == 2
    assert fetched.asset_name == "Microsoft Corp"
    assert fetched.thesis == "Updated thesis text"
