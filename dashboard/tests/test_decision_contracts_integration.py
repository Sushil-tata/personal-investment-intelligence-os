"""Tests for the live Wave 2B decision-contracts integration: typed DTO
parsing (proposal, proposal-version, decisions, diagnostics, governance
backlog), REQUEST_RESEARCH representation, PASS/FAIL/WARNING/UNAVAILABLE/
NOT_APPLICABLE status handling, decision capture (success/duplicate/
validation-error/backend-error), and page-level rendering under healthy,
empty, partial, malformed, unavailable, and timeout backend conditions.
"""
from pathlib import Path

import pytest
import requests
from streamlit.testing.v1 import AppTest

from lib import api_client as api
from lib import components as ui

DASHBOARD_ROOT = Path(__file__).resolve().parents[1]

PV = {
    "proposal_version_id": "PV1", "proposal_id": "P1", "version_number": 2, "status": "ACTIVE",
    "created_at": "2026-07-01T00:00:00Z", "snapshot_id": "S1", "action": "BUY", "action_note": "Add on strength",
    "action_min_weight": 1.0, "action_max_weight": 2.0, "authoritative_confidence": 0.82,
    "priority_level": "HIGH", "priority_score": 0.9, "required_human_review": True,
    "supersedes_version_id": "PV0", "advisory_only": True,
}
PROPOSAL = {"proposal_id": "P1", "target_type": "EQUITY", "target_key": "NVDA", "scope": "TACTICAL",
            "status": "ACTIVE", "created_at": "t", "updated_at": "t", "advisory_only": True}
CONF_WITH_UNAVAILABLE = {
    "proposal_version_id": "PV1", "authoritative_confidence": 0.82,
    "components": [
        {"name": "evidence_quality", "value": 0.7, "status": "PASS", "source": "engine", "explanation": "ok"},
        {"name": "replay_component", "value": None, "status": "UNAVAILABLE", "source": "engine", "explanation": "no replay run yet"},
    ],
    "limitations": ["Some components unavailable"], "generated_at": "t", "advisory_only": True,
}
TRACE_PASS = {
    "proposal_version_id": "PV1", "proposal_id": "P1", "overall_status": "PASS",
    "checks": [{"code": "REPLAY_VERIFICATION", "status": "PASS", "severity": "INFO", "message": "Replay matched.",
                "related_entity_type": "proposal_version", "related_entity_id": "PV1", "remediation_hint": None}],
    "diagnostic_codes": ["REPLAY_VERIFICATION"], "severity": "INFO", "generated_at": "t", "advisory_only": True,
}
BACKLOG_EMPTY = {"proposal_version_id": "PV1", "items": [], "generated_at": "t", "advisory_only": True}
BACKLOG_WITH_ITEMS = {
    "proposal_version_id": "PV1",
    "items": [{"review_item_id": "G1", "proposal_id": "P1", "proposal_version_id": "PV1", "decision_id": None,
               "reason_code": "STALE_EVIDENCE", "severity": "HIGH", "status": "OPEN", "created_at": "t",
               "source_diagnostic": "traceability", "summary": "Evidence older than SLA"}],
    "generated_at": "t", "advisory_only": True,
}
DECISION_REQUEST_RESEARCH = {
    "decision_id": "D1", "proposal_version_id": "PV1", "state": "DEFERRED", "decision_meaning": "REQUEST_RESEARCH",
    "reason_code": "REQUEST_RESEARCH", "reason_text": None, "decided_by": "sushil", "decided_at": "t",
    "preferred_alternative_target_key": None, "modified_action": None, "modified_action_note": None,
    "modified_action_min_weight": None, "modified_action_max_weight": None, "modified_position_min_weight": None,
    "modified_position_max_weight": None, "advisory_only": True,
}
LINEAGE = {
    "decision_id": "D1", "proposal_id": "P1", "proposal_version_id": "PV1", "decision_state": "DEFERRED",
    "decision_meaning": "REQUEST_RESEARCH", "overall_status": "WARNING",
    "checks": [{"code": "DECISION_LINKED", "status": "WARNING", "severity": "MEDIUM", "message": "check",
                "related_entity_type": "decision", "related_entity_id": "D1", "remediation_hint": "review"}],
    "diagnostic_codes": ["DECISION_LINKED"], "severity": "MEDIUM", "generated_at": "t", "advisory_only": True,
}


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, raise_exc=None):
        self.status_code = status_code
        self._json_data = json_data
        self.text = str(json_data) if json_data is not None else ""
        self.content = b"x" if json_data is not None else b""
        self._raise_exc = raise_exc

    def json(self):
        if self._raise_exc:
            raise self._raise_exc
        return self._json_data


