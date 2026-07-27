import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from piios_backend.main import app
from piios_backend.graph.workflow import graph_registry

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


@pytest.fixture
def isolated_graph_fallback(tmp_path, monkeypatch):
    tracked_file = Path(__file__).resolve().parents[1] / "data" / "mock" / "graph_runs_fallback.json"
    before = tracked_file.read_text(encoding="utf-8") if tracked_file.exists() else ""

    fallback_file = tmp_path / "graph_runs_fallback_routes.json"
    monkeypatch.setattr(graph_registry.persistence, "file_path", fallback_file)
    monkeypatch.setattr(
        "piios_backend.services.graph_persistence.Session",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("forced-db-failure")),
    )

    yield fallback_file, tracked_file, before

    after = tracked_file.read_text(encoding="utf-8") if tracked_file.exists() else ""
    assert after == before


def test_graph_routes_available(isolated_graph_fallback) -> None:
    fallback_file, _, _ = isolated_graph_fallback

    run = client.post("/api/v1/graph/run", json={"ticker": "NVDA", "requested_by": "test", "approve": False})
    assert run.status_code == 200
    run_id = run.json()["run_id"]

    rows = json.loads(fallback_file.read_text(encoding="utf-8"))
    assert len(rows) >= 1
    assert rows[-1]["run_id"] == run_id

    status = client.get("/api/v1/graph/status", params={"run_id": run_id})
    assert status.status_code == 200
