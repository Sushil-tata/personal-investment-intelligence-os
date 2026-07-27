from __future__ import annotations

from typing import Protocol

from piios.thesis.domain.entities import ThesisRoot, ThesisVersion


class ThesisRootRepositoryProtocol(Protocol):
    def next_thesis_id(self) -> str:
        ...

    def create(self, root: ThesisRoot) -> ThesisRoot:
        ...

    def get(self, thesis_id: str) -> ThesisRoot | None:
        ...

    def list(self) -> list[ThesisRoot]:
        ...

    def update(self, root: ThesisRoot) -> ThesisRoot:
        ...


class ThesisVersionRepositoryProtocol(Protocol):
    def create(self, version: ThesisVersion) -> ThesisVersion:
        ...

    def get_by_version_id(self, version_id: str) -> ThesisVersion | None:
        ...

    def get_latest(self, thesis_id: str) -> ThesisVersion | None:
        ...

    def list_for_thesis(self, thesis_id: str) -> list[ThesisVersion]:
        ...