# --- DTO parsing -------------------------------------------------------------

def test_proposal_version_parses_all_required_and_optional_fields(monkeypatch):
    monkeypatch.setattr(requests, "request", lambda m, u, **kw: _FakeResponse(200, PV))
    result = api.get_proposal_version("PV1")
    assert result.ok
    assert result.data.action == "BUY"
    assert result.data.version_number == 2
    assert result.data.supersedes_version_id == "PV0"
    assert result.data.authoritative_confidence == 0.82


def test_confidence_diagnostic_preserves_unavailable_component_with_null_value(monkeypatch):
    monkeypatch.setattr(requests, "request", lambda m, u, **kw: _FakeResponse(200, CONF_WITH_UNAVAILABLE))
    result = api.get_confidence_diagnostic("PV1")
    assert result.ok
    unavailable = [c for c in result.data.components if c.status == "UNAVAILABLE"]
    assert len(unavailable) == 1
    assert unavailable[0].value is None


def test_traceability_diagnostic_parses_checks(monkeypatch):
    monkeypatch.setattr(requests, "request", lambda m, u, **kw: _FakeResponse(200, TRACE_PASS))
    result = api.get_traceability_diagnostic("PV1")
    assert result.ok
    assert result.data.overall_status == "PASS"
    assert result.data.checks[0].code == "REPLAY_VERIFICATION"


def test_governance_backlog_parses_items(monkeypatch):
    monkeypatch.setattr(requests, "request", lambda m, u, **kw: _FakeResponse(200, BACKLOG_WITH_ITEMS))
    result = api.get_governance_backlog("PV1")
    assert result.ok
    assert result.data.items[0].severity == "HIGH"
    assert result.data.items[0].reason_code == "STALE_EVIDENCE"


def test_governance_backlog_empty_is_a_clean_success_not_an_error(monkeypatch):
    monkeypatch.setattr(requests, "request", lambda m, u, **kw: _FakeResponse(200, BACKLOG_EMPTY))
    result = api.get_governance_backlog("PV1")
    assert result.ok
    assert result.data.items == []


def test_decision_lineage_diagnostic_parses(monkeypatch):
    monkeypatch.setattr(requests, "request", lambda m, u, **kw: _FakeResponse(200, LINEAGE))
    result = api.get_decision_lineage_diagnostic("D1")
    assert result.ok
    assert result.data.overall_status == "WARNING"
    assert result.data.decision_meaning == "REQUEST_RESEARCH"


def test_request_research_decision_meaning_preserved_despite_deferred_state(monkeypatch):
    monkeypatch.setattr(requests, "request", lambda m, u, **kw: _FakeResponse(200, DECISION_REQUEST_RESEARCH))
    result = api.get_latest_decision_for_proposal_version("PV1")
    assert result.ok
    assert result.data.state == "DEFERRED"
    assert result.data.decision_meaning == "REQUEST_RESEARCH"


def test_latest_decision_null_body_is_a_clean_empty_result(monkeypatch):
    monkeypatch.setattr(requests, "request", lambda m, u, **kw: _FakeResponse(200, None))
    result = api.get_latest_decision_for_proposal_version("PV1")
    assert result.ok
    assert result.data is None


def test_decisions_history_empty_list(monkeypatch):
    monkeypatch.setattr(requests, "request", lambda m, u, **kw: _FakeResponse(200, []))
    result = api.list_decisions_for_proposal_version("PV1")
    assert result.ok
    assert result.data == []


def test_capture_decision_success(monkeypatch):
    monkeypatch.setattr(requests, "request", lambda m, u, **kw: _FakeResponse(200, DECISION_REQUEST_RESEARCH))
    result = api.capture_decision("PV1", "REQUEST_RESEARCH", "sushil")
    assert result.ok
    assert result.data.decision_id == "D1"


