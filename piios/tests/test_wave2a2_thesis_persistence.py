from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

from piios.thesis.application.commands import CreateThesisCommand, UpdateThesisStatusCommand
from piios.thesis.application.services import ThesisApplicationService
from piios.thesis.domain.enums import ThesisStatus
from piios.thesis.infrastructure.sqlmodel_repositories import SQLModelThesisRootRepository, SQLModelThesisVersionRepository
from piios_backend.models import entities  # noqa: F401


def _service(session: Session) -> ThesisApplicationService:
    return ThesisApplicationService(
        root_repository=SQLModelThesisRootRepository(session),
        version_repository=SQLModelThesisVersionRepository(session),
    )


def test_sqlmodel_thesis_create_and_status_versioning() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        service = _service(session)
        created = service.create_thesis(
            CreateThesisCommand(
                ticker="MSFT",
                asset_name="Microsoft",
                theme="Enterprise AI",
                bucket="Strategic Alpha",
                thesis="Durable thesis",
                bull_case="Bull",
                bear_case="Bear",
                why_now="Now",
                why_not_now="Not now",
                invalidation_trigger="Trigger",
                valuation_notes="Notes",
                expected_holding_period="3-5 years",
                source_documents=["rd_msft_1"],
                confidence_score=70,
            )
        )
        assert created.thesis_id == "t1"
        assert created.current_version_number == 1

        updated = service.update_status(UpdateThesisStatusCommand(thesis_id=created.thesis_id, status=ThesisStatus.RESEARCHED))
        assert updated.current_version_number == 2
        assert updated.status == ThesisStatus.RESEARCHED

        versions = service.list_versions(created.thesis_id)
        assert [item.version_number for item in versions] == [1, 2]
        assert versions[0].status == ThesisStatus.DRAFT
        assert versions[1].status == ThesisStatus.RESEARCHED
