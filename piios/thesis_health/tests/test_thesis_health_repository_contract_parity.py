from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlmodel import SQLModel, Session, create_engine

from piios.thesis_health.domain.entities import ThesisHealthSnapshot
from piios.thesis_health.infrastructure.in_memory_repositories import InMemoryThesisHealthRepository
from piios.thesis_health.infrastructure.sqlmodel_repositories import SQLModelThesisHealthRepository
from piios_backend.models import entities as backend_entities  # noqa: F401
from piios.thesis_health.infrastructure import sqlmodel_entities as thesis_health_sqlmodel_entities  # noqa: F401


@pytest.fixture(params=["in_memory", "sqlmodel"])
def thesis_health_repo(request, tmp_path):
    if request.param == "in_memory":
        return InMemoryThesisHealthRepository()

    db_path = tmp_path / "thesis_health_repo.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    request.addfinalizer(session.close)
    return SQLModelThesisHealthRepository(session)


def _snapshot(computation_version: str, second: int) -> ThesisHealthSnapshot:
    return ThesisHealthSnapshot(
        thesis_version_id="t1:v1",
        computation_version=computation_version,
        computed_at=datetime(2026, 7, 27, 10, 0, second, tzinfo=timezone.utc),
        evidence_freshness=0.8,
        evidence_quality=0.7,
        supporting_strength=0.6,
        contradictory_strength=0.1,
        provenance_completeness=0.9,
        thesis_health_index=0.78,
    )


def test_repository_contract_latest_and_sorted_history(thesis_health_repo) -> None:
    first = _snapshot("v1", 0)
    second = _snapshot("v2", 1)

    thesis_health_repo.create(second)
    thesis_health_repo.create(first)

    history = thesis_health_repo.list_history("t1:v1")
    assert [row.computation_version for row in history] == ["v1", "v2"]
    assert thesis_health_repo.get_latest("t1:v1") == second


def test_repository_contract_duplicate_guard(thesis_health_repo) -> None:
    item = _snapshot("v1", 0)
    thesis_health_repo.create(item)
    with pytest.raises(ValueError):
        thesis_health_repo.create(item)
