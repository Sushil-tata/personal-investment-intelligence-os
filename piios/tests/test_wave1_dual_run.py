from __future__ import annotations

from decimal import Decimal

from piios_backend.api.routes.portfolio_layers import get_net_worth, run_portfolio_dual_run_verification
from piios_backend.core.config import settings
from piios_backend.services.portfolio_dual_run import compare_metrics, run_dual_run_verification
from piios_backend.services.portfolio_layers import PortfolioLayersService


def _baseline_payload() -> dict:
    return {
        "total_value": Decimal("100.00"),
        "cash_value": Decimal("10.00"),
        "listed_equity_value": Decimal("90.00"),
        "country_exposure_listing": {
            "India": {"value_reporting": Decimal("40.00"), "weight_pct": Decimal("40.00")},
            "United States": {"value_reporting": Decimal("60.00"), "weight_pct": Decimal("60.00")},
        },
        "country_exposure_economic": {
            "India": {"value_reporting": Decimal("35.00"), "weight_pct": Decimal("35.00")},
            "United States": {"value_reporting": Decimal("65.00"), "weight_pct": Decimal("65.00")},
        },
        "currency_exposure": {
            "USD": {"value_reporting": Decimal("60.00"), "weight_pct": Decimal("60.00")},
            "INR": {"value_reporting": Decimal("40.00"), "weight_pct": Decimal("40.00")},
        },
        "sector_exposure": {
            "Technology": {"value_reporting": Decimal("70.00"), "weight_pct": Decimal("70.00")},
            "Financials": {"value_reporting": Decimal("30.00"), "weight_pct": Decimal("30.00")},
        },
        "theme_exposure": {
            "AI": {"value_reporting": Decimal("50.00"), "weight_pct": Decimal("50.00")},
            "Core": {"value_reporting": Decimal("50.00"), "weight_pct": Decimal("50.00")},
        },
        "position_weights": {
            "AAPL:NASDAQ": Decimal("35.00"),
            "INFY:NSE": Decimal("65.00"),
        },
        "hhi": Decimal("0.5450"),
        "top_holdings": {
            "INFY:NSE": {"value_reporting": Decimal("65.00"), "weight_pct": Decimal("65.00")},
            "AAPL:NASDAQ": {"value_reporting": Decimal("35.00"), "weight_pct": Decimal("35.00")},
        },
        "proposed_trade_impact": {
            "proposed_amount": Decimal("5000.00"),
            "before_total_value": Decimal("100.00"),
            "after_total_value": Decimal("5100.00"),
            "position_weight_delta": {
                "NVDA:NASDAQ": Decimal("90.00"),
                "INFY:NSE": Decimal("-63.73"),
                "AAPL:NASDAQ": Decimal("-26.27"),
            },
        },
    }


def test_dual_run_exact_parity() -> None:
    legacy = _baseline_payload()
    new = _baseline_payload()

    result = compare_metrics(legacy, new, Decimal("0.01"), Decimal("0.01"))
    assert result["status"] == "match"
    assert result["mismatch_count"] == 0


def test_dual_run_accepts_rounding_difference() -> None:
    legacy = _baseline_payload()
    new = _baseline_payload()
    new["sector_exposure"]["Technology"]["weight_pct"] = Decimal("70.01")

    result = compare_metrics(legacy, new, Decimal("0.01"), Decimal("0.01"))
    assert result["status"] == "match"


def test_dual_run_rejects_classification_mismatch() -> None:
    legacy = _baseline_payload()
    new = _baseline_payload()
    del new["theme_exposure"]["Core"]

    result = compare_metrics(legacy, new, Decimal("0.01"), Decimal("0.01"))
    assert result["status"] == "mismatch"
    assert any(item["mismatch_type"] == "classification_mismatch" for item in result["mismatches"])


def test_dual_run_rejects_missing_holding() -> None:
    legacy = _baseline_payload()
    new = _baseline_payload()
    del new["position_weights"]["INFY:NSE"]

    result = compare_metrics(legacy, new, Decimal("0.01"), Decimal("0.01"))
    assert result["status"] == "mismatch"
    assert any(item["path"] == "position_weights.keys" for item in result["mismatches"])


def test_dual_run_rejects_fx_difference() -> None:
    legacy = _baseline_payload()
    new = _baseline_payload()
    new["total_value"] = Decimal("101.50")

    result = compare_metrics(legacy, new, Decimal("0.01"), Decimal("0.01"))
    assert result["status"] == "mismatch"
    assert any(item["metric"] == "total_value" for item in result["mismatches"])


def test_dual_run_rejects_proposed_trade_mismatch() -> None:
    legacy = _baseline_payload()
    new = _baseline_payload()
    new["proposed_trade_impact"]["position_weight_delta"]["NVDA:NASDAQ"] = Decimal("89.95")

    result = compare_metrics(legacy, new, Decimal("0.01"), Decimal("0.01"))
    assert result["status"] == "mismatch"
    assert any("proposed_trade_impact.position_weight_delta" in item["metric"] for item in result["mismatches"])


def test_dual_run_endpoint_non_invasive() -> None:
    original_enabled = settings.portfolio_dual_run_enabled
    original_env = settings.env
    settings.portfolio_dual_run_enabled = True
    settings.env = "test"
    try:
        service = PortfolioLayersService(session=None)  # type: ignore[arg-type]
        legacy_payload = service.net_worth().model_dump()
        route_payload = get_net_worth(service=service).model_dump()
        assert route_payload == legacy_payload

        verify_payload = run_portfolio_dual_run_verification()
        assert verify_payload["enabled"] is True
        assert "report" in verify_payload
        assert sorted(verify_payload["report"]["metrics_compared"]) == sorted([
            "total_value",
            "cash_value",
            "listed_equity_value",
            "country_exposure_listing",
            "country_exposure_economic",
            "currency_exposure",
            "sector_exposure",
            "theme_exposure",
            "position_weights",
            "hhi",
            "top_holdings",
            "proposed_trade_impact",
        ])
    finally:
        settings.portfolio_dual_run_enabled = original_enabled
        settings.env = original_env


def test_dual_run_runtime_report_generation() -> None:
    report = run_dual_run_verification()
    assert "mismatch_count" in report
    assert "metrics_compared" in report
