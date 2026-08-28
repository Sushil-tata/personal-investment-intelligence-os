from fastapi.testclient import TestClient
from fastapi import FastAPI

from piios_backend.api.routes import recommendations, scores
from piios_backend.services.live_feeds import QuoteSnapshot, _advisory_action, live_feeds


def _test_client() -> TestClient:
    app = FastAPI()
    app.include_router(recommendations.router, prefix="/api/v1")
    app.include_router(scores.router, prefix="/api/v1")
    return TestClient(app)


def test_queue_endpoint_exists() -> None:
    client = _test_client()
    response = client.get("/api/v1/recommendations/queue")
    assert response.status_code == 200
    assert "items" in response.json()


def test_status_transition_to_pending_review() -> None:
    client = _test_client()
    response = client.patch(
        "/api/v1/recommendations/r1/status",
        json={"status": "PENDING_REVIEW", "approved_by": "analyst_1"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "PENDING_REVIEW"


def test_visible_recommendations_only_approved() -> None:
    client = _test_client()
    client.patch("/api/v1/recommendations/r1/status", json={"status": "DRAFT"})
    response = client.get("/api/v1/recommendations")
    assert response.status_code == 200
    assert response.json() == []
    client.patch("/api/v1/recommendations/r1/status", json={"status": "APPROVED", "approved_by": "reviewer"})


def test_top_recommendations_endpoint_exists() -> None:
    client = _test_client()
    response = client.get("/api/v1/recommendations/top")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_top_recommendations_respects_limit(monkeypatch) -> None:
    client = _test_client()
    sample = [
        {"ticker": "AAA", "sector": "Consumption", "score": 70.0, "daily_pct": 0.1, "weekly_pct": 0.2, "close": 100.0, "volume_ratio": 1.0, "recommended_action": "Advisory hold"},
        {"ticker": "BBB", "sector": "Consumption", "score": 69.0, "daily_pct": 0.1, "weekly_pct": 0.2, "close": 100.0, "volume_ratio": 1.0, "recommended_action": "Advisory hold"},
        {"ticker": "CCC", "sector": "Tech", "score": 68.0, "daily_pct": 0.1, "weekly_pct": 0.2, "close": 100.0, "volume_ratio": 1.0, "recommended_action": "Advisory hold"},
    ]
    monkeypatch.setattr(
        live_feeds,
        "top_recommendations",
        lambda limit=50, sector=None, market=None: [
            row for row in sample if sector is None or row["sector"].lower() == sector.lower()
        ][:limit],
    )
    response = client.get("/api/v1/recommendations/top", params={"limit": 2})
    assert response.status_code == 200
    assert len(response.json()) <= 2


def test_top_recommendations_filters_by_sector(monkeypatch) -> None:
    client = _test_client()
    sample = [
        {"ticker": "AAA", "sector": "Consumption", "score": 70.0, "daily_pct": 0.1, "weekly_pct": 0.2, "close": 100.0, "volume_ratio": 1.0, "recommended_action": "Advisory hold"},
        {"ticker": "BBB", "sector": "Consumption", "score": 69.0, "daily_pct": 0.1, "weekly_pct": 0.2, "close": 100.0, "volume_ratio": 1.0, "recommended_action": "Advisory hold"},
        {"ticker": "CCC", "sector": "Tech", "score": 68.0, "daily_pct": 0.1, "weekly_pct": 0.2, "close": 100.0, "volume_ratio": 1.0, "recommended_action": "Advisory hold"},
    ]
    monkeypatch.setattr(
        live_feeds,
        "top_recommendations",
        lambda limit=50, sector=None, market=None: [
            row for row in sample if sector is None or row["sector"].lower() == sector.lower()
        ][:limit],
    )
    response = client.get("/api/v1/recommendations/top", params={"limit": 50, "sector": "Consumption"})
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert all(row["sector"] == "Consumption" for row in rows)


def test_advisory_action_rules() -> None:
    assert _advisory_action(82, 1.5, 3.0, 1.2) == "Advisory buy candidate"
    assert _advisory_action(66, 0.2, 0.5, 1.1) == "Advisory accumulate"
    assert _advisory_action(48, 0.0, 0.0, 1.0) == "Advisory reduce / exit watch"
    assert _advisory_action(35, -1.2, -3.0, 0.8) == "Advisory sell candidate"


def test_scores_include_sector_and_action(monkeypatch) -> None:
    client = _test_client()
    monkeypatch.setattr(
        live_feeds,
        "quote",
        lambda ticker: QuoteSnapshot(ticker=ticker, close=110.0, prev_close=100.0),
    )

    response = client.get("/api/v1/scores")
    assert response.status_code == 200

    payload = response.json()
    first = payload["stock_scores"][0]
    assert "sector" in first
    assert "recommended_action" in first
    assert first["recommended_action"] == "Advisory buy candidate"
