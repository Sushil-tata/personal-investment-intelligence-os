from __future__ import annotations

from fastapi.testclient import TestClient

from piios_backend.main import app
from piios_backend.schemas.recommendation import RecommendationGenerateRequest
from piios_backend.services.recommendation_mvp import RecommendationMVPService


client = TestClient(app)


def test_wave3_generate_demo_reconciles_usd_5000_and_actions() -> None:
    service = RecommendationMVPService()
    result = service.generate(
        RecommendationGenerateRequest(
            investable_amount=5000.0,
            market_data_mode="development_seed",
            use_demo_portfolio=True,
        )
    )

    assert abs(result.allocation_total - 5000.0) <= 1.0
    actionable = [r for r in result.recommendations if r.action in {"BUY", "ADD"}]
    assert len(actionable) >= 2
    assert all(r.proposed_allocation >= 0 for r in actionable)


def test_wave3_missing_data_does_not_force_all_research() -> None:
    service = RecommendationMVPService()

    def _unavailable(_ticker: str):
        return None

    service._fetch_live_snapshot = _unavailable  # type: ignore[method-assign]
    result = service.generate(
        RecommendationGenerateRequest(
            investable_amount=5000.0,
            market_data_mode="auto",
            use_demo_portfolio=True,
        )
    )
    actionable = [r for r in result.recommendations if r.action in {"BUY", "ADD"}]
    assert len(actionable) >= 2
    assert result.market_data_mode in {"DEVELOPMENT_SEED", "MIXED", "CACHED"}


def test_wave3_invalid_mode_raises() -> None:
    service = RecommendationMVPService()
    try:
        service.generate(
            RecommendationGenerateRequest(
                investable_amount=5000.0,
                market_data_mode="nope",
                use_demo_portfolio=True,
            )
        )
    except ValueError as exc:
        assert "market_data_mode" in str(exc)
    else:
        assert False, "expected ValueError"


def test_wave3_route_generate_success_and_contract_fields() -> None:
    response = client.post(
        "/api/v1/recommendations/generate",
        json={
            "investable_amount": 5000,
            "market_data_mode": "development_seed",
            "use_demo_portfolio": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["advisory_only"] is True
    assert abs(payload["allocation_total"] - 5000.0) <= 1.0
    assert "recommendations" in payload
    assert payload["market_data_mode"] in {"DEVELOPMENT_SEED", "MIXED", "CACHED", "LIVE", "UNAVAILABLE"}


def test_wave3_route_generate_missing_portfolio() -> None:
    response = client.post(
        "/api/v1/recommendations/generate",
        json={
            "portfolio_snapshot_id": "missing",
            "investable_amount": 5000,
            "market_data_mode": "development_seed",
        },
    )
    assert response.status_code == 422


def test_wave3_route_demo_exists() -> None:
    response = client.post("/api/v1/recommendations/demo")
    assert response.status_code == 200
    payload = response.json()
    assert abs(payload["allocation_total"] - 5000.0) <= 1.0
