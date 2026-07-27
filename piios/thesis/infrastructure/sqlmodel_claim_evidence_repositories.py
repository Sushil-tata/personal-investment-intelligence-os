from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from piios.thesis.domain.claims import ClaimEvidenceInterpretation, ClaimStatus, InterpretationRelation, ThesisClaim
from piios.thesis.domain.evidence import EvidenceItem, EvidenceSource, EvidenceSourceType
from piios.thesis.domain.provenance import ProvenanceRecord
from piios.thesis.infrastructure.claim_evidence_repository_protocols import (
    ClaimEvidenceInterpretationRepositoryProtocol,
    EvidenceItemRepositoryProtocol,
    EvidenceSourceRepositoryProtocol,
    ProvenanceRepositoryProtocol,
    ThesisClaimRepositoryProtocol,
)
from piios_backend.models.entities import (
    ClaimEvidenceInterpretationEntity,
    EvidenceItemEntity,
    EvidenceSourceEntity,
    ProvenanceRecordEntity,
    ThesisClaimEntity,
)


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


class SQLModelThesisClaimRepository(ThesisClaimRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, claim: ThesisClaim) -> ThesisClaim:
        row = ThesisClaimEntity(
            claim_id=claim.claim_id,
            thesis_version_id=claim.thesis_version_id,
            thesis_id=claim.thesis_id,
            claim_key=claim.claim_key,
            claim_text=claim.claim_text,
            claim_type=claim.claim_type,
            status=claim.status.value,
            active_from=claim.active_from.isoformat(),
            active_to=claim.active_to.isoformat() if claim.active_to else None,
            created_at=claim.created_at.isoformat(),
            updated_at=claim.updated_at.isoformat(),
        )
        self._session.add(row)
        self._session.commit()
        return claim

    def get(self, claim_id: str) -> ThesisClaim | None:
        row = self._session.exec(select(ThesisClaimEntity).where(ThesisClaimEntity.claim_id == claim_id)).first()
        return _claim_from_row(row) if row else None

    def update(self, claim: ThesisClaim) -> ThesisClaim:
        row = self._session.exec(select(ThesisClaimEntity).where(ThesisClaimEntity.claim_id == claim.claim_id)).first()
        if row is None:
            raise ValueError(f"claim_id not found: {claim.claim_id}")

        row.status = claim.status.value
        row.active_to = claim.active_to.isoformat() if claim.active_to else None
        row.updated_at = claim.updated_at.isoformat()
        self._session.add(row)
        self._session.commit()
        return claim

    def list_for_version(self, thesis_version_id: str) -> list[ThesisClaim]:
        rows = self._session.exec(
            select(ThesisClaimEntity)
            .where(ThesisClaimEntity.thesis_version_id == thesis_version_id)
            .order_by(ThesisClaimEntity.created_at.asc())
        ).all()
        return [_claim_from_row(row) for row in rows]


class SQLModelEvidenceSourceRepository(EvidenceSourceRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, source: EvidenceSource) -> EvidenceSource:
        row = EvidenceSourceEntity(
            source_id=source.source_id,
            source_type=source.source_type.value,
            publisher=source.publisher,
            url=source.url,
            source_system=source.source_system,
            published_at=source.published_at.isoformat() if source.published_at else None,
            retrieved_at=source.retrieved_at.isoformat(),
            credibility_tier=source.credibility_tier,
            created_at=source.created_at.isoformat(),
        )
        self._session.add(row)
        self._session.commit()
        return source

    def get(self, source_id: str) -> EvidenceSource | None:
        row = self._session.exec(select(EvidenceSourceEntity).where(EvidenceSourceEntity.source_id == source_id)).first()
        return _source_from_row(row) if row else None


class SQLModelEvidenceItemRepository(EvidenceItemRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, item: EvidenceItem) -> EvidenceItem:
        row = EvidenceItemEntity(
            evidence_id=item.evidence_id,
            source_id=item.source_id,
            title=item.title,
            excerpt=item.excerpt,
            content_hash=item.content_hash,
            as_of_date=item.as_of_date,
            metadata_json=item.metadata_json,
            created_at=item.created_at.isoformat(),
        )
        self._session.add(row)
        self._session.commit()
        return item

    def get(self, evidence_id: str) -> EvidenceItem | None:
        row = self._session.exec(select(EvidenceItemEntity).where(EvidenceItemEntity.evidence_id == evidence_id)).first()
        return _item_from_row(row) if row else None


