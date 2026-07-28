"""Smoke tests: every page must render without raising, under three
conditions the frontend is required to handle gracefully — a healthy
backend, a fully unreachable backend, and an empty-but-successful backend.
Uses streamlit.testing.v1.AppTest, which executes each page script directly.
"""
from pathlib import Path

import pytest
import requests
from streamlit.testing.v1 import AppTest

DASHBOARD_ROOT = Path(__file__).resolve().parents[1]

RECOMMENDATION_PAYLOAD = {
    "recommendation_id": "R1", "ticker": "AVGO", "thesis_id": None, "bucket": None,
    "portfolio_bucket": "Tactical Opportunities", "bull_case": "b", "bear_case": "b",
    "why_now": "n", "why_not_now": "n", "thesis_invalidation_trigger": "t",
    "position_size_suggestion": "2%", "time_horizon": "6mo", "confidence_score": 80.0,
    "portfolio_fit_score": 70.0, "data_freshness_timestamp": "t", "source_documents": [],
    "source_links": [], "rationale": "r", "data_source": "internal", "model_version": "v1",
    "status": "PENDING_REVIEW", "created_at": "t1", "updated_at": "t2", "approved_by": None,
    "advisory_only": True,
}

HOLDING_PAYLOAD = {
    "holding_id": "H1", "ticker": "NVDA", "name": "Nvidia", "quantity": 10, "market_value": 1000.0,
    "bucket": "Strategic Alpha", "geography": "US", "currency": "USD", "asset_class": "Equity",
    "sector": "Technology", "theme": "AI",
}

FIXTURES = {
    "/portfolio": [{"snapshot_id": "S1", "owner": "sushil", "total_value": 1000.0, "holdings": [HOLDING_PAYLOAD]}],
    "/portfolio/targets": {"targets": {"Equity": 60}, "thresholds": {"Equity": 5}},
    "/portfolio/drift": {"generated_at": "t", "items": [{
        "dimension": "asset_class", "key": "Equity", "target_percentage": 60.0, "actual_percentage": 65.0,
        "drift_amount": 5.0, "drift_percentage": 5.0, "severity": "HIGH", "recommended_action": "Trim equity",
        "advisory_only": True,
    }]},
    "/holdings": [HOLDING_PAYLOAD],
    "/watchlist": [{"watchlist_id": "W1", "ticker": "TSLA", "note": "watch", "bucket": None}],
    "/family/portfolios": {"households": [{"member_id": "M1", "member_name": "A", "relation": "self", "base_currency": "USD"}]},
    "/portfolio/net-worth": {"owner": "sushil", "total_assets": 100.0, "total_liabilities": 10.0, "net_worth": 90.0,
                              "breakdown": [{"category": "Cash", "value": 10.0}]},
    "/portfolio/allocation": {"total_value": 100.0, "items": [{"dimension": "asset_class", "key": "Equity", "market_value": 60.0, "percentage": 60.0}]},
    "/portfolio/currency-exposure": {"total_value": 100.0, "items": [{"currency": "USD", "market_value": 100.0, "percentage": 100.0}]},
    "/ips/constraints": {"constraints": [{"constraint_id": "C1", "name": "Max Equity", "rule_type": "max_pct",
                                           "threshold_value": 70.0, "severity": "HIGH", "enabled": True}]},
    "/instruments": {"instruments": [{"instrument_id": "I1", "ticker": "NVDA", "name": "Nvidia", "asset_class": "Equity",
                                       "currency": "USD", "exchange": "NASDAQ", "data_source": "internal"}]},
    "/data-trust/hierarchy": {"hierarchy": [{"source_id": "D1", "source_name": "Internal", "trust_tier": "TIER_1",
                                              "score": 95.0, "freshness_sla_hours": 24}]},
    "/recommendations": [RECOMMENDATION_PAYLOAD],
    "/recommendations/queue": {"items": [RECOMMENDATION_PAYLOAD]},
    "/recommendations/top": [{"ticker": "AVGO", "sector": "Tech", "score": 80.0, "daily_pct": 1.0, "weekly_pct": 2.0,
                               "close": 100.0, "volume_ratio": 1.2, "recommended_action": "BUY"}],
    "/tactical-signals": [{"signal_id": "T1", "ticker": "AVGO", "bucket": None, "status": "ACTIVE",
                            "entry_zone": "100-105", "invalidation": "<95", "target": "120", "advisory_only": True}],
    "/risk": {"max_position_pct": 5, "max_tactical_pct": 10, "max_single_ticker_pct": 7, "advisory_only": True},
    "/identity/resolution-issues": [],
    "/identity/shadow/diagnostics": {"enabled": False, "checked_records": 0, "unresolved_records": 0, "items": []},
    "/research": {"items": []},
    "/journal": [],
    "/theses": [],
    "/scores": {},
    "/health": {"status": "ok", "product": "PIIOS"},
}


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data
        self.text = str(json_data) if json_data is not None else ""
        self.content = b"x" if json_data is not None else b""

    def json(self):
        return self._json_data


# Endpoints considered "down" in partial-backend mode: risk and identity
# resolution issues are unavailable, everything else responds normally.
_PARTIAL_MODE_DOWN_PATHS = {"/risk", "/identity/resolution-issues"}


def _fixture_router(mode):
    def _fake_request(method, url, **kw):
        if mode == "unreachable":
            raise requests.exceptions.ConnectionError("no backend")
        path = url.split("/api/v1", 1)[-1]
        if path == "" or path == "/":
            path = "/health"
        if mode == "partial" and path in _PARTIAL_MODE_DOWN_PATHS:
            return _FakeResponse(500, {"detail": "temporarily unavailable"})
        if mode == "malformed":
            # Return a shape missing the fields every parser expects, on every path.
            return _FakeResponse(200, {"unexpected_field": True})
        if mode == "empty":
            data = [] if isinstance(FIXTURES.get(path), list) else {}
        else:
            data = FIXTURES.get(path, {})
        return _FakeResponse(200, data)
    return _fake_request


PAGES = [
    "Home.py",
    "pages/01_Portfolio.py",
    "pages/07_Risk_Console.py",
    "pages/21_Recommendation_Review.py",
    "pages/22_Decisions.py",
    "pages/23_Governance.py",
    "pages/24_Rebalancing.py",
    "pages/25_Performance.py",
    "pages/26_Settings.py",
    "pages/27_Future_Modules.py",
]


@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("mode", ["healthy", "unreachable", "empty", "partial", "malformed"])
def test_page_renders_without_exception(monkeypatch, page, mode):
    monkeypatch.setattr(requests, "request", _fixture_router(mode))
    at = AppTest.from_file(str(DASHBOARD_ROOT / page))
    at.run(timeout=30)
    assert not at.exception, f"{page} ({mode}) raised: {[str(e) for e in at.exception]}"
