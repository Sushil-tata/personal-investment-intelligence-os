from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ClaimStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


class InterpretationRelation(str, Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True)
class ThesisClaim:
    claim_id: str
    thesis_version_id: str
    # Optional denormalized reference for joins/queries without changing source-of-truth linkage.
    thesis_id: str | None
    claim_key: str
    claim_text: str
    claim_type: str
    status: ClaimStatus
    active_from: datetime
    active_to: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ClaimEvidenceInterpretation:
    interpretation_id: str
    claim_id: str
    evidence_id: str
    relation: InterpretationRelation
    strength: str
    note: str | None
    effective_from: datetime
    effective_to: datetime | None
    supersedes_interpretation_id: str | None
    superseded_by_interpretation_id: str | None
    created_at: datetime
