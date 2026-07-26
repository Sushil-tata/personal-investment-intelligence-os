from fastapi.testclient import TestClient

from piios_backend.main import app

client = TestClient(app)


REQUIRED_PATHS = [
    "/api/v1/portfolio",
    "/api/v1/portfolio/targets",
    "/api/v1/portfolio/drift",
    "/api/v1/portfolio/net-worth",
    "/api/v1/portfolio/allocation",
    "/api/v1/portfolio/currency-exposure",
    "/api/v1/family/portfolios",
    "/api/v1/ips/constraints",
    "/api/v1/instruments",
    "/api/v1/data-trust/hierarchy",
    "/api/v1/holdings",
    "/api/v1/watchlist",
    "/api/v1/research",
    "/api/v1/scores",
    "/api/v1/scores/explainability",
    "/api/v1/recommendations",
    "/api/v1/recommendations/top",
    "/api/v1/theses",
    "/api/v1/theses/export",
    "/api/v1/tactical-signals",
    "/api/v1/risk",
    "/api/v1/journal",
]


def test_required_routes_available() -> None:
    for path in REQUIRED_PATHS:
        response = client.get(path)
        assert response.status_code == 200


def test_graph_routes_available() -> None:
    run = client.post("/api/v1/graph/run", json={"ticker": "NVDA", "requested_by": "test", "approve": False})
    assert run.status_code == 200
    run_id = run.json()["run_id"]
    status = client.get("/api/v1/graph/status", params={"run_id": run_id})
    assert status.status_code == 200
