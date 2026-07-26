from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from piios_backend.core.database import engine, init_db
from piios_backend.main import app
from piios_backend.services.thesis_shadow import run_thesis_shadow_diagnostics


def test_thesis_route_contract_preserved_with_versioned_backend() -> None:
    init_db()
    with TestClient(app) as client:
        payload = {
            "ticker": "AMZN",
            "asset_name": "Amazon",
            "theme": "Cloud and Consumer",
            "bucket": "Strategic Alpha",
            "thesis": "Scale platform with AWS cash-flow durability.",
            "bull_case": "Cloud growth plus retail efficiency supports margins.",
            "bear_case": "Regulation and spending normalization can pressure earnings.",
            "why_now": "AI/cloud demand adds incremental runway.",
            "why_not_now": "Execution misses can trigger valuation reset.",
            "invalidation_trigger": "Sustained AWS deceleration and margin pressure.",
            "valuation_notes": "Premium but supported by optionality.",
            "expected_holding_period": "3-5 years",
            "source_documents": ["rd_amzn_1"],
            "confidence_score": 72,
        }
        created = client.post("/api/v1/theses", json=payload)
        assert created.status_code == 200
        body = created.json()

        expected_keys = {
            "thesis_id",
            "ticker",
            "asset_name",
            "theme",
            "bucket",
            "thesis",
            "bull_case",
            "bear_case",
            "why_now",
            "why_not_now",
            "invalidation_trigger",
            "valuation_notes",
            "expected_holding_period",
            "source_documents",
            "confidence_score",
            "status",
            "created_at",
            "updated_at",
        }
        assert set(body.keys()) == expected_keys

        thesis_id = body["thesis_id"]
        status_update = client.patch(f"/api/v1/theses/{thesis_id}/status", json={"status": "APPROVED"})
        assert status_update.status_code == 200
        assert status_update.json()["status"] == "APPROVED"

        fetched = client.get(f"/api/v1/theses/{thesis_id}")
        assert fetched.status_code == 200
        assert set(fetched.json().keys()) == expected_keys


def test_shadow_equivalence_no_mismatch_for_seeded_rows() -> None:
    init_db()
    with Session(engine) as session:
        result = run_thesis_shadow_diagnostics(session)

    assert result["enabled"] is True
    assert result["legacy_count"] >= 1
    assert result["versioned_count"] >= 1
    assert result["mismatches"] == []
