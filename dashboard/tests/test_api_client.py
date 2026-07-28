"""Tests for the dedicated API client layer: error handling, empty-state
detection, and typed model parsing. No network calls are made — the
`requests` layer is monkeypatched with fake responses."""
import requests

from lib import api_client as api


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.content = b"x" if json_data is not None else b""

    def json(self):
        if self._json_data is None:
            raise ValueError("no json")
        return self._json_data


def test_get_json_success(monkeypatch):
    monkeypatch.setattr(requests, "request", lambda method, url, **kw: _FakeResponse(200, {"a": 1}))
    result = api.get_json("/whatever")
    assert result.ok is True
    assert result.data == {"a": 1}
    assert result.error is None


def test_get_json_connection_error_is_caught(monkeypatch):
    def _raise(*a, **kw):
        raise requests.exceptions.ConnectionError("nope")
    monkeypatch.setattr(requests, "request", _raise)
    result = api.get_json("/whatever")
    assert result.ok is False
    assert "Could not reach" in result.error


def test_get_json_timeout_is_caught(monkeypatch):
    def _raise(*a, **kw):
        raise requests.exceptions.Timeout("slow")
    monkeypatch.setattr(requests, "request", _raise)
    result = api.get_json("/whatever")
    assert result.ok is False
    assert "timed out" in result.error


def test_get_json_http_error_status_is_surfaced(monkeypatch):
    monkeypatch.setattr(requests, "request", lambda method, url, **kw: _FakeResponse(404, text="not found"))
    result = api.get_json("/missing")
    assert result.ok is False
    assert result.status_code == 404
    assert "404" in result.error


def test_api_result_is_empty_for_empty_list():
    result = api.ApiResult(ok=True, data=[])
    assert result.is_empty is True


def test_api_result_is_empty_for_none():
    result = api.ApiResult(ok=True, data=None)
    assert result.is_empty is True


def test_api_result_not_empty_for_populated_list():
    result = api.ApiResult(ok=True, data=[1, 2, 3])
    assert result.is_empty is False


def test_api_result_failed_call_is_not_considered_empty():
    result = api.ApiResult(ok=False, error="boom")
    assert result.is_empty is False


def test_get_holdings_parses_into_typed_models(monkeypatch):
    payload = [{
        "holding_id": "H1", "ticker": "NVDA", "name": "Nvidia", "quantity": 10, "market_value": 1000.0,
        "bucket": "Strategic Alpha", "geography": "US", "currency": "USD", "asset_class": "Equity",
        "sector": "Technology", "theme": "AI",
    }]
    monkeypatch.setattr(requests, "request", lambda method, url, **kw: _FakeResponse(200, payload))
    result = api.get_holdings()
    assert result.ok is True
    assert len(result.data) == 1
    holding = result.data[0]
    assert holding.ticker == "NVDA"
    assert holding.market_value == 1000.0
    assert holding.bucket == "Strategic Alpha"


def test_get_recommendations_parses_status_and_scores(monkeypatch):
    payload = [{
        "recommendation_id": "R1", "ticker": "AVGO", "thesis_id": None, "bucket": None,
        "portfolio_bucket": "Tactical Opportunities", "bull_case": "bull", "bear_case": "bear",
        "why_now": "now", "why_not_now": "not now", "thesis_invalidation_trigger": "trigger",
        "position_size_suggestion": "2%", "time_horizon": "6mo", "confidence_score": 80.0,
        "portfolio_fit_score": 70.0, "data_freshness_timestamp": "2026-07-01T00:00:00Z",
        "source_documents": [], "source_links": [], "rationale": "because", "data_source": "internal",
        "model_version": "v1", "status": "PENDING_REVIEW", "created_at": "t1", "updated_at": "t2",
        "approved_by": None, "advisory_only": True,
    }]
    monkeypatch.setattr(requests, "request", lambda method, url, **kw: _FakeResponse(200, payload))
    result = api.get_recommendations()
    assert result.ok is True
    reco = result.data[0]
    assert reco.status == "PENDING_REVIEW"
    assert reco.confidence_score == 80.0


def test_malformed_response_shape_is_reported_not_crashed(monkeypatch):
    # Missing required "items" key should surface as a friendly error, not a raw KeyError traceback.
    monkeypatch.setattr(requests, "request", lambda method, url, **kw: _FakeResponse(200, {"unexpected": True}))
    result = api.get_portfolio_drift()
    assert result.ok is False
    assert "Unexpected response shape" in result.error


def test_update_recommendation_status_sends_patch(monkeypatch):
    captured = {}

    def _fake_request(method, url, **kw):
        captured["method"] = method
        captured["json"] = kw.get("json")
        return _FakeResponse(200, {
            "recommendation_id": "R1", "ticker": "AVGO", "thesis_id": None, "bucket": None,
            "portfolio_bucket": "Tactical Opportunities", "bull_case": "b", "bear_case": "b",
            "why_now": "n", "why_not_now": "n", "thesis_invalidation_trigger": "t",
            "position_size_suggestion": "2%", "time_horizon": "6mo", "confidence_score": 80.0,
            "portfolio_fit_score": 70.0, "data_freshness_timestamp": "t", "source_documents": [],
            "source_links": [], "rationale": "r", "data_source": "internal", "model_version": "v1",
            "status": "APPROVED", "created_at": "t1", "updated_at": "t2", "approved_by": "sushil",
            "advisory_only": True,
        })

    monkeypatch.setattr(requests, "request", _fake_request)
    result = api.update_recommendation_status("R1", "APPROVED", "sushil")
    assert result.ok is True
    assert captured["method"] == "PATCH"
    assert captured["json"] == {"status": "APPROVED", "approved_by": "sushil"}
    assert result.data.status == "APPROVED"
