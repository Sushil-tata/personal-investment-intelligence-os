from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ListClaimsForVersionQuery:
    thesis_version_id: str


@dataclass(frozen=True)
class ListClaimInterpretationsQuery:
    claim_id: str
