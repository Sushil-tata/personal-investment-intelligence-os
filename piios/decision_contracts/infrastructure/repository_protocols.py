from __future__ import annotations

from typing import Protocol

from piios.decision_contracts.domain.decision import InvestmentDecision
from piios.decision_contracts.domain.proposal import (
    RecommendationClaimLink,
    RecommendationEvidenceLink,
    RecommendationInputSnapshot,
    RecommendationProposal,
    RecommendationProposalVersion,
    RecommendationReason,
)


class RecommendationProposalRepositoryProtocol(Protocol):
    def create(self, proposal: RecommendationProposal) -> RecommendationProposal:
        ...

    def get(self, proposal_id: str) -> RecommendationProposal | None:
        ...


class RecommendationProposalVersionRepositoryProtocol(Protocol):
    def create(self, version: RecommendationProposalVersion) -> RecommendationProposalVersion:
        ...

    def get(self, proposal_version_id: str) -> RecommendationProposalVersion | None:
        ...

    def list_for_proposal(self, proposal_id: str) -> list[RecommendationProposalVersion]:
        ...

    def get_latest(self, proposal_id: str) -> RecommendationProposalVersion | None:
        ...


class InvestmentDecisionRepositoryProtocol(Protocol):
    def create(self, decision: InvestmentDecision) -> InvestmentDecision:
        ...

    def list_for_proposal_version(self, proposal_version_id: str) -> list[InvestmentDecision]:
        ...

    def get_latest_for_proposal_version(self, proposal_version_id: str) -> InvestmentDecision | None:
        ...


class RecommendationTraceRepositoryProtocol(Protocol):
    def create_claim_links(self, links: tuple[RecommendationClaimLink, ...]) -> tuple[RecommendationClaimLink, ...]:
        ...

    def create_evidence_links(self, links: tuple[RecommendationEvidenceLink, ...]) -> tuple[RecommendationEvidenceLink, ...]:
        ...

    def list_claim_links(self, proposal_version_id: str) -> list[RecommendationClaimLink]:
        ...

    def list_evidence_links(self, proposal_version_id: str) -> list[RecommendationEvidenceLink]:
        ...


class RecommendationReasonRepositoryProtocol(Protocol):
    def create_many(self, reasons: tuple[RecommendationReason, ...]) -> tuple[RecommendationReason, ...]:
        ...

    def list_for_proposal_version(self, proposal_version_id: str) -> list[RecommendationReason]:
        ...


class RecommendationSnapshotRepositoryProtocol(Protocol):
    def create(self, snapshot: RecommendationInputSnapshot) -> RecommendationInputSnapshot:
        ...

    def get(self, snapshot_id: str) -> RecommendationInputSnapshot | None:
        ...

    def get_for_proposal_version(self, proposal_version_id: str) -> RecommendationInputSnapshot | None:
        ...
