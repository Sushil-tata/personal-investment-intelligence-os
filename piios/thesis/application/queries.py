from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GetThesisQuery:
    thesis_id: str


@dataclass(frozen=True)
class ListThesesQuery:
    include_archived: bool = True