def test_capture_decision_validation_error_422(monkeypatch):
    monkeypatch.setattr(requests, "request", lambda m, u, **kw: _FakeResponse(422, {"detail": "invalid payload"}))
    result = api.capture_decision("PV1", "ACCEPT", "")
    assert not result.ok
    assert "422" in result.error
    assert "invalid payload" in result.error


def test_capture_decision_unknown_proposal_version_404(monkeypatch):
    monkeypatch.setattr(requests, "request", lambda m, u, **kw: _FakeResponse(404, {"detail": "not found"}))
    result = api.capture_decision("UNKNOWN", "ACCEPT", "sushil")
    assert not result.ok
    assert "404" in result.error


def test_backend_unavailable_503(monkeypatch):
    monkeypatch.setattr(requests, "request", lambda m, u, **kw: _FakeResponse(503, {"detail": "repository unavailable"}))
    result = api.get_proposal_version("PV1")
    assert not result.ok
    assert "503" in result.error


def test_timeout_is_caught_cleanly(monkeypatch):
    def _raise(*a, **kw):
        raise requests.exceptions.Timeout("slow")
    monkeypatch.setattr(requests, "request", _raise)
    result = api.get_proposal_version("PV1")
    assert not result.ok
    assert "timed out" in result.error


def test_malformed_proposal_version_payload_is_reported_not_crashed(monkeypatch):
    monkeypatch.setattr(requests, "request", lambda m, u, **kw: _FakeResponse(200, {"unexpected": "shape"}))
    result = api.get_proposal_version("PV1")
    assert not result.ok
    assert "Unexpected response shape" in result.error


# --- badge / status rendering -------------------------------------------------

@pytest.mark.parametrize("status", list(ui.__dict__.get("_DIAGNOSTIC_STATUS_COLORS", {
    "PASS": None, "FAIL": None, "WARNING": None, "UNAVAILABLE": None, "NOT_APPLICABLE": None}).keys()))
def test_diagnostic_status_badge_covers_all_statuses(status):
    badge = ui.diagnostic_status_badge(status)
    assert status in badge or "N/A" in badge


