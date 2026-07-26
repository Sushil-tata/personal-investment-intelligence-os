from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .enums import ThesisStatus


@dataclass(frozen=True)
class ThesisRoot:
    thesis_id: str
    ticker: str
    lifecycle_status: ThesisStatus
    current_version_number: int
    created_at: datetime
    updated_at: datetime
    closed_reason: str | None = None
    closed_at: datetime | None = None


@dataclass(frozen=True)
class ThesisVersion:
    version_id: str
    thesis_id: str
    version_number: int
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
    source_documents: tuple[str, ...]
    confidence_score: float
    status: ThesisStatus
    created_at: datetime
