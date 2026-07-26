from __future__ import annotations

from piios.thesis.domain.entities import ThesisRoot, ThesisVersion
from piios.thesis.infrastructure.repository_protocols import ThesisRootRepositoryProtocol, ThesisVersionRepositoryProtocol


class InMemoryThesisRootRepository(ThesisRootRepositoryProtocol):
    def __init__(self) -> None:
        self._items: dict[str, ThesisRoot] = {}

    def next_thesis_id(self) -> str:
        return f"t{len(self._items) + 1}"

    def create(self, root: ThesisRoot) -> ThesisRoot:
        self._items[root.thesis_id] = root
        return root

    def get(self, thesis_id: str) -> ThesisRoot | None:
        return self._items.get(thesis_id)

    def list(self) -> list[ThesisRoot]:
        return list(self._items.values())

    def update(self, root: ThesisRoot) -> ThesisRoot:
        self._items[root.thesis_id] = root
        return root


class InMemoryThesisVersionRepository(ThesisVersionRepositoryProtocol):
    def __init__(self) -> None:
        self._items: dict[str, list[ThesisVersion]] = {}

    def create(self, version: ThesisVersion) -> ThesisVersion:
        self._items.setdefault(version.thesis_id, []).append(version)
        return version

    def get_by_version_id(self, version_id: str) -> ThesisVersion | None:
        for versions in self._items.values():
            for item in versions:
                if item.version_id == version_id:
                    return item
        return None

    def get_latest(self, thesis_id: str) -> ThesisVersion | None:
        versions = self._items.get(thesis_id, [])
        return versions[-1] if versions else None

    def list_for_thesis(self, thesis_id: str) -> list[ThesisVersion]:
        return list(self._items.get(thesis_id, []))
