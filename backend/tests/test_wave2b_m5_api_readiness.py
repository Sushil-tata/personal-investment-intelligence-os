from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from piios.decision_contracts.application.decision_capture_service import DecisionType
from piios.decision_contracts.application.decision_query_service import (
    DecisionDetail,
    RecommendationProposalDetail,
    RecommendationProposalVersionDetail,
)
from piios.decision_contracts.application.diagnostics_service import (
    ConfidenceComponent,
    ConfidenceDiagnostic,
    DecisionLineageDiagnostic,
    DiagnosticCheck,
    DiagnosticSeverity,
    DiagnosticStatus,
    GovernanceReviewBacklog,
    GovernanceReviewItem,
    TraceabilityDiagnostic,
)
from piios_backend.api.routes.decision_contracts import get_decision_contracts_service
from piios_backend.main import app


@dataclass
class _FakeQueryService:
    def get_recommendation_proposal_detail(self, proposal_id: str):
        return RecommendationProposalDetail(
            proposal_id=proposal_id,
            target_type="SECURITY",
            target_key="NVDA",
            scope="PORTFOLIO",
            status="ACTIVE",
            created_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
            updated_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
        )

    def get_proposal_version_detail(self, proposal_version_id: str):
        return RecommendationProposalVersionDetail(
            proposal_version_id=proposal_version_id,
            proposal_id="p1",
            version_number=1,
            status="ACTIVE",
            created_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
            snapshot_id="snap1",
            action="BUY",
            action_note=None,
            action_min_weight=0.01,
            action_max_weight=0.03,
            authoritative_confidence=0.8,
            priority_level="HIGH",
            priority_score=0.9,
            required_human_review=True,
            supersedes_version_id=None,
        )

    def list_decisions_for_proposal_version(self, proposal_version_id: str):
        return (
            DecisionDetail(
                decision_id="decision:pv1:1",
                proposal_version_id=proposal_version_id,
                state="DEFERRED",
                decision_meaning="REQUEST_RESEARCH",
                reason_code="REQUEST_RESEARCH",
                reason_text=None,
                decided_by="rm_001",
                decided_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
                preferred_alternative_target_key=None,
                modified_action=None,
                modified_action_note=None,
                modified_action_min_weight=None,
                modified_action_max_weight=None,
                modified_position_min_weight=None,
                modified_position_max_weight=None,
            ),
        )

    def get_latest_decision_for_proposal_version(self, proposal_version_id: str):
        return self.list_decisions_for_proposal_version(proposal_version_id)[0]

    def get_traceability_diagnostic(self, proposal_version_id: str):
        return TraceabilityDiagnostic(
            proposal_id="p1",
            proposal_version_id=proposal_version_id,
            overall_status=DiagnosticStatus.PASS,
            checks=(
                DiagnosticCheck(
                    code="PROPOSAL_EXISTS",
                    status=DiagnosticStatus.PASS,
                    severity=DiagnosticSeverity.INFO,
                    message="ok",
                    related_entity_type="proposal",
                    related_entity_id="p1",
                ),
            ),
            diagnostic_codes=("PROPOSAL_EXISTS",),
            severity=DiagnosticSeverity.INFO,
            generated_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
        )

    def get_confidence_diagnostic(self, proposal_version_id: str):
        return ConfidenceDiagnostic(
            proposal_version_id=proposal_version_id,
            authoritative_confidence=0.8,
            components=(
                ConfidenceComponent(
                    name="model_rule_confidence",
                    value=0.8,
                    status=DiagnosticStatus.PASS,
                    source="proposal_version",
                    explanation="ok",
                ),
            ),
            limitations=tuple(),
            generated_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
        )

    def get_decision_lineage_diagnostic(self, decision_id: str):
        return DecisionLineageDiagnostic(
            decision_id=decision_id,
            proposal_id="p1",
            proposal_version_id="pv1",
            decision_state="DEFERRED",
            decision_meaning="REQUEST_RESEARCH",
            overall_status=DiagnosticStatus.PASS,
            checks=(
                DiagnosticCheck(
                    code="REQUEST_RESEARCH_DISTINGUISHABLE",
                    status=DiagnosticStatus.PASS,
                    severity=DiagnosticSeverity.INFO,
                    message="ok",
                    related_entity_type="decision",
                    related_entity_id=decision_id,
                ),
            ),
            diagnostic_codes=("REQUEST_RESEARCH_DISTINGUISHABLE",),
            severity=DiagnosticSeverity.INFO,
            generated_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
        )

    def get_governance_review_backlog(self, proposal_version_id: str):
        return GovernanceReviewBacklog(
            proposal_version_id=proposal_version_id,
            items=(
                GovernanceReviewItem(
                    review_item_id="review:pv1:1",
                    proposal_id="p1",
                    proposal_version_id=proposal_version_id,
                    decision_id="decision:pv1:1",
                    reason_code="REQUEST_RESEARCH_DECISION",
                    severity=DiagnosticSeverity.HIGH,
                    status="OPEN",
                    created_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
                    source_diagnostic="decision_lineage",
                    summary="research requested",
                ),
            ),
            generated_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
        )


@dataclass
class _FakeDecisionContractsService:
    query_service: _FakeQueryService

    def capture_decision(self, request):
        return self.query_service.list_decisions_for_proposal_version(request.proposal_version_id)[0]


client = TestClient(app)


def test_wave2b_m5_decision_contract_routes_contract_shape() -> None:
    fake = _FakeDecisionContractsService(query_service=_FakeQueryService())
    app.dependency_overrides[get_decision_contracts_service] = lambda: fake
    try:
        assert client.get("/api/v1/decision-contracts/health").status_code == 200

        proposal = client.get("/api/v1/decision-contracts/proposals/p1")
        assert proposal.status_code == 200
        assert proposal.json()["advisory_only"] is True

        version = client.get("/api/v1/decision-contracts/proposal-versions/pv1")
        assert version.status_code == 200

        capture = client.post(
            "/api/v1/decision-contracts/decisions/capture",
            json={
                "proposal_version_id": "pv1",
                "decision_type": DecisionType.REQUEST_RESEARCH.value,
                "reviewer": "rm_001",
                "client_request_id": "req-1",
            },
        )
        assert capture.status_code == 200
        assert capture.json()["decision_meaning"] == "REQUEST_RESEARCH"

        backlog = client.get("/api/v1/decision-contracts/proposal-versions/pv1/governance-backlog")
        assert backlog.status_code == 200
        assert backlog.json()["items"][0]["reason_code"] == "REQUEST_RESEARCH_DECISION"

        trace = client.get("/api/v1/decision-contracts/proposal-versions/pv1/diagnostics/traceability")
        assert trace.status_code == 200
        assert trace.json()["checks"][0]["status"] == "PASS"

        confidence = client.get("/api/v1/decision-contracts/proposal-versions/pv1/diagnostics/confidence")
        assert confidence.status_code == 200
        assert confidence.json()["components"][0]["name"] == "model_rule_confidence"

        lineage = client.get("/api/v1/decision-contracts/decisions/decision:pv1:1/diagnostics/lineage")
        assert lineage.status_code == 200
        assert lineage.json()["decision_meaning"] == "REQUEST_RESEARCH"
    finally:
        app.dependency_overrides.clear()
