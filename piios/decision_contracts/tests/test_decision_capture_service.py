from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from piios.decision_contracts.application.decision_capture_service import (
    DecisionCaptureRequest,
    DecisionCaptureService,
    DecisionPersistenceError,
    DecisionType,
    InvalidDecisionPayloadError,
    RepositoryAccessError,
    UnknownProposalError,
    UnknownProposalVersionError,
)
from piios.decision_contracts.domain.decision import InvestmentDecision
from piios.decision_contracts.domain.enums import DecisionState, Priority, ProposalStatus, RecommendationAction
from piios.decision_contracts.domain.proposal import RecommendationProposal, RecommendationProposalVersion
from piios.decision_contracts.domain.value_objects import (
    ActionProposal,
    ConfidenceBreakdown,
    RecommendationConfidenceDimensions,
    RecommendationPriority,
)
from piios.decision_contracts.infrastructure.in_memory_repositories import (
    InMemoryInvestmentDecisionRepository,
    InMemoryRecommendationProposalRepository,
    InMemoryRecommendationProposalVersionRepository,
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


def _version(version_id: str = "pv1", proposal_id: str = "p1") -> RecommendationProposalVersion:
    return RecommendationProposalVersion(
        proposal_version_id=version_id,
        proposal_id=proposal_id,
        version_number=1,
        status=ProposalStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        snapshot_id=f"snap-{version_id}",
        action_proposal=ActionProposal(action=RecommendationAction.BUY),
        confidence_breakdown=_confidence(),
        priority=RecommendationPriority(level=Priority.HIGH, score=0.8),
        required_human_review=True,
    )


def _service_with_seeded_repos() -> tuple[
    DecisionCaptureService,
    InMemoryRecommendationProposalRepository,
    InMemoryRecommendationProposalVersionRepository,
    InMemoryInvestmentDecisionRepository,
]:
    proposal_repo = InMemoryRecommendationProposalRepository()
    version_repo = InMemoryRecommendationProposalVersionRepository()
    decision_repo = InMemoryInvestmentDecisionRepository()

    proposal_repo.create(_proposal("p1"))
    version_repo.create(_version("pv1", "p1"))

    service = DecisionCaptureService(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        decision_repository=decision_repo,
    )
    return service, proposal_repo, version_repo, decision_repo


@pytest.mark.parametrize(
    ("decision_type", "expected_state", "kwargs"),
    [
        (DecisionType.ACCEPT, DecisionState.ACCEPTED, {"reason_code": "APPROVED"}),
        (DecisionType.REJECT, DecisionState.REJECTED, {"reason_code": "RISK_HIGH"}),
        (
            DecisionType.MODIFIED,
            DecisionState.MODIFIED,
            {
                "reason_code": "ADJUST_SIZE",
                "modified_action": RecommendationAction.HOLD,
                "modified_action_min_weight": 0.01,
                "modified_action_max_weight": 0.03,
            },
        ),
        (
            DecisionType.OVERRIDDEN,
            DecisionState.OVERRIDDEN,
            {
                "reason_code": "ALTERNATIVE_BETTER",
                "preferred_alternative_target_key": "AMD",
            },
        ),
        (DecisionType.DEFERRED, DecisionState.DEFERRED, {"reason_code": "WAIT_FOR_EVENT"}),
        (
            DecisionType.REQUEST_RESEARCH,
            DecisionState.DEFERRED,
            {"reason_text": "Need counter-evidence"},
        ),
    ],
)
def test_capture_happy_path_by_decision_type(decision_type, expected_state, kwargs) -> None:
    service, _, _, decision_repo = _service_with_seeded_repos()

    request = DecisionCaptureRequest(
        proposal_version_id="pv1",
        decision_type=decision_type,
        reviewer="rm_001",
        client_request_id=f"req-{decision_type.value.lower()}",
        **kwargs,
    )
    decision = service.capture(request)

    assert decision.state == expected_state
    assert decision.proposal_version_id == "pv1"
    assert decision.decided_by == "rm_001"
    assert decision_repo.get(decision.decision_id) == decision

    if decision_type == DecisionType.REQUEST_RESEARCH:
        assert decision.reason_code == "REQUEST_RESEARCH"


def test_capture_idempotency_identical_request_returns_existing_without_duplicate() -> None:
    service, _, _, decision_repo = _service_with_seeded_repos()

    request = DecisionCaptureRequest(
        proposal_version_id="pv1",
        decision_type=DecisionType.ACCEPT,
        reviewer="rm_001",
        reason_code="APPROVED",
        client_request_id="req-1",
    )

    first = service.capture(request)
    second = service.capture(request)

    assert first == second
    assert first.decision_id == second.decision_id
    assert len(decision_repo.list_for_proposal_version("pv1")) == 1


def test_capture_idempotency_different_request_creates_new_immutable_decision() -> None:
    service, _, _, decision_repo = _service_with_seeded_repos()

    first = service.capture(
        DecisionCaptureRequest(
            proposal_version_id="pv1",
            decision_type=DecisionType.DEFERRED,
            reviewer="rm_001",
            reason_code="WAIT_FOR_EVENT",
            client_request_id="req-1",
        )
    )
    second = service.capture(
        DecisionCaptureRequest(
            proposal_version_id="pv1",
            decision_type=DecisionType.REQUEST_RESEARCH,
            reviewer="rm_001",
            reason_text="Need additional data",
            client_request_id="req-2",
        )
    )

    assert first.decision_id != second.decision_id
    assert len(decision_repo.list_for_proposal_version("pv1")) == 2


def test_capture_unknown_proposal_version_rejected() -> None:
    service, _, _, _ = _service_with_seeded_repos()

    with pytest.raises(UnknownProposalVersionError):
        service.capture(
            DecisionCaptureRequest(
                proposal_version_id="missing",
                decision_type=DecisionType.ACCEPT,
                reviewer="rm_001",
                reason_code="APPROVED",
            )
        )


def test_capture_unknown_proposal_rejected_for_orphan_version() -> None:
    proposal_repo = InMemoryRecommendationProposalRepository()
    version_repo = InMemoryRecommendationProposalVersionRepository()
    decision_repo = InMemoryInvestmentDecisionRepository()

    version_repo.create(_version("pv1", "missing-proposal"))
    service = DecisionCaptureService(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        decision_repository=decision_repo,
    )

    with pytest.raises(UnknownProposalError):
        service.capture(
            DecisionCaptureRequest(
                proposal_version_id="pv1",
                decision_type=DecisionType.ACCEPT,
                reviewer="rm_001",
                reason_code="APPROVED",
            )
        )


def test_capture_invalid_payload_rejected() -> None:
    service, _, _, _ = _service_with_seeded_repos()

    with pytest.raises(InvalidDecisionPayloadError):
        service.capture(
            DecisionCaptureRequest(
                proposal_version_id="pv1",
                decision_type=DecisionType.ACCEPT,
                reviewer=" ",
                reason_code="APPROVED",
            )
        )

    with pytest.raises(InvalidDecisionPayloadError):
        service.capture(
            DecisionCaptureRequest(
                proposal_version_id="pv1",
                decision_type=DecisionType.MODIFIED,
                reviewer="rm_001",
                reason_code="ADJUST_SIZE",
                modified_action_min_weight=0.01,
                modified_action_max_weight=0.03,
            )
        )


def test_capture_invariant_violation_is_propagated() -> None:
    service, _, _, _ = _service_with_seeded_repos()

    with pytest.raises(ValueError):
        service.capture(
            DecisionCaptureRequest(
                proposal_version_id="pv1",
                decision_type=DecisionType.OVERRIDDEN,
                reviewer="rm_001",
                reason_code="ALTERNATIVE_BETTER",
            )
        )


def test_capture_repository_read_failure_is_wrapped() -> None:
    service, _, version_repo, decision_repo = _service_with_seeded_repos()

    class FailingProposalRepo:
        def get(self, proposal_id: str):
            raise RuntimeError("db unavailable")

    failing_service = DecisionCaptureService(
        proposal_repository=FailingProposalRepo(),
        version_repository=version_repo,
        decision_repository=decision_repo,
    )

    with pytest.raises(RepositoryAccessError):
        failing_service.capture(
            DecisionCaptureRequest(
                proposal_version_id="pv1",
                decision_type=DecisionType.ACCEPT,
                reviewer="rm_001",
                reason_code="APPROVED",
            )
        )


@dataclass
class _SpyProposalRepo:
    proposal: RecommendationProposal | None
    calls: list[str]

    def get(self, proposal_id: str):
        self.calls.append(f"proposal.get:{proposal_id}")
        return self.proposal


@dataclass
class _SpyVersionRepo:
    version: RecommendationProposalVersion | None
    calls: list[str]

    def get(self, proposal_version_id: str):
        self.calls.append(f"version.get:{proposal_version_id}")
        return self.version


class _SpyDecisionRepo:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.by_id: dict[str, InvestmentDecision] = {}
        self.by_version: dict[str, list[InvestmentDecision]] = {}

    def get(self, decision_id: str):
        self.calls.append(f"decision.get:{decision_id}")
        return self.by_id.get(decision_id)

    def create(self, decision: InvestmentDecision):
        self.calls.append(f"decision.create:{decision.decision_id}")
        self.by_id[decision.decision_id] = decision
        self.by_version.setdefault(decision.proposal_version_id, []).append(decision)
        return decision

    def list_for_proposal_version(self, proposal_version_id: str):
        return list(self.by_version.get(proposal_version_id, []))


def test_capture_repository_interactions_are_repository_only() -> None:
    calls: list[str] = []
    proposal = _proposal("p1")
    version = _version("pv1", "p1")
    proposal_repo = _SpyProposalRepo(proposal=proposal, calls=calls)
    version_repo = _SpyVersionRepo(version=version, calls=calls)
    decision_repo = _SpyDecisionRepo()

    service = DecisionCaptureService(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        decision_repository=decision_repo,
    )
    result = service.capture(
        DecisionCaptureRequest(
            proposal_version_id="pv1",
            decision_type=DecisionType.ACCEPT,
            reviewer="rm_001",
            reason_code="APPROVED",
            client_request_id="req-1",
        )
    )

    assert result.proposal_version_id == "pv1"
    assert calls == ["version.get:pv1", "proposal.get:p1"]
    assert len([row for row in decision_repo.calls if row.startswith("decision.get:")]) == 1
    assert len([row for row in decision_repo.calls if row.startswith("decision.create:")]) == 1


def test_capture_persistence_failure_has_no_partial_storage() -> None:
    proposal = _proposal("p1")
    version = _version("pv1", "p1")

    class FailingDecisionRepo(_SpyDecisionRepo):
        def create(self, decision: InvestmentDecision):
            self.calls.append(f"decision.create:{decision.decision_id}")
            raise RuntimeError("insert failed")

    decision_repo = FailingDecisionRepo()
    service = DecisionCaptureService(
        proposal_repository=_SpyProposalRepo(proposal=proposal, calls=[]),
        version_repository=_SpyVersionRepo(version=version, calls=[]),
        decision_repository=decision_repo,
    )

    with pytest.raises(DecisionPersistenceError):
        service.capture(
            DecisionCaptureRequest(
                proposal_version_id="pv1",
                decision_type=DecisionType.ACCEPT,
                reviewer="rm_001",
                reason_code="APPROVED",
                client_request_id="req-1",
            )
        )

    assert decision_repo.list_for_proposal_version("pv1") == []
