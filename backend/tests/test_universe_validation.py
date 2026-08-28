from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from piios_backend.services.recommendation_mvp import RecommendationMVPService
from scripts import validate_universe


class _FakeTicker:
    def __init__(self, info: dict, history: pd.DataFrame) -> None:
        self.info = info
        self._history = history

    def history(self, **_kwargs) -> pd.DataFrame:
        return self._history


def _history(daily_value: float) -> pd.DataFrame:
    price = 100.0
    return pd.DataFrame(
        {"Adj Close": [price, price], "Close": [price, price], "Volume": [daily_value / price] * 2},
        index=pd.DatetimeIndex([datetime.now(timezone.utc), datetime.now(timezone.utc)]),
    )


def _validate(monkeypatch, *, market_cap=12_000_000_000, currency="USD", daily_value=20_000_000):
    info = {
        "marketCap": market_cap,
        "currency": currency,
        "quoteType": "EQUITY",
        "regularMarketPrice": 100.0,
        "trailingPE": 20.0,
        "totalDebt": 1.0,
    }
    monkeypatch.setattr(validate_universe.yf, "Ticker", lambda _ticker: _FakeTicker(info, _history(daily_value)))
    return validate_universe.validate_ticker("TEST", "US")


def test_validator_marks_complete_liquid_ticker_eligible(monkeypatch) -> None:
    result = _validate(monkeypatch)

    assert result["status"] == validate_universe.VALID
    assert result["cap_tier"] == "LARGE"
    assert result["liquidity_status"] == "PASS"
    assert result["eligibility_status"] == "ELIGIBLE"
    assert result["eligible_for_screening"] is True


def test_validator_marks_missing_cap_data_pending(monkeypatch) -> None:
    result = _validate(monkeypatch, market_cap=None)

    assert result["cap_tier"] is None
    assert result["eligibility_status"] == "DATA_PENDING_MARKET_CAP"
    assert result["eligible_for_screening"] is False


def test_validator_rejects_below_threshold_liquidity(monkeypatch) -> None:
    result = _validate(monkeypatch, daily_value=2_000_000)

    assert result["liquidity_status"] == "FAIL"
    assert result["eligibility_status"] == "INELIGIBLE_LIQUIDITY"
    assert result["eligible_for_screening"] is False


def test_validator_does_not_guess_cross_currency_cap_tier(monkeypatch) -> None:
    result = _validate(monkeypatch, currency="SGD")

    assert result["cap_tier"] is None
    assert result["eligibility_status"] == "DATA_PENDING_MARKET_CAP_CURRENCY"
    assert result["eligible_for_screening"] is False


def test_resume_settles_only_definitive_results() -> None:
    assert validate_universe._settled_row({"status": "VALID", "reason": None}) is True
    assert validate_universe._settled_row({"status": "INVALID", "reason": "invalid_symbol_format"}) is True
    assert validate_universe._settled_row({"status": "STALE_DELISTED", "reason": "empty_history"}) is True
    assert validate_universe._settled_row({"status": "PROVIDER_UNAVAILABLE", "reason": "rate limited"}) is False


def test_discovery_honors_validator_eligibility() -> None:
    service = RecommendationMVPService()
    service._load_universe_file = lambda _market: ["PASS", "ILLIQUID", "PENDING"]  # type: ignore[method-assign]
    service._load_universe_validation_rows = lambda: {  # type: ignore[method-assign]
        ("US", "PASS"): {"status": "VALID", "eligible_for_screening": True},
        ("US", "ILLIQUID"): {
            "status": "VALID",
            "eligible_for_screening": False,
            "eligibility_status": "INELIGIBLE_LIQUIDITY",
            "missing_fields": [],
        },
        ("US", "PENDING"): {
            "status": "VALID",
            "eligible_for_screening": False,
            "eligibility_status": "DATA_PENDING_MARKET_CAP",
            "missing_fields": ["marketCap"],
        },
    }

    candidates, universe_summary, screening_summary, excluded = service._discover_candidates(["US"])

    assert [candidate.ticker for candidate in candidates] == ["PASS"]
    assert universe_summary["markets"]["US"]["eligible"] == 1
    assert screening_summary["partial_by_market"]["US"] == 1
    assert {row["ticker"] for row in excluded} == {"ILLIQUID", "PENDING"}