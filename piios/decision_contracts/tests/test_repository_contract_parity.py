from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlmodel import SQLModel, Session, create_engine

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
from piios.decision_contracts.infrastructure.sqlmodel_repositories import (
    SQLModelInvestmentDecisionRepository,
    SQLModelRecommendationProposalRepository,
    SQLModelRecommendationProposalVersionRepository,
    SQLModelRecommendationReasonRepository,
    SQLModelRecommendationSnapshotRepository,
    SQLModelRecommendationTraceRepository,
)
from piios.decision_contracts.infrastructure import sqlmodel_entities as decision_sqlmodel_entities  # noqa: F401
from piios.thesis_health.infrastructure import sqlmodel_entities as thesis_health_sqlmodel_entities  # noqa: F401
from piios_backend.models import entities as backend_entities  # noqa: F401


@pytest.fixture(params=["in_memory", "sqlmodel"])
def repo_bundle(request, tmp_path):
    if request.param == "in_memory":
        return {
            "proposal": InMemoryRecommendationProposalRepository(),
            "version": InMemoryRecommendationProposalVersionRepository(),
            "snapshot": InMemoryRecommendationSnapshotRepository(),
            "reason": InMemoryRecommendationReasonRepository(),
            "trace": InMemoryRecommendationTraceRepository(),
            "decision": InMemoryInvestmentDecisionRepository(),
        }

    db_path = tmp_path / "decision_contract_repo.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    request.addfinalizer(session.close)
    return {
        "proposal": SQLModelRecommendationProposalRepository(session),
        "version": SQLModelRecommendationProposalVersionRepository(session),
        "snapshot": SQLModelRecommendationSnapshotRepository(session),
        "reason": SQLModelRecommendationReasonRepository(session),
        "trace": SQLModelRecommendationTraceRepository(session),
        "decision": SQLModelInvestmentDecisionRepository(session),
    }


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


def test_contract_proposal_version_snapshot_and_decision_flow(repo_bundle) -> None:
    proposal_repo = repo_bundle["proposal"]
    version_repo = repo_bundle["version"]
    snapshot_repo = repo_bundle["snapshot"]
    decision_repo = repo_bundle["decision"]

    proposal_repo.create(_proposal("p1"))
    v1 = _version("pv1", "p1", 1)
    v2 = _version("pv2", "p1", 2)
    version_repo.create(v1)
    version_repo.create(v2)

    rows = version_repo.list_for_proposal("p1")
    assert [row.version_number for row in rows] == [1, 2]
    assert version_repo.get_latest("p1").proposal_version_id == "pv2"

    snap = RecommendationInputSnapshot(
        snapshot_id="s1",
        proposal_version_id="pv1",
        captured_at=datetime.now(timezone.utc),
        canonical_payload_json='{"ticker":"NVDA"}',
        input_hash="hash1",
    )
    snapshot_repo.create(snap)
    assert snapshot_repo.get("s1") == snap
    assert snapshot_repo.get_for_proposal_version("pv1") == snap

    d1 = InvestmentDecision(
        decision_id="d1",
        proposal_version_id="pv1",
        state=DecisionState.DEFERRED,
        reason_code="NEED_MORE_DATA",
        decided_at=datetime(2026, 7, 27, 10, 0, 0, tzinfo=timezone.utc),
    )
    d2 = InvestmentDecision(
        decision_id="d2",
        proposal_version_id="pv1",
        state=DecisionState.ACCEPTED,
        reason_code="CONFIRMED",
        decided_at=datetime(2026, 7, 27, 10, 1, 0, tzinfo=timezone.utc),
    )
    decision_repo.create(d2)
    decision_repo.create(d1)
    decision_rows = decision_repo.list_for_proposal_version("pv1")
    assert [row.decision_id for row in decision_rows] == ["d1", "d2"]
    assert decision_repo.get_latest_for_proposal_version("pv1").decision_id == "d2"


def test_contract_duplicate_guards(repo_bundle) -> None:
    proposal_repo = repo_bundle["proposal"]
    version_repo = repo_bundle["version"]
    snapshot_repo = repo_bundle["snapshot"]
    reason_repo = repo_bundle["reason"]
    trace_repo = repo_bundle["trace"]

    proposal_repo.create(_proposal("p1"))
    with pytest.raises(ValueError):
        proposal_repo.create(_proposal("p1"))

    version_repo.create(_version("pv1", "p1", 1))
    with pytest.raises(ValueError):
        version_repo.create(_version("pv1", "p1", 2))

    snapshot = RecommendationInputSnapshot(
        snapshot_id="s1",
        proposal_version_id="pv1",
        captured_at=datetime.now(timezone.utc),
        canonical_payload_json='{"ticker":"NVDA"}',
        input_hash="hash1",
    )
    snapshot_repo.create(snapshot)
    with pytest.raises(ValueError):
        snapshot_repo.create(snapshot)

    reason = RecommendationReason(
        reason_id="r1",
        proposal_version_id="pv1",
        rank=1,
        reason_type=ReasonType.THESIS_SUPPORT,
        weight=ReasonWeight(0.8),
        reason_code="THESIS",
        detail_json="{}",
    )
    reason_repo.create_many((reason,))
    with pytest.raises(ValueError):
        reason_repo.create_many((reason,))

    claim_link = RecommendationClaimLink(
        claim_link_id="cl1",
        proposal_version_id="pv1",
        claim_id="claim-1",
        contribution_weight=ReasonWeight(0.7),
        role="supporting",
    )
    trace_repo.create_claim_links((claim_link,))
    with pytest.raises(ValueError):
        trace_repo.create_claim_links((claim_link,))


def test_contract_ordering_for_reason_and_trace(repo_bundle) -> None:
    proposal_repo = repo_bundle["proposal"]
    version_repo = repo_bundle["version"]
    reason_repo = repo_bundle["reason"]
    trace_repo = repo_bundle["trace"]

    proposal_repo.create(_proposal("p1"))
    version_repo.create(_version("pv1", "p1", 1))

    reason_repo.create_many(
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
    assert [row.reason_id for row in reason_repo.list_for_proposal_version("pv1")] == ["r1", "r2"]

    trace_repo.create_evidence_links(
        (
            RecommendationEvidenceLink(
                evidence_link_id="ev2",
                proposal_version_id="pv1",
                evidence_id="evidence-2",
                interpretation_id=None,
                freshness_days=8,
                quality_score=0.6,
                conflict_flag=True,
            ),
            RecommendationEvidenceLink(
                evidence_link_id="ev1",
                proposal_version_id="pv1",
                evidence_id="evidence-1",
                interpretation_id=None,
                freshness_days=5,
                quality_score=0.9,
                conflict_flag=False,
            ),
        )
    )
    assert [row.evidence_link_id for row in trace_repo.list_evidence_links("pv1")] == ["ev1", "ev2"]
