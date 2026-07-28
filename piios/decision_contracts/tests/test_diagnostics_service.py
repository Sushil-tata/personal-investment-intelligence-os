from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json

import pytest

from piios.decision_contracts.application.decision_capture_service import (
    DecisionCaptureRequest,
    DecisionCaptureService,
    DecisionType,
)
from piios.decision_contracts.application.decision_engine import RecommendationDecisionEngine
from piios.decision_contracts.application.diagnostics_service import (
    DiagnosticStatus,
    RecommendationDiagnosticsService,
)
from piios.decision_contracts.application.recommendation_reconstruction_service import (
    RecommendationReconstructionService,
)
from piios.decision_contracts.application.recommendation_replay_verification_service import (
    RecommendationReplayVerificationService,
)
from piios.decision_contracts.domain.decision import InvestmentDecision
from piios.decision_contracts.domain.enums import DecisionState
from piios.decision_contracts.infrastructure.in_memory_repositories import (
    InMemoryInvestmentDecisionRepository,
    InMemoryRecommendationProposalRepository,
    InMemoryRecommendationProposalVersionRepository,
    InMemoryRecommendationReasonRepository,
    InMemoryRecommendationSnapshotRepository,
    InMemoryRecommendationTraceRepository,
)
from piios.decision_contracts.tests.functional_acceptance_helpers import build_input, scenario_catalog
from piios.thesis.domain.entities import ThesisRoot, ThesisVersion
from piios.thesis.domain.enums import ThesisStatus
from piios.thesis.infrastructure.in_memory_claim_evidence_repositories import (
    InMemoryEvidenceItemRepository,
    InMemoryThesisClaimRepository,
)
from piios.thesis.infrastructure.in_memory_repositories import (
    InMemoryThesisRootRepository,
    InMemoryThesisVersionRepository,
)


class _CorruptedSnapshot:
    def __init__(self, base, canonical_payload_json: str):
        self.snapshot_id = base.snapshot_id
        self.proposal_version_id = base.proposal_version_id
        self.captured_at = base.captured_at
        self.canonical_payload_json = canonical_payload_json
        self.input_hash = base.input_hash


def _bundle(scenario_key: str = "A_strong_positive"):
    proposal_repo = InMemoryRecommendationProposalRepository()
    version_repo = InMemoryRecommendationProposalVersionRepository()
    snapshot_repo = InMemoryRecommendationSnapshotRepository()
    reason_repo = InMemoryRecommendationReasonRepository()
    trace_repo = InMemoryRecommendationTraceRepository()
    decision_repo = InMemoryInvestmentDecisionRepository()

    engine = RecommendationDecisionEngine(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        snapshot_repository=snapshot_repo,
        reason_repository=reason_repo,
        trace_repository=trace_repo,
    )

    data = build_input(scenario_catalog()[scenario_key])
    generated = engine.generate_recommendation(data)

    thesis_root_repo = InMemoryThesisRootRepository()
    thesis_version_repo = InMemoryThesisVersionRepository()
    claim_repo = InMemoryThesisClaimRepository()
    evidence_repo = InMemoryEvidenceItemRepository()

    thesis_id = data.thesis_version_id.split(":v")[0]
    thesis_root_repo.create(
        ThesisRoot(
            thesis_id=thesis_id,
            ticker=generated.proposal.target_key,
            lifecycle_status=ThesisStatus.RESEARCHED,
            current_version_number=1,
            created_at=data.generated_at,
            updated_at=data.generated_at,
        )
    )
    thesis_version_repo.create(
        ThesisVersion(
            version_id=data.thesis_version_id,
            thesis_id=thesis_id,
            version_number=1,
            asset_name=generated.proposal.target_key,
            theme="AI",
            bucket="Growth",
            thesis="Base thesis",
            bull_case="Bull",
            bear_case="Bear",
            why_now="Now",
            why_not_now="Not now",
            invalidation_trigger="Invalidation",
            valuation_notes="Valuation",
            expected_holding_period="2-5 years",
            source_documents=("doc1",),
            confidence_score=70.0,
            status=ThesisStatus.RESEARCHED,
            created_at=data.generated_at,
        )
    )

    for claim in data.claims:
        claim_repo.create(claim)
    for evidence in data.evidence_items:
        evidence_repo.create(evidence)

    reconstruction = RecommendationReconstructionService(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        snapshot_repository=snapshot_repo,
        trace_repository=trace_repo,
        reason_repository=reason_repo,
        decision_repository=decision_repo,
    )
    replay = RecommendationReplayVerificationService(reconstruction)

    diagnostics = RecommendationDiagnosticsService(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        snapshot_repository=snapshot_repo,
        trace_repository=trace_repo,
        decision_repository=decision_repo,
        reconstruction_service=reconstruction,
        replay_verification_service=replay,
        thesis_version_repository=thesis_version_repo,
        thesis_claim_repository=claim_repo,
        evidence_item_repository=evidence_repo,
    )

    capture = DecisionCaptureService(
        proposal_repository=proposal_repo,
        version_repository=version_repo,
        decision_repository=decision_repo,
    )

    return {
        "data": data,
        "generated": generated,
        "proposal_repo": proposal_repo,
        "version_repo": version_repo,
        "snapshot_repo": snapshot_repo,
        "trace_repo": trace_repo,
        "decision_repo": decision_repo,
        "thesis_version_repo": thesis_version_repo,
        "claim_repo": claim_repo,
        "evidence_repo": evidence_repo,
        "diagnostics": diagnostics,
        "capture": capture,
    }


