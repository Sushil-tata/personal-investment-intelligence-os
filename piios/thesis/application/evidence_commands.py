from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from piios.thesis.domain.evidence import EvidenceSourceType


@dataclass(frozen=True)
class CreateEvidenceSourceCommand:
    source_id: str
    source_type: EvidenceSourceType
    publisher: str
    url: str | None
    source_system: str
    published_at: datetime | None
    retrieved_at: datetime
    credibility_tier: str


@dataclass(frozen=True)
class CreateEvidenceItemCommand:
    evidence_id: str
    source_id: str
    title: str
    excerpt: str
    content_hash: str | None
    as_of_date: str | None
    metadata_json: str
