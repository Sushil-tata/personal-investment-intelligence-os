from __future__ import annotations

from datetime import datetime, timezone

import pytest

from piios.thesis_health.domain.entities import ThesisHealthSnapshot
from piios.thesis_health.infrastructure.in_memory_repositories import InMemoryThesisHealthRepository


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


def test_in_memory_thesis_health_repository_history_and_latest() -> None:
    repo = InMemoryThesisHealthRepository()
    first = _snapshot("v1", 0)
    second = _snapshot("v2", 1)

    repo.create(second)
    repo.create(first)

    history = repo.list_history("t1:v1")
    assert [row.computation_version for row in history] == ["v1", "v2"]
    assert repo.get_latest("t1:v1") == second


def test_in_memory_thesis_health_repository_rejects_duplicate_tuple() -> None:
    repo = InMemoryThesisHealthRepository()
    item = _snapshot("v1", 0)
    repo.create(item)
    with pytest.raises(ValueError):
        repo.create(item)