def _check_map(diag):
    return {row.code: row for row in diag.checks}


def test_traceability_diagnostic_valid_lineage_passes() -> None:
    bundle = _bundle("A_strong_positive")
    proposal_version_id = bundle["generated"].proposal_version.proposal_version_id

    diag = bundle["diagnostics"].diagnose_traceability(proposal_version_id)

    checks = _check_map(diag)
    assert diag.overall_status == DiagnosticStatus.PASS
    assert checks["PROPOSAL_EXISTS"].status == DiagnosticStatus.PASS
    assert checks["RECONSTRUCTION_SUCCESS"].status == DiagnosticStatus.PASS
    assert checks["REPLAY_VERIFICATION_PASS"].status == DiagnosticStatus.PASS
    assert checks["CLAIM_REFERENCES_EXIST"].status == DiagnosticStatus.PASS
    assert checks["EVIDENCE_REFERENCES_EXIST"].status == DiagnosticStatus.PASS


def test_traceability_diagnostic_missing_proposal_version_fails() -> None:
    bundle = _bundle("A_strong_positive")

    diag = bundle["diagnostics"].diagnose_traceability("missing-version")

    assert diag.overall_status == DiagnosticStatus.FAIL
    assert any(row.code == "PROPOSAL_VERSION_MISSING" for row in diag.checks)


def test_traceability_diagnostic_missing_proposal_fails() -> None:
    bundle = _bundle("A_strong_positive")
    generated = bundle["generated"]
    bundle["proposal_repo"]._items.pop(generated.proposal.proposal_id)

    diag = bundle["diagnostics"].diagnose_traceability(generated.proposal_version.proposal_version_id)

    assert diag.overall_status == DiagnosticStatus.FAIL
    assert any(row.code == "PROPOSAL_MISSING" for row in diag.checks)


def test_traceability_diagnostic_missing_snapshot_fails() -> None:
    bundle = _bundle("A_strong_positive")
    generated = bundle["generated"]
    snapshot_repo = bundle["snapshot_repo"]
    snapshot_repo._by_snapshot_id.pop(generated.input_snapshot.snapshot_id, None)
    snapshot_repo._by_version_id.pop(generated.proposal_version.proposal_version_id, None)

    diag = bundle["diagnostics"].diagnose_traceability(generated.proposal_version.proposal_version_id)

    assert diag.overall_status == DiagnosticStatus.FAIL
    assert any(row.code == "SNAPSHOT_MISSING" for row in diag.checks)


def test_traceability_diagnostic_missing_canonical_payload_detected() -> None:
    bundle = _bundle("A_strong_positive")
    generated = bundle["generated"]
    snapshot_repo = bundle["snapshot_repo"]
    base = snapshot_repo._by_snapshot_id[generated.input_snapshot.snapshot_id]
    corrupted = _CorruptedSnapshot(base=base, canonical_payload_json="")
    snapshot_repo._by_snapshot_id[base.snapshot_id] = corrupted
    snapshot_repo._by_version_id[generated.proposal_version.proposal_version_id] = corrupted

    diag = bundle["diagnostics"].diagnose_traceability(generated.proposal_version.proposal_version_id)

    assert any(row.code == "CANONICAL_PAYLOAD_MISSING" for row in diag.checks)


