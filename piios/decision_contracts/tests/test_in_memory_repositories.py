from __future__ import annotations

from datetime import datetime, timezone

import pytest

from piios.decision_contracts.domain.decision import InvestmentDecision
from piios.decision_contracts.domain.enums import (
    DecisionState,
    Priority,
    ProposalStatus,
    ReasonType,
    RecommendationAction,
)
from piios.decision_contracts.domain.proposal import (
    RecommendationClaimLink,
    RecommendationEvidenceLink,
    RecommendationInputSnapshot,
    RecommendationProposal,
    RecommendationProposalVersion,
    RecommendationReason,
)
from piios.decision_contracts.domain.value_objects import (
    ActionProposal,
    ConfidenceBreakdown,
    RecommendationConfidenceDimensions,
    RecommendationPriority,
    ReasonWeight,
)
from piios.decision_contracts.infrastructure.in_memory_repositories import (
    InMemoryInvestmentDecisionRepository,
    InMemoryRecommendationProposalRepository,
    InMemoryRecommendationProposalVersionRepository,
    InMemoryRecommendationReasonRepository,
    InMemoryRecommendationSnapshotRepository,
    InMemoryRecommendationTraceRepository,
)


def _confidence() -> ConfidenceBreakdown:
    return ConfidenceBreakdown(
        dimensions=RecommendationConfidenceDimensions(
            company_quality=0.8,
            valuation_attractiveness=0.7,
            portfolio_suitability=0.6,
            recommendation_confidence=0.65,
            relationship_confidence=0.55,
            expected_return=0.5,
        ),
        overall_confidence=0.64,
    )


def _proposal(proposal_id: str = "p1") -> RecommendationProposal:
    now = datetime.now(timezone.utc)
    return RecommendationProposal(
        proposal_id=proposal_id,
        target_type="SECURITY",
        target_key="NVDA",
        scope="PORTFOLIO",
        status=ProposalStatus.DRAFT,
        created_at=now,
        updated_at=now,
    )


def _version(version_id: str, proposal_id: str, version_number: int) -> RecommendationProposalVersion:
    return RecommendationProposalVersion(
        proposal_version_id=version_id,
        proposal_id=proposal_id,
        version_number=version_number,
        status=ProposalStatus.ACTIVE,
        created_at=datetime(2026, 7, 27, 10, 0, version_number, tzinfo=timezone.utc),
        snapshot_id=f"snap-{version_id}",
        action_proposal=ActionProposal(action=RecommendationAction.BUY),
        confidence_breakdown=_confidence(),
        priority=RecommendationPriority(level=Priority.HIGH, score=0.8),
        required_human_review=True,
    )


def test_in_memory_proposal_repository_create_and_duplicate_guard() -> None:
    repo = InMemoryRecommendationProposalRepository()
    item = _proposal("p1")
    repo.create(item)
    assert repo.get("p1") == item
    with pytest.raises(ValueError):
        repo.create(item)


def test_in_memory_version_repository_append_only_latest_and_unique_version_number() -> None:
    repo = InMemoryRecommendationProposalVersionRepository()
    v1 = _version("pv1", "p1", 1)
    v2 = _version("pv2", "p1", 2)

    repo.create(v2)
    repo.create(v1)
    rows = repo.list_for_proposal("p1")
    assert [row.version_number for row in rows] == [1, 2]
    assert repo.get_latest("p1") == v2

    with pytest.raises(ValueError):
        repo.create(_version("pv3", "p1", 2))


def test_in_memory_snapshot_repository_enforces_one_snapshot_per_version() -> None:
    repo = InMemoryRecommendationSnapshotRepository()
    snap1 = RecommendationInputSnapshot(
        snapshot_id="s1",
        proposal_version_id="pv1",
        captured_at=datetime.now(timezone.utc),
        canonical_payload_json='{"ticker":"NVDA"}',
        input_hash="hash1",
    )
    repo.create(snap1)
    assert repo.get("s1") == snap1
    assert repo.get_for_proposal_version("pv1") == snap1

    with pytest.raises(ValueError):
        repo.create(
            RecommendationInputSnapshot(
                snapshot_id="s2",
                proposal_version_id="pv1",
                captured_at=datetime.now(timezone.utc),
                canonical_payload_json='{"ticker":"NVDA"}',
                input_hash="hash2",
            )
        )


def test_in_memory_reason_repository_returns_stable_ordering() -> None:
    repo = InMemoryRecommendationReasonRepository()
    repo.create_many(
        (
            RecommendationReason(
                reason_id="r2",
                proposal_version_id="pv1",
                rank=2,
                reason_type=ReasonType.RISK_CONTROL,
                weight=ReasonWeight(0.5),
                reason_code="RISK",
                detail_json="{}",
            ),
            RecommendationReason(
                reason_id="r1",
                proposal_version_id="pv1",
                rank=1,
                reason_type=ReasonType.THESIS_SUPPORT,
                weight=ReasonWeight(0.8),
                reason_code="THESIS",
                detail_json="{}",
            ),
        )
    )

    ordered = repo.list_for_proposal_version("pv1")
    assert [row.reason_id for row in ordered] == ["r1", "r2"]


def test_in_memory_trace_repository_claim_and_evidence_links() -> None:
    repo = InMemoryRecommendationTraceRepository()
    claim_link = RecommendationClaimLink(
        claim_link_id="cl1",
        proposal_version_id="pv1",
        claim_id="claim-1",
        contribution_weight=ReasonWeight(0.7),
        role="supporting",
    )
    evidence_link = RecommendationEvidenceLink(
        evidence_link_id="ev1",
        proposal_version_id="pv1",
        evidence_id="evidence-1",
        interpretation_id="interp-1",
        freshness_days=5,
        quality_score=0.9,
        conflict_flag=False,
    )

    repo.create_claim_links((claim_link,))
    repo.create_evidence_links((evidence_link,))

    assert repo.list_claim_links("pv1") == [claim_link]
    assert repo.list_evidence_links("pv1") == [evidence_link]


def test_in_memory_decision_repository_history_and_latest() -> None:
    repo = InMemoryInvestmentDecisionRepository()
    first = InvestmentDecision(
        decision_id="d1",
        proposal_version_id="pv1",
        state=DecisionState.DEFERRED,
        reason_code="NEED_MORE_DATA",
        decided_at=datetime(2026, 7, 27, 10, 0, 0, tzinfo=timezone.utc),
    )
    second = InvestmentDecision(
        decision_id="d2",
        proposal_version_id="pv1",
        state=DecisionState.ACCEPTED,
        reason_code="CONFIRMED",
        decided_at=datetime(2026, 7, 27, 10, 1, 0, tzinfo=timezone.utc),
    )

    repo.create(second)
    repo.create(first)

    history = repo.list_for_proposal_version("pv1")
    assert [row.decision_id for row in history] == ["d1", "d2"]
    assert repo.get_latest_for_proposal_version("pv1") == second


def test_in_memory_repositories_reject_duplicate_ids() -> None:
    reasons = InMemoryRecommendationReasonRepository()
    reason = RecommendationReason(
        reason_id="r1",
        proposal_version_id="pv1",
        rank=1,
        reason_type=ReasonType.THESIS_SUPPORT,
        weight=ReasonWeight(0.8),
        reason_code="THESIS",
        detail_json="{}",
    )
    reasons.create_many((reason,))
    with pytest.raises(ValueError):
        reasons.create_many((reason,))
