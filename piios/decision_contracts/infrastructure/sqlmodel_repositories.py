from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from piios.decision_contracts.domain.decision import InvestmentDecision
from piios.decision_contracts.domain.proposal import (
    RecommendationClaimLink,
    RecommendationEvidenceLink,
    RecommendationInputSnapshot,
    RecommendationProposal,
    RecommendationProposalVersion,
    RecommendationReason,
)
from piios.decision_contracts.domain.recommendation_trace import RecommendationTrace, TraceEntry
from piios.decision_contracts.infrastructure.repository_protocols import (
    InvestmentDecisionRepositoryProtocol,
    RecommendationProposalRepositoryProtocol,
    RecommendationProposalVersionRepositoryProtocol,
    RecommendationReasonRepositoryProtocol,
    RecommendationSnapshotRepositoryProtocol,
    RecommendationTraceRepositoryProtocol,
)
from piios.decision_contracts.infrastructure.sqlmodel_entities import (
    InvestmentDecisionEntity,
    RecommendationClaimLinkEntity,
    RecommendationEvidenceLinkEntity,
    RecommendationInputSnapshotEntity,
    RecommendationProposalEntity,
    RecommendationProposalVersionEntity,
    RecommendationReasonEntity,
    RecommendationTraceEntity,
    RecommendationTraceEntryEntity,
)
from piios.decision_contracts.infrastructure.sqlmodel_mappers import (
    claim_link_from_row,
    claim_link_to_row,
    decision_from_row,
    decision_to_row,
    evidence_link_from_row,
    evidence_link_to_row,
    proposal_from_row,
    proposal_to_row,
    proposal_version_from_row,
    proposal_version_to_row,
    reason_from_row,
    reason_to_row,
    snapshot_from_row,
    snapshot_to_row,
    trace_entry_from_row,
    trace_entry_to_row,
    trace_from_row,
    trace_to_row,
)


class SQLModelRecommendationProposalRepository(RecommendationProposalRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, proposal: RecommendationProposal) -> RecommendationProposal:
        self._session.add(proposal_to_row(proposal))
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError(f"proposal_id already exists: {proposal.proposal_id}") from exc
        return proposal

    def create_uncommitted(self, proposal: RecommendationProposal) -> RecommendationProposal:
        self._session.add(proposal_to_row(proposal))
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError(f"proposal_id already exists: {proposal.proposal_id}") from exc
        return proposal

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    def get(self, proposal_id: str) -> RecommendationProposal | None:
        row = self._session.exec(
            select(RecommendationProposalEntity).where(RecommendationProposalEntity.proposal_id == proposal_id)
        ).first()
        return proposal_from_row(row) if row else None


class SQLModelRecommendationProposalVersionRepository(RecommendationProposalVersionRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, version: RecommendationProposalVersion) -> RecommendationProposalVersion:
        self._session.add(proposal_version_to_row(version))
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError(
                "proposal_version duplicate on proposal_version_id, snapshot_id, or (proposal_id, version_number)"
            ) from exc
        return version

    def create_uncommitted(self, version: RecommendationProposalVersion) -> RecommendationProposalVersion:
        self._session.add(proposal_version_to_row(version))
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError(
                "proposal_version duplicate on proposal_version_id, snapshot_id, or (proposal_id, version_number)"
            ) from exc
        return version

    def get(self, proposal_version_id: str) -> RecommendationProposalVersion | None:
        row = self._session.exec(
            select(RecommendationProposalVersionEntity).where(
                RecommendationProposalVersionEntity.proposal_version_id == proposal_version_id
            )
        ).first()
        return proposal_version_from_row(row) if row else None

    def list_for_proposal(self, proposal_id: str) -> list[RecommendationProposalVersion]:
        rows = self._session.exec(
            select(RecommendationProposalVersionEntity)
            .where(RecommendationProposalVersionEntity.proposal_id == proposal_id)
            .order_by(
                RecommendationProposalVersionEntity.version_number.asc(),
                RecommendationProposalVersionEntity.created_at.asc(),
                RecommendationProposalVersionEntity.proposal_version_id.asc(),
            )
        ).all()
        return [proposal_version_from_row(row) for row in rows]

    def get_latest(self, proposal_id: str) -> RecommendationProposalVersion | None:
        row = self._session.exec(
            select(RecommendationProposalVersionEntity)
            .where(RecommendationProposalVersionEntity.proposal_id == proposal_id)
            .order_by(
                RecommendationProposalVersionEntity.version_number.desc(),
                RecommendationProposalVersionEntity.created_at.desc(),
                RecommendationProposalVersionEntity.proposal_version_id.desc(),
            )
        ).first()
        return proposal_version_from_row(row) if row else None


