from __future__ import annotations

from piios.thesis_health.domain.entities import ThesisHealthSnapshot
from piios.thesis_health.infrastructure.repository_protocols import ThesisHealthRepositoryProtocol


class InMemoryThesisHealthRepository(ThesisHealthRepositoryProtocol):
    def __init__(self) -> None:
        self._by_version_id: dict[str, list[ThesisHealthSnapshot]] = {}

    def create(self, snapshot: ThesisHealthSnapshot) -> ThesisHealthSnapshot:
        rows = self._by_version_id.setdefault(snapshot.thesis_version_id, [])
        if any(
            existing.thesis_version_id == snapshot.thesis_version_id
            and existing.computation_version == snapshot.computation_version
            and existing.computed_at == snapshot.computed_at
            for existing in rows
        ):
            raise ValueError("duplicate thesis health snapshot for thesis_version_id/computation_version/computed_at")
        rows.append(snapshot)
        rows.sort(key=lambda row: (row.computed_at, row.computation_version))
        return snapshot

    def get_latest(self, thesis_version_id: str) -> ThesisHealthSnapshot | None:
        rows = self._by_version_id.get(thesis_version_id, [])
        return rows[-1] if rows else None

    def list_history(self, thesis_version_id: str) -> list[ThesisHealthSnapshot]:
        return list(self._by_version_id.get(thesis_version_id, []))
