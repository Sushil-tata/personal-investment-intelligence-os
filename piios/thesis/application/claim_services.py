from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from piios.thesis.application.claim_commands import (
    AddClaimEvidenceInterpretationCommand,
    CreateClaimCommand,
    UpdateClaimStatusCommand,
)
from piios.thesis.application.claim_dto import ClaimEvidenceInterpretationDTO, ThesisClaimDTO
from piios.thesis.application.claim_queries import ListClaimInterpretationsQuery, ListClaimsForVersionQuery
from piios.thesis.domain.claims import ClaimEvidenceInterpretation, ClaimStatus, ThesisClaim
from piios.thesis.domain.exceptions import (
    ClaimInterpretationConflictError,
    ClaimNotFoundError,
    ClaimVersionBindingError,
    ThesisVersionNotFoundError,
)
from piios.thesis.domain.provenance import ProvenanceRecord
from piios.thesis.infrastructure.claim_evidence_repository_protocols import (
    ClaimEvidenceInterpretationRepositoryProtocol,
    EvidenceItemRepositoryProtocol,
    ProvenanceRepositoryProtocol,
    ThesisClaimRepositoryProtocol,
)
from piios.thesis.infrastructure.repository_protocols import ThesisVersionRepositoryProtocol


class ThesisClaimApplicationService:
    def __init__(
        self,
        claim_repo: ThesisClaimRepositoryProtocol,
        interpretation_repo: ClaimEvidenceInterpretationRepositoryProtocol,
        evidence_item_repo: EvidenceItemRepositoryProtocol,
        thesis_version_repo: ThesisVersionRepositoryProtocol,
        provenance_repo: ProvenanceRepositoryProtocol,
    ) -> None:
        self._claims = claim_repo
        self._interpretations = interpretation_repo
        self._evidence_items = evidence_item_repo
        self._versions = thesis_version_repo
        self._provenance = provenance_repo

    def create_claim(self, command: CreateClaimCommand) -> ThesisClaimDTO:
        linked_version = self._versions.get_by_version_id(command.thesis_version_id)
        if linked_version is None:
            raise ThesisVersionNotFoundError(f"thesis_version_id not found: {command.thesis_version_id}")

        if command.thesis_id and linked_version.thesis_id != command.thesis_id:
            # Prevent cross-linking claim creation against a non-owning thesis.
            raise ClaimVersionBindingError("thesis_id and thesis_version_id reference different thesis roots")

        now = _now()
        claim = ThesisClaim(
            claim_id=command.claim_id,
            thesis_version_id=command.thesis_version_id,
            thesis_id=command.thesis_id,
            claim_key=command.claim_key,
            claim_text=command.claim_text,
            claim_type=command.claim_type,
            status=ClaimStatus.DRAFT,
            active_from=now,
            active_to=None,
            created_at=now,
            updated_at=now,
        )
        self._claims.create(claim)
        self._provenance.create(
            ProvenanceRecord(
                provenance_id=f"prov:{command.claim_id}:create",
                entity_type="THESIS_CLAIM",
                entity_id=command.claim_id,
                action="CREATE",
                actor_type="SYSTEM",
                actor_reference="claim_service",
                ingestion_method="manual",
                source_system="piios",
                extraction_method="none",
                model_name=None,
                model_version=None,
                payload_hash=None,
                created_at=now,
            )
        )
        return _claim_to_dto(claim)

    def update_claim_status(self, command: UpdateClaimStatusCommand) -> ThesisClaimDTO:
        claim = self._claims.get(command.claim_id)
        if claim is None:
            raise ClaimNotFoundError(f"claim_id not found: {command.claim_id}")

        now = _now()
        updated = replace(
            claim,
            status=command.status,
            active_to=now if command.status == ClaimStatus.RETIRED else claim.active_to,
            updated_at=now,
        )
        self._claims.update(updated)
        return _claim_to_dto(updated)

    def add_interpretation(self, command: AddClaimEvidenceInterpretationCommand) -> ClaimEvidenceInterpretationDTO:
        claim = self._claims.get(command.claim_id)
        if claim is None:
            raise ClaimNotFoundError(f"claim_id not found: {command.claim_id}")

        evidence = self._evidence_items.get(command.evidence_id)
        if evidence is None:
            raise ValueError(f"evidence_id not found: {command.evidence_id}")

        now = _now()
        existing = self._interpretations.list_for_claim(command.claim_id)
        active = [row for row in existing if row.effective_to is None]

        if command.supersedes_interpretation_id is None and active:
            # No automatic conflict resolution: caller must supersede an active interpretation explicitly.
            raise ClaimInterpretationConflictError("active interpretation exists; provide supersedes_interpretation_id")

        if command.supersedes_interpretation_id is not None:
            previous = self._interpretations.get(command.supersedes_interpretation_id)
            if previous is None:
                raise ClaimInterpretationConflictError("supersedes interpretation not found")
            if previous.claim_id != command.claim_id:
                raise ClaimInterpretationConflictError("cannot supersede interpretation from different claim")
            if previous.effective_to is not None:
                raise ClaimInterpretationConflictError("cannot supersede already closed interpretation")

            self._interpretations.update(
                replace(
                    previous,
                    effective_to=now,
                    superseded_by_interpretation_id=command.interpretation_id,
                )
            )

        interpretation = ClaimEvidenceInterpretation(
            interpretation_id=command.interpretation_id,
            claim_id=command.claim_id,
            evidence_id=command.evidence_id,
            relation=command.relation,
            strength=command.strength,
            note=command.note,
            effective_from=now,
            effective_to=None,
            supersedes_interpretation_id=command.supersedes_interpretation_id,
            superseded_by_interpretation_id=None,
            created_at=now,
        )
        self._interpretations.create(interpretation)
        return _interpretation_to_dto(interpretation)

    def list_claims_for_version(self, query: ListClaimsForVersionQuery) -> list[ThesisClaimDTO]:
        items = self._claims.list_for_version(query.thesis_version_id)
        return [_claim_to_dto(item) for item in items]

    def list_interpretations(self, query: ListClaimInterpretationsQuery) -> list[ClaimEvidenceInterpretationDTO]:
        items = self._interpretations.list_for_claim(query.claim_id)
        items.sort(key=lambda row: row.created_at)
        return [_interpretation_to_dto(item) for item in items]


def _claim_to_dto(item: ThesisClaim) -> ThesisClaimDTO:
    return ThesisClaimDTO(
        claim_id=item.claim_id,
        thesis_version_id=item.thesis_version_id,
        thesis_id=item.thesis_id,
        claim_key=item.claim_key,
        claim_text=item.claim_text,
        claim_type=item.claim_type,
        status=item.status.value,
        active_from=item.active_from.isoformat(),
        active_to=item.active_to.isoformat() if item.active_to else None,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


def _interpretation_to_dto(item: ClaimEvidenceInterpretation) -> ClaimEvidenceInterpretationDTO:
    return ClaimEvidenceInterpretationDTO(
        interpretation_id=item.interpretation_id,
        claim_id=item.claim_id,
        evidence_id=item.evidence_id,
        relation=item.relation.value,
        strength=item.strength,
        note=item.note,
        effective_from=item.effective_from.isoformat(),
        effective_to=item.effective_to.isoformat() if item.effective_to else None,
        supersedes_interpretation_id=item.supersedes_interpretation_id,
        superseded_by_interpretation_id=item.superseded_by_interpretation_id,
        created_at=item.created_at.isoformat(),
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)