class SQLModelClaimEvidenceInterpretationRepository(ClaimEvidenceInterpretationRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, interpretation: ClaimEvidenceInterpretation) -> ClaimEvidenceInterpretation:
        row = ClaimEvidenceInterpretationEntity(
            interpretation_id=interpretation.interpretation_id,
            claim_id=interpretation.claim_id,
            evidence_id=interpretation.evidence_id,
            relation=interpretation.relation.value,
            strength=interpretation.strength,
            note=interpretation.note,
            effective_from=interpretation.effective_from.isoformat(),
            effective_to=interpretation.effective_to.isoformat() if interpretation.effective_to else None,
            supersedes_interpretation_id=interpretation.supersedes_interpretation_id,
            superseded_by_interpretation_id=interpretation.superseded_by_interpretation_id,
            created_at=interpretation.created_at.isoformat(),
        )
        self._session.add(row)
        self._session.commit()
        return interpretation

    def get(self, interpretation_id: str) -> ClaimEvidenceInterpretation | None:
        row = self._session.exec(
            select(ClaimEvidenceInterpretationEntity).where(
                ClaimEvidenceInterpretationEntity.interpretation_id == interpretation_id
            )
        ).first()
        return _interpretation_from_row(row) if row else None

    def update(self, interpretation: ClaimEvidenceInterpretation) -> ClaimEvidenceInterpretation:
        row = self._session.exec(
            select(ClaimEvidenceInterpretationEntity).where(
                ClaimEvidenceInterpretationEntity.interpretation_id == interpretation.interpretation_id
            )
        ).first()
        if row is None:
            raise ValueError(f"interpretation_id not found: {interpretation.interpretation_id}")

        # Append-only semantics: only supersession/effective dating fields may change.
        immutable_current = (
            row.claim_id,
            row.evidence_id,
            row.relation,
            row.strength,
            row.note,
            row.effective_from,
            row.created_at,
        )
        immutable_target = (
            interpretation.claim_id,
            interpretation.evidence_id,
            interpretation.relation.value,
            interpretation.strength,
            interpretation.note,
            interpretation.effective_from.isoformat(),
            interpretation.created_at.isoformat(),
        )
        if immutable_current != immutable_target:
            raise ValueError("claim evidence interpretation is append-only; immutable fields cannot be modified")

        row.effective_to = interpretation.effective_to.isoformat() if interpretation.effective_to else None
        row.supersedes_interpretation_id = interpretation.supersedes_interpretation_id
        row.superseded_by_interpretation_id = interpretation.superseded_by_interpretation_id
        self._session.add(row)
        self._session.commit()
        return interpretation

    def list_for_claim(self, claim_id: str) -> list[ClaimEvidenceInterpretation]:
        rows = self._session.exec(
            select(ClaimEvidenceInterpretationEntity)
            .where(ClaimEvidenceInterpretationEntity.claim_id == claim_id)
            .order_by(ClaimEvidenceInterpretationEntity.created_at.asc())
        ).all()
        return [_interpretation_from_row(row) for row in rows]


class SQLModelProvenanceRepository(ProvenanceRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, item: ProvenanceRecord) -> ProvenanceRecord:
        row = ProvenanceRecordEntity(
            provenance_id=item.provenance_id,
            entity_type=item.entity_type,
            entity_id=item.entity_id,
            action=item.action,
            actor_type=item.actor_type,
            actor_reference=item.actor_reference,
            ingestion_method=item.ingestion_method,
            source_system=item.source_system,
            extraction_method=item.extraction_method,
            model_name=item.model_name,
            model_version=item.model_version,
            payload_hash=item.payload_hash,
            created_at=item.created_at.isoformat(),
        )
        self._session.add(row)
        self._session.commit()
        return item

    def list_for_entity(self, entity_type: str, entity_id: str) -> list[ProvenanceRecord]:
        rows = self._session.exec(
            select(ProvenanceRecordEntity)
            .where(
                ProvenanceRecordEntity.entity_type == entity_type,
                ProvenanceRecordEntity.entity_id == entity_id,
            )
            .order_by(ProvenanceRecordEntity.created_at.asc())
        ).all()
        return [_provenance_from_row(row) for row in rows]


def _claim_from_row(row: ThesisClaimEntity) -> ThesisClaim:
    return ThesisClaim(
        claim_id=row.claim_id,
        thesis_version_id=row.thesis_version_id,
        thesis_id=row.thesis_id,
        claim_key=row.claim_key,
        claim_text=row.claim_text,
        claim_type=row.claim_type,
        status=ClaimStatus(row.status),
        active_from=_parse_dt(row.active_from),
        active_to=_parse_dt(row.active_to) if row.active_to else None,
        created_at=_parse_dt(row.created_at),
        updated_at=_parse_dt(row.updated_at),
    )


def _source_from_row(row: EvidenceSourceEntity) -> EvidenceSource:
    return EvidenceSource(
        source_id=row.source_id,
        source_type=EvidenceSourceType(row.source_type),
        publisher=row.publisher,
        url=row.url,
        source_system=row.source_system,
        published_at=_parse_dt(row.published_at) if row.published_at else None,
        retrieved_at=_parse_dt(row.retrieved_at),
        credibility_tier=row.credibility_tier,
        created_at=_parse_dt(row.created_at),
    )


def _item_from_row(row: EvidenceItemEntity) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=row.evidence_id,
        source_id=row.source_id,
        title=row.title,
        excerpt=row.excerpt,
        content_hash=row.content_hash,
        as_of_date=row.as_of_date,
        metadata_json=row.metadata_json,
        created_at=_parse_dt(row.created_at),
    )


def _interpretation_from_row(row: ClaimEvidenceInterpretationEntity) -> ClaimEvidenceInterpretation:
    return ClaimEvidenceInterpretation(
        interpretation_id=row.interpretation_id,
        claim_id=row.claim_id,
        evidence_id=row.evidence_id,
        relation=InterpretationRelation(row.relation),
        strength=row.strength,
        note=row.note,
        effective_from=_parse_dt(row.effective_from),
        effective_to=_parse_dt(row.effective_to) if row.effective_to else None,
        supersedes_interpretation_id=row.supersedes_interpretation_id,
        superseded_by_interpretation_id=row.superseded_by_interpretation_id,
        created_at=_parse_dt(row.created_at),
    )


def _provenance_from_row(row: ProvenanceRecordEntity) -> ProvenanceRecord:
    return ProvenanceRecord(
        provenance_id=row.provenance_id,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        action=row.action,
        actor_type=row.actor_type,
        actor_reference=row.actor_reference,
        ingestion_method=row.ingestion_method,
        source_system=row.source_system,
        extraction_method=row.extraction_method,
        model_name=row.model_name,
        model_version=row.model_version,
        payload_hash=row.payload_hash,
        created_at=_parse_dt(row.created_at),
    )