def test_traceability_diagnostic_replay_mismatch_detected() -> None:
    bundle = _bundle("A_strong_positive")
    generated = bundle["generated"]
    snapshot_repo = bundle["snapshot_repo"]

    row = snapshot_repo._by_snapshot_id[generated.input_snapshot.snapshot_id]
    payload = json.loads(row.canonical_payload_json)
    payload["thesis_health"]["supporting_strength"] = 0.01
    payload["thesis_health"]["contradictory_strength"] = 0.99
    tampered = replace(
        generated.input_snapshot,
        canonical_payload_json=json.dumps(payload, sort_keys=True, separators=(",", ":")),
    )
    snapshot_repo._by_snapshot_id[generated.input_snapshot.snapshot_id] = tampered
    snapshot_repo._by_version_id[generated.proposal_version.proposal_version_id] = tampered

    diag = bundle["diagnostics"].diagnose_traceability(generated.proposal_version.proposal_version_id)

    checks = _check_map(diag)
    assert checks["REPLAY_VERIFICATION_FAIL"].status == DiagnosticStatus.FAIL


def test_traceability_diagnostic_reconstruction_failure_detected() -> None:
    bundle = _bundle("A_strong_positive")
    generated = bundle["generated"]
    trace_repo = bundle["trace_repo"]

    trace_repo._traces.pop(generated.recommendation_trace.trace_id, None)
    trace_repo._trace_by_proposal_version.pop(generated.proposal_version.proposal_version_id, None)
    trace_repo._trace_by_execution_identity.pop(generated.recommendation_trace.execution_identity, None)
    trace_repo._entries_by_trace_id.pop(generated.recommendation_trace.trace_id, None)

    diag = bundle["diagnostics"].diagnose_traceability(generated.proposal_version.proposal_version_id)

    checks = _check_map(diag)
    assert checks["RECONSTRUCTION_FAILED"].status == DiagnosticStatus.FAIL


def test_traceability_diagnostic_missing_thesis_claim_and_evidence_detected() -> None:
    bundle = _bundle("A_strong_positive")
    generated = bundle["generated"]
    data = bundle["data"]

    bundle["thesis_version_repo"]._items.clear()
    bundle["claim_repo"]._items.pop(data.claims[0].claim_id, None)
    bundle["evidence_repo"]._items.pop(data.evidence_items[0].evidence_id, None)

    diag = bundle["diagnostics"].diagnose_traceability(generated.proposal_version.proposal_version_id)

    checks = _check_map(diag)
    assert checks["THESIS_VERSION_MISSING"].status == DiagnosticStatus.FAIL
    assert checks["CLAIM_REFERENCES_MISSING"].status == DiagnosticStatus.FAIL
    assert checks["EVIDENCE_REFERENCES_MISSING"].status == DiagnosticStatus.FAIL


def test_traceability_diagnostic_decision_linkage_valid_and_orphan_detected() -> None:
    bundle = _bundle("A_strong_positive")
    generated = bundle["generated"]
    capture = bundle["capture"]
    decision_repo = bundle["decision_repo"]

    decision = capture.capture(
        DecisionCaptureRequest(
            proposal_version_id=generated.proposal_version.proposal_version_id,
            decision_type=DecisionType.ACCEPT,
            reviewer="rm_001",
            reason_code="APPROVED",
            client_request_id="req-accept",
        )
    )

    valid = bundle["diagnostics"].diagnose_traceability(generated.proposal_version.proposal_version_id)
    assert _check_map(valid)["DECISION_LINKAGE_VALID"].status == DiagnosticStatus.PASS

    orphan = InvestmentDecision(
        decision_id="decision:orphan:1",
        proposal_version_id="missing-version",
        state=DecisionState.ACCEPTED,
        reason_code="APPROVED",
        decided_at=datetime.now(timezone.utc),
        decided_by="rm_002",
    )
    decision_repo.create(orphan)

    orphan_diag = bundle["diagnostics"].diagnose_decision(orphan.decision_id)
    assert orphan_diag.overall_status == DiagnosticStatus.FAIL
    assert any(row.code == "DECISION_PROPOSAL_VERSION_MISSING" for row in orphan_diag.checks)
    assert decision.decision_id != orphan.decision_id


