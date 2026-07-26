from __future__ import annotations

from piios.thesis.domain.claims import ClaimEvidenceInterpretation, ThesisClaim
from piios.thesis.domain.evidence import EvidenceItem, EvidenceSource
from piios.thesis.domain.provenance import ProvenanceRecord
from piios.thesis.infrastructure.claim_evidence_repository_protocols import (
    ClaimEvidenceInterpretationRepositoryProtocol,
    EvidenceItemRepositoryProtocol,
    EvidenceSourceRepositoryProtocol,
    ProvenanceRepositoryProtocol,
    ThesisClaimRepositoryProtocol,
)


class InMemoryThesisClaimRepository(ThesisClaimRepositoryProtocol):
    def __init__(self) -> None:
        self._items: dict[str, ThesisClaim] = {}

    def create(self, claim: ThesisClaim) -> ThesisClaim:
        self._items[claim.claim_id] = claim
        return claim

    def get(self, claim_id: str) -> ThesisClaim | None:
        return self._items.get(claim_id)

    def update(self, claim: ThesisClaim) -> ThesisClaim:
        self._items[claim.claim_id] = claim
        return claim

    def list_for_version(self, thesis_version_id: str) -> list[ThesisClaim]:
        return [item for item in self._items.values() if item.thesis_version_id == thesis_version_id]


class InMemoryEvidenceSourceRepository(EvidenceSourceRepositoryProtocol):
    def __init__(self) -> None:
        self._items: dict[str, EvidenceSource] = {}

    def create(self, source: EvidenceSource) -> EvidenceSource:
        self._items[source.source_id] = source
        return source

    def get(self, source_id: str) -> EvidenceSource | None:
        return self._items.get(source_id)


class InMemoryEvidenceItemRepository(EvidenceItemRepositoryProtocol):
    def __init__(self) -> None:
        self._items: dict[str, EvidenceItem] = {}

    def create(self, item: EvidenceItem) -> EvidenceItem:
        self._items[item.evidence_id] = item
        return item

    def get(self, evidence_id: str) -> EvidenceItem | None:
        return self._items.get(evidence_id)


class InMemoryClaimEvidenceInterpretationRepository(ClaimEvidenceInterpretationRepositoryProtocol):
    def __init__(self) -> None:
        self._items: dict[str, ClaimEvidenceInterpretation] = {}

    def create(self, interpretation: ClaimEvidenceInterpretation) -> ClaimEvidenceInterpretation:
        self._items[interpretation.interpretation_id] = interpretation
        return interpretation

    def get(self, interpretation_id: str) -> ClaimEvidenceInterpretation | None:
        return self._items.get(interpretation_id)

    def update(self, interpretation: ClaimEvidenceInterpretation) -> ClaimEvidenceInterpretation:
        self._items[interpretation.interpretation_id] = interpretation
        return interpretation

    def list_for_claim(self, claim_id: str) -> list[ClaimEvidenceInterpretation]:
        return [item for item in self._items.values() if item.claim_id == claim_id]


class InMemoryProvenanceRepository(ProvenanceRepositoryProtocol):
    def __init__(self) -> None:
        self._items: list[ProvenanceRecord] = []

    def create(self, item: ProvenanceRecord) -> ProvenanceRecord:
        self._items.append(item)
        return item

    def list_for_entity(self, entity_type: str, entity_id: str) -> list[ProvenanceRecord]:
        return [row for row in self._items if row.entity_type == entity_type and row.entity_id == entity_id]
