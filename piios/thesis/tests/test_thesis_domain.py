import pytest

from piios.thesis.domain.enums import ThesisStatus
from piios.thesis.domain.exceptions import InvalidThesisStatusTransitionError, ThesisDomainError
from piios.thesis.domain.value_objects import ThesisVersionNumber, ensure_valid_status_transition


def test_version_number_must_be_positive() -> None:
    with pytest.raises(ThesisDomainError):
        ThesisVersionNumber(0)


def test_status_transition_allows_linear_progression() -> None:
    ensure_valid_status_transition(ThesisStatus.DRAFT, ThesisStatus.RESEARCHED)
    ensure_valid_status_transition(ThesisStatus.RESEARCHED, ThesisStatus.RISK_CHECKED)
    ensure_valid_status_transition(ThesisStatus.RISK_CHECKED, ThesisStatus.PENDING_REVIEW)
    ensure_valid_status_transition(ThesisStatus.PENDING_REVIEW, ThesisStatus.APPROVED)


def test_status_transition_rejects_backward_move() -> None:
    with pytest.raises(InvalidThesisStatusTransitionError):
        ensure_valid_status_transition(ThesisStatus.APPROVED, ThesisStatus.RESEARCHED)


def test_archived_is_terminal() -> None:
    with pytest.raises(InvalidThesisStatusTransitionError):
        ensure_valid_status_transition(ThesisStatus.ARCHIVED, ThesisStatus.DRAFT)
