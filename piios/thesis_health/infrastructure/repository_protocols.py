from __future__ import annotations

from typing import Protocol

from piios.thesis_health.domain.entities import ThesisHealthSnapshot


class ThesisHealthRepositoryProtocol(Protocol):
    def create(self, snapshot: ThesisHealthSnapshot) -> ThesisHealthSnapshot:
        ...

    def get_latest(self, thesis_version_id: str) -> ThesisHealthSnapshot | None:
        ...

    def list_history(self, thesis_version_id: str) -> list[ThesisHealthSnapshot]:
        ...
