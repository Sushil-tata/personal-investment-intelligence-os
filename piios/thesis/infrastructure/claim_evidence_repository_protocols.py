from __future__ import annotations

from typing import Protocol

from piios.thesis.domain.claims import ClaimEvidenceInterpretation, ThesisClaim
from piios.thesis.domain.evidence import EvidenceItem, EvidenceSource
from piios.thesis.domain.provenance import ProvenanceRecord


class ThesisClaimRepositoryProtocol(Protocol):
    def create(self, claim: ThesisClaim) -> ThesisClaim:
        ...

    def get(self, claim_id: str) -> ThesisClaim | None:
        ...

    def update(self, claim: ThesisClaim) -> ThesisClaim:
        ...

    def list_for_version(self, thesis_version_id: str) -> list[ThesisClaim]:
        ...


class EvidenceSourceRepositoryProtocol(Protocol):
    def create(self, source: EvidenceSource) -> EvidenceSource:
        ...

    def get(self, source_id: str) -> EvidenceSource | None:
        ...


class EvidenceItemRepositoryProtocol(Protocol):
    def create(self, item: EvidenceItem) -> EvidenceItem:
        ...

    def get(self, evidence_id: str) -> EvidenceItem | None:
        ...


class ClaimEvidenceInterpretationRepositoryProtocol(Protocol):
    def create(self, interpretation: ClaimEvidenceInterpretation) -> ClaimEvidenceInterpretation:
        ...

    def get(self, interpretation_id: str) -> ClaimEvidenceInterpretation | None:
        ...

    def update(self, interpretation: ClaimEvidenceInterpretation) -> ClaimEvidenceInterpretation:
        ...

    def list_for_claim(self, claim_id: str) -> list[ClaimEvidenceInterpretation]:
        ...


class ProvenanceRepositoryProtocol(Protocol):
    def create(self, item: ProvenanceRecord) -> ProvenanceRecord:
        ...

    def list_for_entity(self, entity_type: str, entity_id: str) -> list[ProvenanceRecord]:
        ...