class SQLModelInvestmentDecisionRepository(InvestmentDecisionRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, decision: InvestmentDecision) -> InvestmentDecision:
        self._session.add(decision_to_row(decision))
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError(f"decision_id already exists: {decision.decision_id}") from exc
        return decision

    def get(self, decision_id: str) -> InvestmentDecision | None:
        row = self._session.exec(
            select(InvestmentDecisionEntity).where(InvestmentDecisionEntity.decision_id == decision_id)
        ).first()
        return decision_from_row(row) if row else None

    def list_for_proposal_version(self, proposal_version_id: str) -> list[InvestmentDecision]:
        rows = self._session.exec(
            select(InvestmentDecisionEntity)
            .where(InvestmentDecisionEntity.proposal_version_id == proposal_version_id)
            .order_by(
                InvestmentDecisionEntity.decided_at.asc(),
                InvestmentDecisionEntity.decision_id.asc(),
            )
        ).all()
        return [decision_from_row(row) for row in rows]

    def get_latest_for_proposal_version(self, proposal_version_id: str) -> InvestmentDecision | None:
        row = self._session.exec(
            select(InvestmentDecisionEntity)
            .where(InvestmentDecisionEntity.proposal_version_id == proposal_version_id)
            .order_by(
                InvestmentDecisionEntity.decided_at.desc(),
                InvestmentDecisionEntity.decision_id.desc(),
            )
        ).first()
        return decision_from_row(row) if row else None