def test_confidence_diagnostic_complete_projection_and_authoritative_preserved() -> None:
    bundle = _bundle("A_strong_positive")
    generated = bundle["generated"]

    diag = bundle["diagnostics"].diagnose_confidence(generated.proposal_version.proposal_version_id)
    components = {row.name: row for row in diag.components}

    assert diag.authoritative_confidence == generated.proposal_version.confidence_breakdown.overall_confidence
    assert components["valuation_support"].status == DiagnosticStatus.PASS
    assert components["model_rule_confidence"].status == DiagnosticStatus.PASS
    assert components["replay_integrity"].status == DiagnosticStatus.PASS


def test_confidence_diagnostic_unavailable_component_and_optional_data_absence() -> None:
    bundle = _bundle("A_strong_positive")
    generated = bundle["generated"]
    snapshot_repo = bundle["snapshot_repo"]
    snapshot_repo._by_snapshot_id.pop(generated.input_snapshot.snapshot_id, None)
    snapshot_repo._by_version_id.pop(generated.proposal_version.proposal_version_id, None)

    diag = bundle["diagnostics"].diagnose_confidence(generated.proposal_version.proposal_version_id)
    components = {row.name: row for row in diag.components}

    assert components["evidence_sufficiency"].status == DiagnosticStatus.UNAVAILABLE
    assert components["risk_uncertainty"].status == DiagnosticStatus.UNAVAILABLE


def test_confidence_diagnostic_stale_evidence_and_deterministic_ordering() -> None:
    bundle = _bundle("E_stale_evidence")
    generated = bundle["generated"]

    first = bundle["diagnostics"].diagnose_confidence(generated.proposal_version.proposal_version_id)
    second = bundle["diagnostics"].diagnose_confidence(generated.proposal_version.proposal_version_id)

    first_rows = [(row.name, row.status, row.value) for row in first.components]
    second_rows = [(row.name, row.status, row.value) for row in second.components]
    assert first_rows == second_rows

    component = {row.name: row for row in first.components}["evidence_freshness"]
    assert component.value is not None and component.value < 0.2
    assert "evidence freshness is low" in first.limitations


@pytest.mark.parametrize(
    ("decision_type", "reason_code", "expected_meaning"),
    [
        (DecisionType.ACCEPT, "APPROVED", "ACCEPTED"),
        (DecisionType.REJECT, "RISK", "REJECTED"),
        (DecisionType.MODIFIED, "ADJUST_SIZE", "MODIFIED"),
        (DecisionType.OVERRIDDEN, "ALTERNATIVE_BETTER", "OVERRIDDEN"),
        (DecisionType.DEFERRED, "WAIT", "DEFERRED"),
        (DecisionType.REQUEST_RESEARCH, None, "REQUEST_RESEARCH"),
    ],
)
def test_decision_lineage_diagnostic_states_and_request_research_representation(
    decision_type,
    reason_code,
    expected_meaning,
) -> None:
    bundle = _bundle("A_strong_positive")
    generated = bundle["generated"]

    kwargs = {
        "proposal_version_id": generated.proposal_version.proposal_version_id,
        "decision_type": decision_type,
        "reviewer": "rm_001",
        "client_request_id": f"req-{decision_type.value.lower()}",
    }
    if reason_code is not None:
        kwargs["reason_code"] = reason_code
    if decision_type == DecisionType.MODIFIED:
        kwargs["modified_action"] = bundle["generated"].proposal_version.action_proposal.action
    if decision_type == DecisionType.OVERRIDDEN:
        kwargs["preferred_alternative_target_key"] = "AMD"

    decision = bundle["capture"].capture(DecisionCaptureRequest(**kwargs))
    diag = bundle["diagnostics"].diagnose_decision(decision.decision_id)

    assert diag.overall_status in {DiagnosticStatus.PASS, DiagnosticStatus.WARNING}
    assert diag.decision_meaning == expected_meaning
    assert any(row.code == "DECISION_IMMUTABLE_REPRESENTATION" for row in diag.checks)
    assert any(row.code == "DECISION_TIMESTAMP_PRESENT" for row in diag.checks)


