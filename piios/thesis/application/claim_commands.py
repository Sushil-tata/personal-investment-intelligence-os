from __future__ import annotations

from dataclasses import dataclass

from piios.thesis.domain.claims import ClaimStatus, InterpretationRelation


@dataclass(frozen=True)
class CreateClaimCommand:
    claim_id: str
    thesis_version_id: str
    thesis_id: str | None
    claim_key: str
    claim_text: str
    claim_type: str


@dataclass(frozen=True)
class UpdateClaimStatusCommand:
    claim_id: str
    status: ClaimStatus


@dataclass(frozen=True)
class AddClaimEvidenceInterpretationCommand:
    interpretation_id: str
    claim_id: str
    evidence_id: str
    relation: InterpretationRelation
    strength: str
    note: str | None = None
    supersedes_interpretation_id: str | None = None
