from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EvidenceSourceType(str, Enum):
    FILING = "FILING"
    NEWS = "NEWS"
    RESEARCH = "RESEARCH"
    INTERNAL_METRIC = "INTERNAL_METRIC"
    OTHER = "OTHER"


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    source_type: EvidenceSourceType
    publisher: str
    url: str | None
    source_system: str
    published_at: datetime | None
    retrieved_at: datetime
    credibility_tier: str
    created_at: datetime


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    source_id: str
    title: str
    excerpt: str
    content_hash: str | None
    as_of_date: str | None
    metadata_json: str
    created_at: datetime