class SQLModelRecommendationTraceRepository(RecommendationTraceRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_trace(self, trace: RecommendationTrace) -> RecommendationTrace:
        self.create_trace_uncommitted(trace)
        self._session.commit()
        return trace

    def create_trace_uncommitted(self, trace: RecommendationTrace) -> RecommendationTrace:
        self._session.add(trace_to_row(trace))
        for entry in trace.entries:
            self._session.add(trace_entry_to_row(entry))
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError(
                "trace duplicate on trace_id, proposal_version_id, execution_identity, or entry sequence"
            ) from exc
        return trace

    def get_trace(self, trace_id: str) -> RecommendationTrace | None:
        trace_row = self._session.exec(
            select(RecommendationTraceEntity).where(RecommendationTraceEntity.trace_id == trace_id)
        ).first()
        if trace_row is None:
            return None
        return trace_from_row(trace_row, self.list_entries(trace_id))

    def get_trace_for_proposal_version(self, proposal_version_id: str) -> RecommendationTrace | None:
        trace_row = self._session.exec(
            select(RecommendationTraceEntity).where(
                RecommendationTraceEntity.proposal_version_id == proposal_version_id
            )
        ).first()
        if trace_row is None:
            return None
        return trace_from_row(trace_row, self.list_entries(trace_row.trace_id))

    def get_trace_for_execution_identity(self, execution_identity: str) -> RecommendationTrace | None:
        trace_row = self._session.exec(
            select(RecommendationTraceEntity).where(
                RecommendationTraceEntity.execution_identity == execution_identity
            )
        ).first()
        if trace_row is None:
            return None
        return trace_from_row(trace_row, self.list_entries(trace_row.trace_id))

    def list_entries(self, trace_id: str) -> list[TraceEntry]:
        rows = self._session.exec(
            select(RecommendationTraceEntryEntity)
            .where(RecommendationTraceEntryEntity.trace_id == trace_id)
            .order_by(
                RecommendationTraceEntryEntity.sequence_number.asc(),
                RecommendationTraceEntryEntity.entry_id.asc(),
            )
        ).all()
        return [trace_entry_from_row(row) for row in rows]

    def trace_exists_for_execution_identity(self, execution_identity: str) -> bool:
        row = self._session.exec(
            select(RecommendationTraceEntity.trace_id).where(
                RecommendationTraceEntity.execution_identity == execution_identity
            )
        ).first()
        return row is not None

    def create_claim_links(self, links: tuple[RecommendationClaimLink, ...]) -> tuple[RecommendationClaimLink, ...]:
        for row in links:
            self._session.add(claim_link_to_row(row))
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError("claim_link_id already exists") from exc
        return links

    def create_claim_links_uncommitted(
        self,
        links: tuple[RecommendationClaimLink, ...],
    ) -> tuple[RecommendationClaimLink, ...]:
        for row in links:
            self._session.add(claim_link_to_row(row))
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError("claim_link_id already exists") from exc
        return links

    def create_evidence_links(self, links: tuple[RecommendationEvidenceLink, ...]) -> tuple[RecommendationEvidenceLink, ...]:
        for row in links:
            self._session.add(evidence_link_to_row(row))
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError("evidence_link_id already exists") from exc
        return links

    def create_evidence_links_uncommitted(
        self,
        links: tuple[RecommendationEvidenceLink, ...],
    ) -> tuple[RecommendationEvidenceLink, ...]:
        for row in links:
            self._session.add(evidence_link_to_row(row))
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError("evidence_link_id already exists") from exc
        return links

    def list_claim_links(self, proposal_version_id: str) -> list[RecommendationClaimLink]:
        rows = self._session.exec(
            select(RecommendationClaimLinkEntity)
            .where(RecommendationClaimLinkEntity.proposal_version_id == proposal_version_id)
            .order_by(RecommendationClaimLinkEntity.claim_link_id.asc())
        ).all()
        return [claim_link_from_row(row) for row in rows]

    def list_evidence_links(self, proposal_version_id: str) -> list[RecommendationEvidenceLink]:
        rows = self._session.exec(
            select(RecommendationEvidenceLinkEntity)
            .where(RecommendationEvidenceLinkEntity.proposal_version_id == proposal_version_id)
            .order_by(RecommendationEvidenceLinkEntity.evidence_link_id.asc())
        ).all()
        return [evidence_link_from_row(row) for row in rows]


class SQLModelRecommendationReasonRepository(RecommendationReasonRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_many(self, reasons: tuple[RecommendationReason, ...]) -> tuple[RecommendationReason, ...]:
        for row in reasons:
            self._session.add(reason_to_row(row))
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError("reason_id already exists") from exc
        return reasons

    def create_many_uncommitted(self, reasons: tuple[RecommendationReason, ...]) -> tuple[RecommendationReason, ...]:
        for row in reasons:
            self._session.add(reason_to_row(row))
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError("reason_id already exists") from exc
        return reasons

    def list_for_proposal_version(self, proposal_version_id: str) -> list[RecommendationReason]:
        rows = self._session.exec(
            select(RecommendationReasonEntity)
            .where(RecommendationReasonEntity.proposal_version_id == proposal_version_id)
            .order_by(
                RecommendationReasonEntity.rank.asc(),
                RecommendationReasonEntity.reason_id.asc(),
            )
        ).all()
        return [reason_from_row(row) for row in rows]


class SQLModelRecommendationSnapshotRepository(RecommendationSnapshotRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, snapshot: RecommendationInputSnapshot) -> RecommendationInputSnapshot:
        self._session.add(snapshot_to_row(snapshot))
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError("snapshot_id already exists or proposal_version_id already has snapshot") from exc
        return snapshot

    def create_uncommitted(self, snapshot: RecommendationInputSnapshot) -> RecommendationInputSnapshot:
        self._session.add(snapshot_to_row(snapshot))
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError("snapshot_id already exists or proposal_version_id already has snapshot") from exc
        return snapshot

    def get(self, snapshot_id: str) -> RecommendationInputSnapshot | None:
        row = self._session.exec(
            select(RecommendationInputSnapshotEntity).where(
                RecommendationInputSnapshotEntity.snapshot_id == snapshot_id
            )
        ).first()
        return snapshot_from_row(row) if row else None

    def get_for_proposal_version(self, proposal_version_id: str) -> RecommendationInputSnapshot | None:
        row = self._session.exec(
            select(RecommendationInputSnapshotEntity).where(
                RecommendationInputSnapshotEntity.proposal_version_id == proposal_version_id
            )
        ).first()
        return snapshot_from_row(row) if row else None
