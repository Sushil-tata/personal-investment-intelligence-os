from __future__ import annotations

from dataclasses import dataclass, field

from piios.thesis.domain.enums import ThesisStatus


@dataclass(frozen=True)
class CreateThesisCommand:
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
    thesis_id: str | None = None


@dataclass(frozen=True)
class CreateThesisVersionCommand:
    thesis_id: str
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


@dataclass(frozen=True)
class UpdateThesisStatusCommand:
    thesis_id: str
    status: ThesisStatus
