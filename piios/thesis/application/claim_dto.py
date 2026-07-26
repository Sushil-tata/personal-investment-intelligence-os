from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThesisClaimDTO:
    claim_id: str
    thesis_version_id: str
    thesis_id: str | None
    claim_key: str
    claim_text: str
    claim_type: str
    status: str
    active_from: str
    active_to: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ClaimEvidenceInterpretationDTO:
    interpretation_id: str
    claim_id: str
    evidence_id: str
    relation: str
    strength: str
    note: str | None
    effective_from: str
    effective_to: str | None
    supersedes_interpretation_id: str | None
    superseded_by_interpretation_id: str | None
    created_at: str