@pytest.mark.parametrize("severity", ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"])
def test_diagnostic_severity_badge_covers_all_severities(severity):
    badge = ui.diagnostic_severity_badge(severity)
    assert severity in badge


def test_unavailable_status_is_visually_distinct_from_fail():
    unavailable = ui.diagnostic_status_badge("UNAVAILABLE")
    fail = ui.diagnostic_status_badge("FAIL")
    assert unavailable != fail
    assert "#B3261E" not in unavailable  # FAIL's red must not leak into UNAVAILABLE


# --- Page-level rendering under every required backend condition -----------

def _router(mode):
    def _fake_request(method, url, **kw):
        if mode == "unreachable":
            raise requests.exceptions.ConnectionError("no backend")
        if mode == "timeout":
            raise requests.exceptions.Timeout("slow")
        path = url.split("/api/v1", 1)[-1]
        if mode == "malformed":
            return _FakeResponse(200, {"nonsense": True})
        if mode == "partial":
            if "diagnostics" in path or "governance-backlog" in path:
                return _FakeResponse(503, {"detail": "diagnostics temporarily unavailable"})
        healthy_routes = {
            "/decision-contracts/proposal-versions/PV1": PV,
            "/decision-contracts/proposals/P1": PROPOSAL,
            "/decision-contracts/proposal-versions/PV1/diagnostics/confidence": CONF_WITH_UNAVAILABLE,
            "/decision-contracts/proposal-versions/PV1/diagnostics/traceability": TRACE_PASS,
            "/decision-contracts/proposal-versions/PV1/governance-backlog": BACKLOG_WITH_ITEMS,
            "/decision-contracts/proposal-versions/PV1/decisions": [DECISION_REQUEST_RESEARCH],
            "/decision-contracts/proposal-versions/PV1/decisions/latest": DECISION_REQUEST_RESEARCH,
            "/decision-contracts/decisions/D1/diagnostics/lineage": LINEAGE,
            "/decision-contracts/decisions/capture": DECISION_REQUEST_RESEARCH,
        }
        if mode == "empty":
            empty_routes = dict(healthy_routes)
            empty_routes["/decision-contracts/proposal-versions/PV1/governance-backlog"] = BACKLOG_EMPTY
            empty_routes["/decision-contracts/proposal-versions/PV1/decisions"] = []
            empty_routes["/decision-contracts/proposal-versions/PV1/decisions/latest"] = None
            return _FakeResponse(200, empty_routes.get(path, {}))
        if path not in healthy_routes:
            return _FakeResponse(404, {"detail": "not found"})
        return _FakeResponse(200, healthy_routes[path])
    return _fake_request


@pytest.mark.parametrize("page", [
    "pages/21_Recommendation_Review.py", "pages/22_Decisions.py", "pages/23_Governance.py",
])
@pytest.mark.parametrize("mode", ["healthy", "empty", "partial", "unreachable", "timeout", "malformed"])
def test_decision_contracts_pages_render_without_exception(monkeypatch, page, mode):
    monkeypatch.setattr(requests, "request", _router(mode))
    at = AppTest.from_file(str(DASHBOARD_ROOT / page))
    at.session_state["piios_shared_proposal_version_id"] = "PV1"
    at.session_state["piios_shared_decision_id"] = "D1"
    at.run(timeout=30)
    assert not at.exception, f"{page} ({mode}) raised: {[str(e) for e in at.exception]}"


def test_decisions_page_shows_request_further_research_label(monkeypatch):
    monkeypatch.setattr(requests, "request", _router("healthy"))
    at = AppTest.from_file(str(DASHBOARD_ROOT / "pages/22_Decisions.py"))
    at.session_state["piios_shared_proposal_version_id"] = "PV1"
    at.run(timeout=30)
    assert not at.exception
    rendered_text = " ".join(df.value.to_string() for df in at.dataframe) if at.dataframe else ""
    assert "Request Further Research" in rendered_text


def test_decisions_page_successful_submission_shows_success_and_refreshes(monkeypatch):
    call_count = {"n": 0}

    def _fake_request(method, url, **kw):
        path = url.split("/api/v1", 1)[-1]
        if path == "/decision-contracts/decisions/capture":
            call_count["n"] += 1
            return _FakeResponse(200, DECISION_REQUEST_RESEARCH)
        return _router("healthy")(method, url, **kw)

    monkeypatch.setattr(requests, "request", _fake_request)
    at = AppTest.from_file(str(DASHBOARD_ROOT / "pages/22_Decisions.py"))
    at.session_state["piios_shared_proposal_version_id"] = "PV1"
    at.run(timeout=30)
    assert not at.exception

    at.selectbox[0].set_value("REQUEST_RESEARCH")
    at.text_input(key=None).set_value("sushil") if False else None
    # Find the reviewer text_input by iterating (form-scoped widgets)
    reviewer_input = next(t for t in at.text_input if t.label.startswith("Reviewer"))
    reviewer_input.set_value("sushil")
    submit = next(b for b in at.button if b.label == "Submit decision")
    submit.click().run(timeout=30)

    assert not at.exception
    assert call_count["n"] == 1
    assert any("Decision recorded" in s.value for s in at.success)


def test_decisions_page_duplicate_submission_shows_idempotent_notice(monkeypatch):
    monkeypatch.setattr(requests, "request", _router("healthy"))
    at = AppTest.from_file(str(DASHBOARD_ROOT / "pages/22_Decisions.py"))
    at.session_state["piios_shared_proposal_version_id"] = "PV1"
    at.session_state["piios_last_decision_id"] = "D1"  # simulate having already recorded D1 once
    at.run(timeout=30)
    reviewer_input = next(t for t in at.text_input if t.label.startswith("Reviewer"))
    reviewer_input.set_value("sushil")
    submit = next(b for b in at.button if b.label == "Submit decision")
    submit.click().run(timeout=30)
    assert not at.exception
    assert any("already recorded" in i.value for i in at.info)


def test_decisions_page_missing_reviewer_shows_validation_error(monkeypatch):
    monkeypatch.setattr(requests, "request", _router("healthy"))
    at = AppTest.from_file(str(DASHBOARD_ROOT / "pages/22_Decisions.py"))
    at.session_state["piios_shared_proposal_version_id"] = "PV1"
    at.run(timeout=30)
    submit = next(b for b in at.button if b.label == "Submit decision")
    submit.click().run(timeout=30)
    assert not at.exception
    assert any("Reviewer is required" in m.value for m in at.markdown if "Reviewer is required" in m.value)
