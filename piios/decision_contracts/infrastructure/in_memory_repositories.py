from __future__ import annotations

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


class InMemoryRecommendationProposalRepository(RecommendationProposalRepositoryProtocol):
    def __init__(self) -> None:
        self._items: dict[str, RecommendationProposal] = {}

    def create(self, proposal: RecommendationProposal) -> RecommendationProposal:
        return self.create_uncommitted(proposal)

    def create_uncommitted(self, proposal: RecommendationProposal) -> RecommendationProposal:
        if proposal.proposal_id in self._items:
            raise ValueError(f"proposal_id already exists: {proposal.proposal_id}")
        self._items[proposal.proposal_id] = proposal
        return proposal

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def get(self, proposal_id: str) -> RecommendationProposal | None:
        return self._items.get(proposal_id)


class InMemoryRecommendationProposalVersionRepository(RecommendationProposalVersionRepositoryProtocol):
    def __init__(self) -> None:
        self._by_id: dict[str, RecommendationProposalVersion] = {}
        self._by_proposal_id: dict[str, list[RecommendationProposalVersion]] = {}

    def create(self, version: RecommendationProposalVersion) -> RecommendationProposalVersion:
        return self.create_uncommitted(version)

    def create_uncommitted(self, version: RecommendationProposalVersion) -> RecommendationProposalVersion:
        if version.proposal_version_id in self._by_id:
            raise ValueError(f"proposal_version_id already exists: {version.proposal_version_id}")

        rows = self._by_proposal_id.setdefault(version.proposal_id, [])
        if any(existing.version_number == version.version_number for existing in rows):
            raise ValueError(
                f"version_number already exists for proposal_id={version.proposal_id}: {version.version_number}"
            )

        rows.append(version)
        rows.sort(key=lambda row: (row.version_number, row.created_at, row.proposal_version_id))
        self._by_id[version.proposal_version_id] = version
        return version

    def get(self, proposal_version_id: str) -> RecommendationProposalVersion | None:
        return self._by_id.get(proposal_version_id)

    def list_for_proposal(self, proposal_id: str) -> list[RecommendationProposalVersion]:
        return list(self._by_proposal_id.get(proposal_id, []))

    def get_latest(self, proposal_id: str) -> RecommendationProposalVersion | None:
        rows = self._by_proposal_id.get(proposal_id, [])
        return rows[-1] if rows else None


class InMemoryInvestmentDecisionRepository(InvestmentDecisionRepositoryProtocol):
    def __init__(self) -> None:
        self._by_id: dict[str, InvestmentDecision] = {}
        self._by_version: dict[str, list[InvestmentDecision]] = {}

    def create(self, decision: InvestmentDecision) -> InvestmentDecision:
        if decision.decision_id in self._by_id:
            raise ValueError(f"decision_id already exists: {decision.decision_id}")
        self._by_id[decision.decision_id] = decision
        rows = self._by_version.setdefault(decision.proposal_version_id, [])
        rows.append(decision)
        rows.sort(key=lambda row: (row.decided_at, row.decision_id))
        return decision

    def get(self, decision_id: str) -> InvestmentDecision | None:
        return self._by_id.get(decision_id)

    def list_for_proposal_version(self, proposal_version_id: str) -> list[InvestmentDecision]:
        return list(self._by_version.get(proposal_version_id, []))

    def get_latest_for_proposal_version(self, proposal_version_id: str) -> InvestmentDecision | None:
        rows = self._by_version.get(proposal_version_id, [])
        return rows[-1] if rows else None


