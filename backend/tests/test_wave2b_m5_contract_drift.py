from __future__ import annotations

from pathlib import Path
import re

from piios.decision_contracts.application.decision_capture_service import DecisionType
from piios.decision_contracts.application.diagnostics_service import DiagnosticSeverity, DiagnosticStatus
from piios_backend.main import app
from piios_backend.schemas.decision_contracts import DecisionCaptureRequestModel


def test_wave2b_m5_enum_contract_alignment() -> None:
    openapi = app.openapi()
    components = openapi["components"]["schemas"]

    status_enum = set(components["DiagnosticStatus"]["enum"])
    severity_enum = set(components["DiagnosticSeverity"]["enum"])

    assert status_enum == {row.value for row in DiagnosticStatus}
    assert severity_enum == {row.value for row in DiagnosticSeverity}


def test_wave2b_m5_decision_capture_request_enum_alignment() -> None:
    openapi = app.openapi()
    components = openapi["components"]["schemas"]
    request_props = components["DecisionCaptureRequestModel"]["properties"]

    assert request_props["decision_type"]["$ref"].endswith("/DecisionType")
    assert {row.value for row in DecisionType} == set(components["DecisionType"]["enum"])


def test_wave2b_m5_no_orm_entity_leak_in_transport_schemas() -> None:
    openapi = app.openapi()
    schema_names = set(openapi["components"]["schemas"].keys())

    forbidden = {
        "InvestmentDecisionEntity",
        "RecommendationProposalEntity",
        "RecommendationProposalVersionEntity",
        "RecommendationTraceEntity",
    }
    assert forbidden.isdisjoint(schema_names)


def test_wave2b_m5_domain_concept_separation_in_transport_contract() -> None:
    openapi = app.openapi()
    schemas = openapi["components"]["schemas"]

    proposal_fields = set(schemas["RecommendationProposalDetailResponse"]["properties"].keys())
    decision_fields = set(schemas["DecisionDetailResponse"]["properties"].keys())

    assert "decision_id" not in proposal_fields
    assert "proposal_id" not in decision_fields
    assert "execution_id" not in proposal_fields
    assert "execution_id" not in decision_fields


def test_wave2b_m5_frontend_contract_mentions_request_research_representation() -> None:
    doc = Path(__file__).resolve().parents[2] / "piios" / "docs" / "WAVE2B_M5_FRONTEND_CONTRACT.md"
    text = doc.read_text(encoding="utf-8")

    assert "REQUEST_RESEARCH" in text
    assert re.search(r"REQUEST_RESEARCH_DECISION", text)
