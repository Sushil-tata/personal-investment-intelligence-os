from fastapi.testclient import TestClient
from sqlmodel import Session, select

from piios_backend.core.database import engine
from piios_backend.main import app
from piios_backend.models.entities import AuditLog, InvestmentThesisEntity


def test_thesis_lifecycle() -> None:
    with TestClient(app) as client:
        list_response = client.get("/api/v1/theses")
        assert list_response.status_code == 200
        assert len(list_response.json()) >= 1

        create_payload = {
            "ticker": "MSFT",
            "asset_name": "Microsoft",
            "theme": "Enterprise AI",
            "bucket": "Strategic Alpha",
            "thesis": "Durable enterprise software moat with AI monetization upside.",
            "bull_case": "Cloud leadership and ecosystem lock-in support earnings compounding.",
            "bear_case": "Regulatory pressure and cloud pricing competition can compress margins.",
            "why_now": "AI product cycle is creating additional demand across enterprise stack.",
            "why_not_now": "Premium valuation leaves limited room for execution misses.",
            "invalidation_trigger": "Sustained Azure growth deceleration with lower operating leverage.",
            "valuation_notes": "Reasonable at quality premium; position sizing remains important.",
            "expected_holding_period": "3-5 years",
            "source_documents": ["rd_msft_1"],
            "confidence_score": 73,
        }
        create_response = client.post("/api/v1/theses", json=create_payload)
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["status"] == "DRAFT"

        thesis_id = created["thesis_id"]
        get_response = client.get(f"/api/v1/theses/{thesis_id}")
        assert get_response.status_code == 200
        assert get_response.json()["ticker"] == "MSFT"

        status_response = client.patch(f"/api/v1/theses/{thesis_id}/status", json={"status": "RESEARCHED"})
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "RESEARCHED"

        export_response = client.get("/api/v1/theses/export")
        assert export_response.status_code == 200
        assert "thesis_id" in export_response.text

    with Session(engine) as session:
        created_row = session.exec(select(InvestmentThesisEntity).where(InvestmentThesisEntity.ticker == "MSFT")).first()
        assert created_row is not None

        audit_events = session.exec(select(AuditLog).where(AuditLog.event_type == "THESIS_CREATED")).all()
        assert audit_events

        status_events = session.exec(select(AuditLog).where(AuditLog.event_type == "THESIS_STATUS_CHANGED")).all()
        assert status_events


def test_thesis_survives_restart() -> None:
    with TestClient(app) as client:
        create_payload = {
            "ticker": "AAPL",
            "asset_name": "Apple",
            "theme": "Consumer Platform",
            "bucket": "Strategic Alpha",
            "thesis": "Installed base and services monetization remain durable.",
            "bull_case": "Ecosystem lock-in and recurring services revenue expand margins.",
            "bear_case": "Hardware saturation and regulation pressure platform economics.",
            "why_now": "Services mix continues to improve and capital allocation stays disciplined.",
            "why_not_now": "Limited near-term upside if multiple compression persists.",
            "invalidation_trigger": "Sustained gross margin deterioration and ecosystem weakening.",
            "valuation_notes": "Quality premium with cash-flow support.",
            "expected_holding_period": "3-5 years",
            "source_documents": ["rd_aapl_1"],
            "confidence_score": 71,
        }
        create_response = client.post("/api/v1/theses", json=create_payload)
        assert create_response.status_code == 200
        thesis_id = create_response.json()["thesis_id"]

    with TestClient(app) as restarted_client:
        response = restarted_client.get(f"/api/v1/theses/{thesis_id}")
        assert response.status_code == 200
        assert response.json()["ticker"] == "AAPL"


def test_portfolio_drift_calculation_contract() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/portfolio/drift")
        assert response.status_code == 200
        payload = response.json()
        assert "generated_at" in payload
        assert payload["items"]
        first = payload["items"][0]
        for required in [
            "dimension",
            "key",
            "drift_amount",
            "drift_percentage",
            "severity",
            "recommended_action",
            "advisory_only",
        ]:
            assert required in first


def test_drift_output_is_advisory_only() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/portfolio/drift")
    assert response.status_code == 200
    items = response.json()["items"]
    assert all(item["advisory_only"] is True for item in items)


def test_approved_recommendation_links_to_thesis() -> None:
    with TestClient(app) as client:
        client.patch(
            "/api/v1/recommendations/r1/status",
            json={"status": "APPROVED", "approved_by": "reviewer"},
        )
        recommendations = client.get("/api/v1/recommendations")
        assert recommendations.status_code == 200
        approved = recommendations.json()
        assert approved

        theses = client.get("/api/v1/theses")
        assert theses.status_code == 200
        thesis_ids = {item["thesis_id"] for item in theses.json()}

        linked = [item for item in approved if item.get("thesis_id")]
        assert linked
        assert all(item["thesis_id"] in thesis_ids for item in linked)