def test_decision_lineage_diagnostic_flags_missing_reviewer() -> None:
    bundle = _bundle("A_strong_positive")
    generated = bundle["generated"]
    decision = InvestmentDecision(
        decision_id="decision:legacy:1",
        proposal_version_id=generated.proposal_version.proposal_version_id,
        state=DecisionState.ACCEPTED,
        reason_code="APPROVED",
        decided_at=datetime.now(timezone.utc),
        decided_by=None,
    )
    bundle["decision_repo"].create(decision)

    diag = bundle["diagnostics"].diagnose_decision(decision.decision_id)

    assert any(row.code == "DECISION_REVIEWER_MISSING" for row in diag.checks)


def test_governance_backlog_clean_case_has_no_items() -> None:
    bundle = _bundle("A_strong_positive")
    generated = bundle["generated"]

    backlog = bundle["diagnostics"].build_governance_review_backlog(
        generated.proposal_version.proposal_version_id
    )

    assert backlog.items == tuple()


def test_governance_backlog_contains_deterministic_items_for_failures() -> None:
    bundle = _bundle("B_strong_negative")
    generated = bundle["generated"]
    capture = bundle["capture"]

    capture.capture(
        DecisionCaptureRequest(
            proposal_version_id=generated.proposal_version.proposal_version_id,
            decision_type=DecisionType.OVERRIDDEN,
            reviewer="rm_001",
            reason_code="ALTERNATIVE_BETTER",
            preferred_alternative_target_key="AMD",
            client_request_id="req-override",
        )
    )
    capture.capture(
        DecisionCaptureRequest(
            proposal_version_id=generated.proposal_version.proposal_version_id,
            decision_type=DecisionType.REQUEST_RESEARCH,
            reviewer="rm_001",
            client_request_id="req-research",
        )
    )

    row = bundle["snapshot_repo"]._by_snapshot_id[generated.input_snapshot.snapshot_id]
    payload = json.loads(row.canonical_payload_json)
    payload["thesis_health"]["supporting_strength"] = 0.01
    payload["thesis_health"]["contradictory_strength"] = 0.99
    payload["thesis_health"]["evidence_freshness"] = 0.05
    tampered = replace(
        generated.input_snapshot,
        canonical_payload_json=json.dumps(payload, sort_keys=True, separators=(",", ":")),
    )
    bundle["snapshot_repo"]._by_snapshot_id[generated.input_snapshot.snapshot_id] = tampered
    bundle["snapshot_repo"]._by_version_id[generated.proposal_version.proposal_version_id] = tampered

    first = bundle["diagnostics"].build_governance_review_backlog(generated.proposal_version.proposal_version_id)
    second = bundle["diagnostics"].build_governance_review_backlog(generated.proposal_version.proposal_version_id)

    first_keys = [(row.review_item_id, row.reason_code, row.severity, row.decision_id) for row in first.items]
    second_keys = [(row.review_item_id, row.reason_code, row.severity, row.decision_id) for row in second.items]

    assert first_keys == second_keys
    reason_codes = {row.reason_code for row in first.items}
    assert "REPLAY_MISMATCH" in reason_codes
    assert "STALE_EVIDENCE" in reason_codes
    assert "UNRESOLVED_CONTRADICTION" in reason_codes
    assert "OVERRIDDEN_RECOMMENDATION" in reason_codes
    assert "REQUEST_RESEARCH_DECISION" in reason_codes


def test_governance_backlog_stable_ordering_and_no_duplicate_items() -> None:
    bundle = _bundle("A_strong_positive")
    generated = bundle["generated"]

    bundle["thesis_version_repo"]._items.clear()
    first = bundle["diagnostics"].build_governance_review_backlog(generated.proposal_version.proposal_version_id)
    second = bundle["diagnostics"].build_governance_review_backlog(generated.proposal_version.proposal_version_id)

    first_ids = [row.review_item_id for row in first.items]
    second_ids = [row.review_item_id for row in second.items]
    assert first_ids == second_ids
    assert len(first_ids) == len(set(first_ids))
