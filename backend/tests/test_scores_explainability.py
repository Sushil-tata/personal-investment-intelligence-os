from fastapi.testclient import TestClient

from piios_backend.main import app
from piios_backend.services.live_feeds import live_feeds

client = TestClient(app)


def test_scores_explainability_endpoint_shape(monkeypatch) -> None:
    monkeypatch.setattr(live_feeds, "_can_attempt", lambda: False)
    response = client.get("/api/v1/scores/explainability", params={"limit": 5})
    assert response.status_code == 200

    payload = response.json()
    assert "items" in payload
    assert "as_of" in payload
    assert isinstance(payload["items"], list)
    assert len(payload["items"]) <= 5

    if payload["items"]:
        first = payload["items"][0]
        required_keys = {
            "ticker",
            "sector",
            "quality",
            "value",
            "momentum",
            "financial_health",
            "composite",
            "reason_for_ranking",
            "top_positive_contributors",
            "top_negative_contributors",
            "sector_percentile",
            "universe_percentile",
            "missing_data_flags",
        }
        assert required_keys.issubset(first.keys())
        assert len(first["top_positive_contributors"]) <= 5
        assert len(first["top_negative_contributors"]) <= 5
        assert isinstance(first["missing_data_flags"], list)
