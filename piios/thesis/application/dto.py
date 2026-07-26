from __future__ import annotations

from dataclasses import dataclass, field

from piios.thesis.domain.enums import ThesisStatus


@dataclass(frozen=True)
class ThesisVersionDTO:
    version_id: str
    thesis_id: str
    version_number: int
    status: ThesisStatus
    created_at: str


@dataclass(frozen=True)
class ThesisDTO:
    thesis_id: str
    ticker: str
    asset_name: str
    theme: str
    bucket: str
    thesis: str
    bull_case: str
    bear_case: str
    why_now: str
    why_not_now: str
    invalidation_trigger: str
    valuation_notes: str
    expected_holding_period: str
    source_documents: list[str] = field(default_factory=list)
    confidence_score: float = 0.0
    status: ThesisStatus = ThesisStatus.DRAFT
    created_at: str = ""
    updated_at: str = ""
    current_version_number: int = 1
    closed_reason: str | None = None
    closed_at: str | None = None
