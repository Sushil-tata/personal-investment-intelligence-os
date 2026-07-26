from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from piios_backend.core.database import init_db
from piios_backend.main import app

client = TestClient(app)


def test_identity_routes_create_and_resolve() -> None:
    init_db()
    suffix = uuid4().hex[:8]
    company_id = f"co_test_us_{suffix}"
    security_id = f"sec_test_us_{suffix}"
    listing_id = f"list_test_nasdaq_{suffix}"
    ticker = f"T{suffix[:4]}"

    company_payload = {
        "company_id": company_id,
        "legal_name": "Test United States Corp",
        "common_name": "TUSC",
        "company_type": "CORPORATE",
        "jurisdiction_of_incorporation": "US",
        "primary_economic_country": "US",
        "sector": "Technology",
        "industry": "Software",
        "active_from": "2020-01-01",
        "active_to": None,
    }
    response = client.post("/api/v1/identity/companies", json=company_payload)
    assert response.status_code == 200

    security_payload = {
        "security_id": security_id,
        "issuer_company_id": company_id,
        "issuer_name": None,
        "security_type": "ORDINARY_EQUITY",
        "security_name": "Test US Common",
        "issue_currency": "USD",
        "issue_date": None,
        "maturity_date": None,
        "share_class_or_seniority": None,
        "economic_exposure_type": "EQUITY",
        "active_from": "2020-01-01",
        "active_to": None,
    }
    response = client.post("/api/v1/identity/securities", json=security_payload)
    assert response.status_code == 200

    listing_payload = {
        "listing_id": listing_id,
        "security_id": security_id,
        "exchange_code": "NASDAQ",
        "ticker": ticker,
        "trading_currency": "USD",
        "listing_country": "US",
        "is_primary_listing": True,
        "lot_size": 1,
        "price_source_symbol": ticker,
        "active_from": "2020-01-01",
        "active_to": None,
    }
    response = client.post("/api/v1/identity/listings", json=listing_payload)
    assert response.status_code == 200

    resolution_payload = {
        "exchange": "NASDAQ",
        "ticker": ticker,
        "effective_date": "2026-07-26",
    }
    response = client.post("/api/v1/identity/resolve", json=resolution_payload)
    assert response.status_code == 200
    assert response.json()["status"] in {"RESOLVED", "HISTORICAL_MATCH"}


def test_existing_portfolio_route_shape_unchanged() -> None:
    response = client.get("/api/v1/holdings")
    assert response.status_code == 200
    payload = response.json()
    assert payload
    first = payload[0]
    # Identity enrichment is shadow-only in Wave 2A.1; legacy fields remain intact.
    assert "ticker" in first
    assert "name" in first
    assert "quantity" in first
    assert "market_value" in first


def test_identity_shadow_diagnostics_non_invasive() -> None:
    before = client.get("/api/v1/recommendations").json()
    diag = client.get("/api/v1/identity/shadow/diagnostics")
    after = client.get("/api/v1/recommendations").json()

    assert diag.status_code == 200
    diag_payload = diag.json()
    assert diag_payload["enabled"] is True
    assert "items" in diag_payload
    assert before == after