class InMemoryRecommendationTraceRepository(RecommendationTraceRepositoryProtocol):
    def __init__(self) -> None:
        self._traces: dict[str, RecommendationTrace] = {}
        self._trace_by_proposal_version: dict[str, str] = {}
        self._trace_by_execution_identity: dict[str, str] = {}
        self._entries_by_trace_id: dict[str, list[TraceEntry]] = {}
        self._claim_links: dict[str, RecommendationClaimLink] = {}
        self._evidence_links: dict[str, RecommendationEvidenceLink] = {}

    def create_trace(self, trace: RecommendationTrace) -> RecommendationTrace:
        return self.create_trace_uncommitted(trace)

    def create_trace_uncommitted(self, trace: RecommendationTrace) -> RecommendationTrace:
        if trace.trace_id in self._traces:
            raise ValueError(f"trace_id already exists: {trace.trace_id}")
        if trace.proposal_version_id in self._trace_by_proposal_version:
            raise ValueError(
                f"proposal_version_id already has authoritative trace: {trace.proposal_version_id}"
            )
        if trace.execution_identity in self._trace_by_execution_identity:
            raise ValueError(f"execution_identity already exists: {trace.execution_identity}")

        self._traces[trace.trace_id] = trace
        self._trace_by_proposal_version[trace.proposal_version_id] = trace.trace_id
        self._trace_by_execution_identity[trace.execution_identity] = trace.trace_id
        self._entries_by_trace_id[trace.trace_id] = list(trace.entries)
        return trace

    def get_trace(self, trace_id: str) -> RecommendationTrace | None:
        return self._traces.get(trace_id)

    def get_trace_for_proposal_version(self, proposal_version_id: str) -> RecommendationTrace | None:
        trace_id = self._trace_by_proposal_version.get(proposal_version_id)
        if trace_id is None:
            return None
        return self._traces.get(trace_id)

    def get_trace_for_execution_identity(self, execution_identity: str) -> RecommendationTrace | None:
        trace_id = self._trace_by_execution_identity.get(execution_identity)
        if trace_id is None:
            return None
        return self._traces.get(trace_id)

    def list_entries(self, trace_id: str) -> list[TraceEntry]:
        rows = list(self._entries_by_trace_id.get(trace_id, []))
        rows.sort(key=lambda row: (row.sequence_number, row.entry_id))
        return rows

    def trace_exists_for_execution_identity(self, execution_identity: str) -> bool:
        return execution_identity in self._trace_by_execution_identity

    def create_claim_links(self, links: tuple[RecommendationClaimLink, ...]) -> tuple[RecommendationClaimLink, ...]:
        return self.create_claim_links_uncommitted(links)

    def create_claim_links_uncommitted(
        self,
        links: tuple[RecommendationClaimLink, ...],
    ) -> tuple[RecommendationClaimLink, ...]:
        for row in links:
            if row.claim_link_id in self._claim_links:
                raise ValueError(f"claim_link_id already exists: {row.claim_link_id}")
            self._claim_links[row.claim_link_id] = row
        return links

    def create_evidence_links(self, links: tuple[RecommendationEvidenceLink, ...]) -> tuple[RecommendationEvidenceLink, ...]:
        return self.create_evidence_links_uncommitted(links)

    def create_evidence_links_uncommitted(
        self,
        links: tuple[RecommendationEvidenceLink, ...],
    ) -> tuple[RecommendationEvidenceLink, ...]:
        for row in links:
            if row.evidence_link_id in self._evidence_links:
                raise ValueError(f"evidence_link_id already exists: {row.evidence_link_id}")
            self._evidence_links[row.evidence_link_id] = row
        return links

    def list_claim_links(self, proposal_version_id: str) -> list[RecommendationClaimLink]:
        rows = [row for row in self._claim_links.values() if row.proposal_version_id == proposal_version_id]
        rows.sort(key=lambda row: row.claim_link_id)
        return rows

    def list_evidence_links(self, proposal_version_id: str) -> list[RecommendationEvidenceLink]:
        rows = [row for row in self._evidence_links.values() if row.proposal_version_id == proposal_version_id]
        rows.sort(key=lambda row: row.evidence_link_id)
        return rows


class InMemoryRecommendationReasonRepository(RecommendationReasonRepositoryProtocol):
    def __init__(self) -> None:
        self._items: dict[str, RecommendationReason] = {}

    def create_many(self, reasons: tuple[RecommendationReason, ...]) -> tuple[RecommendationReason, ...]:
        return self.create_many_uncommitted(reasons)

    def create_many_uncommitted(self, reasons: tuple[RecommendationReason, ...]) -> tuple[RecommendationReason, ...]:
        for row in reasons:
            if row.reason_id in self._items:
                raise ValueError(f"reason_id already exists: {row.reason_id}")
            self._items[row.reason_id] = row
        return reasons

    def list_for_proposal_version(self, proposal_version_id: str) -> list[RecommendationReason]:
        rows = [row for row in self._items.values() if row.proposal_version_id == proposal_version_id]
        rows.sort(key=lambda row: (row.rank, row.reason_id))
        return rows


class InMemoryRecommendationSnapshotRepository(RecommendationSnapshotRepositoryProtocol):
    def __init__(self) -> None:
        self._by_snapshot_id: dict[str, RecommendationInputSnapshot] = {}
        self._by_version_id: dict[str, RecommendationInputSnapshot] = {}

    def create(self, snapshot: RecommendationInputSnapshot) -> RecommendationInputSnapshot:
        return self.create_uncommitted(snapshot)

    def create_uncommitted(self, snapshot: RecommendationInputSnapshot) -> RecommendationInputSnapshot:
        if snapshot.snapshot_id in self._by_snapshot_id:
            raise ValueError(f"snapshot_id already exists: {snapshot.snapshot_id}")
        if snapshot.proposal_version_id in self._by_version_id:
            raise ValueError(
                f"proposal_version_id already has a snapshot: {snapshot.proposal_version_id}"
            )
        self._by_snapshot_id[snapshot.snapshot_id] = snapshot
        self._by_version_id[snapshot.proposal_version_id] = snapshot
        return snapshot

    def get(self, snapshot_id: str) -> RecommendationInputSnapshot | None:
        return self._by_snapshot_id.get(snapshot_id)

    def get_for_proposal_version(self, proposal_version_id: str) -> RecommendationInputSnapshot | None:
        return self._by_version_id.get(proposal_version_id)
