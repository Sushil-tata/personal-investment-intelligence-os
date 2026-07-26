from fastapi.testclient import TestClient

from piios_backend.main import app

client = TestClient(app)


def test_root_mentions_advisory_boundary() -> None:
    response = client.get("/")
    assert response.status_code == 200
    text = response.json()["boundary"].lower()
    assert "advisory-only" in text
    assert "no broker integration" in text


def test_recommendations_are_advisory_only() -> None:
    response = client.get("/api/v1/recommendations")
    assert response.status_code == 200
    assert all(item["advisory_only"] for item in response.json())
