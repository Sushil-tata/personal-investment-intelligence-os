from __future__ import annotations

from dataclasses import dataclass

from .enums import ThesisStatus
from .exceptions import InvalidThesisStatusTransitionError, ThesisDomainError


_ALLOWED_STATUS_TRANSITIONS: dict[ThesisStatus, set[ThesisStatus]] = {
    ThesisStatus.DRAFT: {ThesisStatus.RESEARCHED, ThesisStatus.ARCHIVED},
    ThesisStatus.RESEARCHED: {ThesisStatus.RISK_CHECKED, ThesisStatus.ARCHIVED},
    ThesisStatus.RISK_CHECKED: {ThesisStatus.PENDING_REVIEW, ThesisStatus.ARCHIVED},
    ThesisStatus.PENDING_REVIEW: {ThesisStatus.APPROVED, ThesisStatus.ARCHIVED},
    ThesisStatus.APPROVED: {ThesisStatus.ARCHIVED},
    ThesisStatus.ARCHIVED: set(),
}


@dataclass(frozen=True)
class ThesisVersionNumber:
    value: int

    def __post_init__(self) -> None:
        if self.value < 1:
            raise ThesisDomainError("version number must be >= 1")

    def next(self) -> "ThesisVersionNumber":
        return ThesisVersionNumber(self.value + 1)


def ensure_valid_status_transition(current: ThesisStatus, target: ThesisStatus) -> None:
    if current == target:
        return
    if target not in _ALLOWED_STATUS_TRANSITIONS[current]:
        raise InvalidThesisStatusTransitionError(f"invalid status transition: {current.value} -> {target.value}")
