from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from piios.decision_contracts.domain.decision import InvestmentDecision
from piios.decision_contracts.domain.enums import DecisionState, Priority, ProposalStatus, ReasonType, RecommendationAction
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
    PositionSizeRange,
    RecommendationConfidenceDimensions,
    RecommendationPriority,
    ReasonWeight,
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


def _version() -> RecommendationProposalVersion:
    return RecommendationProposalVersion(
        proposal_version_id="pv1",
        proposal_id="p1",
        version_number=1,
        status=ProposalStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        snapshot_id="snap1",
        action_proposal=ActionProposal(
            action=RecommendationAction.BUY,
            position_size_range=PositionSizeRange(0.01, 0.02),
        ),
        confidence_breakdown=_confidence(),
        priority=RecommendationPriority(level=Priority.HIGH, score=0.85),
        required_human_review=True,
        supersedes_version_id=None,
    )


def test_recommendation_proposal_validation_and_immutability() -> None:
    proposal = RecommendationProposal(
        proposal_id="p1",
        target_type="SECURITY",
        target_key="NVDA",
        scope="PORTFOLIO",
        status=ProposalStatus.DRAFT,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    with pytest.raises(FrozenInstanceError):
        proposal.scope = "SECURITY"


def test_recommendation_proposal_version_requires_snapshot_and_positive_version() -> None:
    with pytest.raises(ValueError):
        RecommendationProposalVersion(
            proposal_version_id="pv1",
            proposal_id="p1",
            version_number=0,
            status=ProposalStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            snapshot_id="snap1",
            action_proposal=ActionProposal(action=RecommendationAction.BUY),
            confidence_breakdown=_confidence(),
            priority=RecommendationPriority(level=Priority.HIGH, score=0.8),
            required_human_review=True,
        )


def test_recommendation_input_snapshot_validation() -> None:
    with pytest.raises(ValueError):
        RecommendationInputSnapshot(
            snapshot_id="snap1",
            proposal_version_id="pv1",
            captured_at=datetime.now(timezone.utc),
            canonical_payload_json="",
            input_hash="hash",
        )


def test_recommendation_reason_and_trace_link_validations() -> None:
    reason = RecommendationReason(
        reason_id="r1",
        proposal_version_id="pv1",
        rank=1,
        reason_type=ReasonType.THESIS_SUPPORT,
        weight=ReasonWeight(0.9),
        reason_code="SUPPORTING_CLAIM",
        detail_json='{"claim_id":"cl1"}',
    )
    assert reason.rank == 1

    with pytest.raises(ValueError):
        RecommendationClaimLink(
            claim_link_id="clink1",
            proposal_version_id="pv1",
            claim_id="",
            contribution_weight=ReasonWeight(0.5),
            role="supporting",
        )

    with pytest.raises(ValueError):
        RecommendationEvidenceLink(
            evidence_link_id="elink1",
            proposal_version_id="pv1",
            evidence_id="ev1",
            interpretation_id=None,
            freshness_days=-1,
            quality_score=0.5,
            conflict_flag=False,
        )


def test_investment_decision_requires_modification_payload_for_modified_state() -> None:
    with pytest.raises(ValueError):
        InvestmentDecision(
            decision_id="d1",
            proposal_version_id="pv1",
            state=DecisionState.MODIFIED,
            reason_code="ADJUST_SIZE",
            decided_at=datetime.now(timezone.utc),
        )


def test_investment_decision_is_separate_from_proposal_version() -> None:
    version = _version()
    decision = InvestmentDecision(
        decision_id="d1",
        proposal_version_id=version.proposal_version_id,
        state=DecisionState.ACCEPTED,
        reason_code="ALIGNS_WITH_MANDATE",
        decided_at=datetime.now(timezone.utc),
    )

    assert decision.proposal_version_id == version.proposal_version_id
    assert decision.decision_id != version.proposal_id
