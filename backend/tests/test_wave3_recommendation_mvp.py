from __future__ import annotations

from copy import deepcopy
import random

from fastapi import FastAPI
from piios_backend.schemas.portfolio import Holding
from piios_backend.schemas.recommendation import RecommendationGenerateRequest
from piios_backend.api.routes import recommendations as recommendations_routes
from piios_backend.services.recommendation_mvp import CandidateInstrument, MarketSnapshot, RecommendationMVPService


def test_wave3_generate_demo_reconciles_usd_5000_and_actions() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0 if from_ccy.upper() == to_ccy.upper() else 0.012  # type: ignore[method-assign]
    result = service.generate(
        RecommendationGenerateRequest(
            investable_amount=5000.0,
            market_data_mode="development_seed",
            use_demo_portfolio=True,
        )
    )

    assert 0.0 <= result.allocation_total <= 5000.0
    assert abs((result.allocation_total + (result.residual_cash or 0.0)) - 5000.0) <= 1.0
    actionable = [r for r in result.recommendations if r.action in {"BUY", "ADD"}]
    assert all(r.proposed_allocation >= 0 for r in actionable)


def test_wave3_missing_data_does_not_force_all_research() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0 if from_ccy.upper() == to_ccy.upper() else 0.012  # type: ignore[method-assign]

    candidates = [
        CandidateInstrument(
            ticker="AAA",
            instrument_name="AAA",
            portfolio_role="UNAVAILABLE",
            market="US",
            exchange="US",
            issuer_country="United States",
            trading_currency="USD",
            instrument_type="Equity",
            geography="US",
            sector=None,
            risk_band=None,
        ),
        CandidateInstrument(
            ticker="BBB",
            instrument_name="BBB",
            portfolio_role="UNAVAILABLE",
            market="US",
            exchange="US",
            issuer_country="United States",
            trading_currency="USD",
            instrument_type="Equity",
            geography="US",
            sector=None,
            risk_band=None,
        ),
    ]
    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        candidates,
        {"markets": {"US": {"total_seed": 2, "eligible": 2, "partial": 0, "ineligible": 0}}, "total_candidates": 2, "eligible_candidates": 2, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"US": 2}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )

    def _unavailable(_candidate, _base_currency: str):
        return None

    service._fetch_live_snapshot = _unavailable  # type: ignore[method-assign]
    result = service.generate(
        RecommendationGenerateRequest(
            investable_amount=5000.0,
            market_data_mode="live",
            use_demo_portfolio=True,
            eligible_markets=["US"],
        )
    )
    actionable = [r for r in result.recommendations if r.action in {"BUY", "ADD"}]
    assert len(actionable) == 0
    assert result.allocation_total == 0.0
    assert result.residual_cash == 5000.0
    assert result.market_data_mode == "UNAVAILABLE"


def test_wave3_real_runtime_quality_growth_not_seeded_when_missing() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0 if from_ccy.upper() == to_ccy.upper() else 0.012  # type: ignore[method-assign]

    candidate = CandidateInstrument(
        ticker="TEST1",
        instrument_name="Test One",
        portfolio_role="UNAVAILABLE",
        market="US",
        exchange="US",
        issuer_country="United States",
        trading_currency="USD",
        instrument_type="Equity",
        geography="US",
        sector=None,
        risk_band=None,
    )

    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        [candidate],
        {"markets": {"US": {"total_seed": 1, "eligible": 1, "partial": 0, "ineligible": 0}}, "total_candidates": 1, "eligible_candidates": 1, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"US": 1}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )

    service._fetch_live_snapshot = lambda _candidate, _base_currency: MarketSnapshot(  # type: ignore[method-assign]
        ticker="TEST1",
        provider="yfinance",
        mode="LIVE",
        as_of="2026-08-10T00:00:00Z",
        is_stale=False,
        fallback_reason=None,
        seeded_input=False,
        latest_price=100.0,
        daily_return_pct=0.2,
        return_1m_pct=0.8,
        return_3m_pct=2.4,
        return_6m_pct=4.0,
        return_12m_pct=8.0,
        realized_volatility=0.05,
        drawdown_pct=-8.0,
        distance_from_52w_high_pct=-4.0,
        trading_currency="USD",
        sector="UNKNOWN",
        portfolio_role="UNAVAILABLE",
        quality_score=None,
        growth_score=None,
        fx_required=False,
        fx_available=True,
        fx_rate_to_base=1.0,
        missing_inputs=["quality", "growth"],
    )

    result = service.generate(
        RecommendationGenerateRequest(
            investable_amount=5000.0,
            market_data_mode="live",
            use_demo_portfolio=True,
            eligible_markets=["US"],
        )
    )

    target = next(r for r in result.recommendations if r.ticker == "TEST1")
    components = {c.name: c for c in target.components}
    assert components["quality"].value is None
    assert components["quality"].status == "UNAVAILABLE"
    assert components["growth"].value is None
    assert components["growth"].status == "UNAVAILABLE"


def test_wave3_fx_unavailable_blocks_cross_currency_actionable() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0 if from_ccy.upper() == to_ccy.upper() else 0.012  # type: ignore[method-assign]

    candidate = CandidateInstrument(
        ticker="XNS.NS",
        instrument_name="Cross Currency Test",
        portfolio_role="UNAVAILABLE",
        market="India",
        exchange="NSE",
        issuer_country="India",
        trading_currency="INR",
        instrument_type="Equity",
        geography="INDIA",
        sector=None,
        risk_band=None,
    )

    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        [candidate],
        {"markets": {"India": {"total_seed": 1, "eligible": 1, "partial": 0, "ineligible": 0}}, "total_candidates": 1, "eligible_candidates": 1, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"India": 1}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )

    service._fetch_live_snapshot = lambda _candidate, _base_currency: MarketSnapshot(  # type: ignore[method-assign]
        ticker="XNS.NS",
        provider="yfinance",
        mode="LIVE",
        as_of="2026-08-10T00:00:00Z",
        is_stale=False,
        fallback_reason=None,
        seeded_input=False,
        latest_price=1000.0,
        daily_return_pct=1.1,
        return_1m_pct=4.4,
        return_3m_pct=13.2,
        return_6m_pct=22.0,
        return_12m_pct=44.0,
        realized_volatility=0.03,
        drawdown_pct=-5.0,
        distance_from_52w_high_pct=-2.0,
        trading_currency="INR",
        sector="Technology",
        portfolio_role="GEOGRAPHIC_DIVERSIFIER",
        quality_score=75.0,
        growth_score=72.0,
        fx_required=True,
        fx_available=False,
        fx_rate_to_base=None,
        missing_inputs=["fx_rate"],
    )

    result = service.generate(
        RecommendationGenerateRequest(
            investable_amount=5000.0,
            market_data_mode="live",
            use_demo_portfolio=True,
            base_currency="USD",
            eligible_markets=["India"],
        )
    )

    target = next(r for r in result.recommendations if r.ticker == "XNS.NS")
    assert target.action in {"RESEARCH", "AVOID", "HOLD"}
    assert target.action not in {"BUY", "ADD"}
    assert any(l.code == "FX_UNAVAILABLE" for l in result.limitations)


def test_wave3_invalid_mode_raises() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0 if from_ccy.upper() == to_ccy.upper() else 0.012  # type: ignore[method-assign]
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


def _recommendations_test_client():
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(recommendations_routes.router, prefix="/api/v1")
    return TestClient(app)


def test_wave3_route_generate_success_and_contract_fields() -> None:
    client = _recommendations_test_client()
    response = client.post(
        "/api/v1/recommendations/generate",
        json={
            "investable_amount": 5000,
            "market_data_mode": "live",
            "use_demo_portfolio": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["advisory_only"] is True
    assert 0.0 <= payload["allocation_total"] <= 5000.0
    assert abs((payload["allocation_total"] + payload.get("residual_cash", 0.0)) - 5000.0) <= 1.0
    assert "recommendations" in payload
    assert payload["market_data_mode"] in {"MIXED", "CACHED", "LIVE", "UNAVAILABLE"}


def test_wave3_route_generate_rejects_demo_portfolio() -> None:
    client = _recommendations_test_client()
    response = client.post(
        "/api/v1/recommendations/generate",
        json={
            "investable_amount": 5000,
            "market_data_mode": "live",
            "use_demo_portfolio": True,
        },
    )
    assert response.status_code == 422


def test_wave3_route_generate_rejects_development_seed() -> None:
    client = _recommendations_test_client()
    response = client.post(
        "/api/v1/recommendations/generate",
        json={
            "investable_amount": 5000,
            "market_data_mode": "development_seed",
            "use_demo_portfolio": False,
        },
    )
    assert response.status_code == 422


def test_wave3_route_generate_requires_explicit_live_mode() -> None:
    client = _recommendations_test_client()
    for payload in (
        {"investable_amount": 5000, "use_demo_portfolio": False},
        {"investable_amount": 5000, "market_data_mode": "auto", "use_demo_portfolio": False},
    ):
        response = client.post("/api/v1/recommendations/generate", json=payload)
        assert response.status_code == 422
        assert "requires explicit market_data_mode='live'" in response.json()["detail"]


def test_wave3_route_generate_missing_portfolio() -> None:
    client = _recommendations_test_client()
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
    client = _recommendations_test_client()
    response = client.post("/api/v1/recommendations/demo")
    assert response.status_code == 200
    payload = response.json()
    assert 0.0 <= payload["allocation_total"] <= 5000.0
    assert abs((payload["allocation_total"] + payload.get("residual_cash", 0.0)) - 5000.0) <= 1.0


def test_wave3_low_evidence_security_is_not_buy() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0 if from_ccy.upper() == to_ccy.upper() else 0.012  # type: ignore[method-assign]

    candidate = CandidateInstrument(
        ticker="LOWEVID",
        instrument_name="Low Evidence",
        portfolio_role="UNAVAILABLE",
        market="US",
        exchange="US",
        issuer_country="United States",
        trading_currency="USD",
        instrument_type="Equity",
        geography="US",
        sector=None,
        risk_band=None,
    )

    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        [candidate],
        {"markets": {"US": {"total_seed": 1, "eligible": 1, "partial": 0, "ineligible": 0}}, "total_candidates": 1, "eligible_candidates": 1, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"US": 1}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )

    service._fetch_live_snapshot = lambda _candidate, _base_currency: MarketSnapshot(  # type: ignore[method-assign]
        ticker="LOWEVID",
        provider="yfinance",
        mode="LIVE",
        as_of="2026-08-10T00:00:00Z",
        is_stale=False,
        fallback_reason=None,
        seeded_input=False,
        latest_price=50.0,
        daily_return_pct=0.1,
        return_1m_pct=0.5,
        return_3m_pct=1.2,
        return_6m_pct=2.1,
        return_12m_pct=3.0,
        realized_volatility=0.12,
        drawdown_pct=-9.0,
        distance_from_52w_high_pct=-7.0,
        trading_currency="USD",
        sector=None,
        portfolio_role="UNAVAILABLE",
        quality_score=None,
        growth_score=None,
        fx_required=False,
        fx_available=True,
        fx_rate_to_base=1.0,
        missing_inputs=["quality", "growth", "valuation"],
        history_observations=70,
        raw_metrics={
            "return_3m_pct": 1.2,
            "return_6m_pct": 2.1,
            "return_12m_pct": 3.0,
            "realized_volatility": 0.12,
            "max_drawdown_pct": -9.0,
            "distance_from_52w_high_pct": -7.0,
            "sector": None,
        },
    )

    result = service.generate(
        RecommendationGenerateRequest(
            investable_amount=5000.0,
            market_data_mode="live",
            use_demo_portfolio=True,
            eligible_markets=["US"],
        )
    )

    target = next(r for r in result.recommendations if r.ticker == "LOWEVID")
    assert target.action in {"RESEARCH", "AVOID", "HOLD"}
    assert target.action not in {"BUY", "ADD"}


def test_wave3_valuation_missingness_is_preserved() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0 if from_ccy.upper() == to_ccy.upper() else 0.012  # type: ignore[method-assign]

    candidate = CandidateInstrument(
        ticker="VALMISS",
        instrument_name="Valuation Missing",
        portfolio_role="UNAVAILABLE",
        market="US",
        exchange="US",
        issuer_country="United States",
        trading_currency="USD",
        instrument_type="Equity",
        geography="US",
        sector="Technology",
        risk_band=None,
    )

    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        [candidate],
        {"markets": {"US": {"total_seed": 1, "eligible": 1, "partial": 0, "ineligible": 0}}, "total_candidates": 1, "eligible_candidates": 1, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"US": 1}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )

    service._fetch_live_snapshot = lambda _candidate, _base_currency: MarketSnapshot(  # type: ignore[method-assign]
        ticker="VALMISS",
        provider="yfinance",
        mode="LIVE",
        as_of="2026-08-10T00:00:00Z",
        is_stale=False,
        fallback_reason=None,
        seeded_input=False,
        latest_price=120.0,
        daily_return_pct=0.2,
        return_1m_pct=1.1,
        return_3m_pct=3.5,
        return_6m_pct=7.2,
        return_12m_pct=12.4,
        realized_volatility=0.18,
        drawdown_pct=-12.0,
        distance_from_52w_high_pct=-5.0,
        trading_currency="USD",
        sector="Technology",
        portfolio_role="UNAVAILABLE",
        quality_score=70.0,
        growth_score=68.0,
        fx_required=False,
        fx_available=True,
        fx_rate_to_base=1.0,
        missing_inputs=["valuation"],
        history_observations=252,
        raw_metrics={
            "returnOnEquity": 0.18,
            "operatingMargins": 0.24,
            "profitMargins": 0.20,
            "revenueGrowth": 0.12,
            "earningsGrowth": 0.11,
            "return_3m_pct": 3.5,
            "return_6m_pct": 7.2,
            "return_12m_pct": 12.4,
            "realized_volatility": 0.18,
            "max_drawdown_pct": -12.0,
            "distance_from_52w_high_pct": -5.0,
            "sector": "Technology",
        },
    )

    result = service.generate(
        RecommendationGenerateRequest(
            investable_amount=5000.0,
            market_data_mode="live",
            use_demo_portfolio=True,
            eligible_markets=["US"],
        )
    )

    target = next(r for r in result.recommendations if r.ticker == "VALMISS")
    components = {c.name: c for c in target.components}
    assert components["valuation"].value is None
    assert components["valuation"].status == "UNAVAILABLE"


def test_wave3_cross_market_ranking_and_allocation_reconciliation() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0 if from_ccy.upper() == to_ccy.upper() else (83.0 if from_ccy.upper() == "USD" and to_ccy.upper() == "INR" else 1.35)  # type: ignore[method-assign]

    candidates = [
        CandidateInstrument("USA1", "US One", "UNAVAILABLE", "US", "US", "United States", "USD", "Equity", "US", "Technology", None),
        CandidateInstrument("IND1.NS", "India One", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Financials", None),
        CandidateInstrument("SGP1.SI", "SG One", "UNAVAILABLE", "Singapore", "SGX", "Singapore", "SGD", "Equity", "SINGAPORE", "Industrials", None),
    ]

    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        candidates,
        {"markets": {"US": {"total_seed": 1, "eligible": 1, "partial": 0, "ineligible": 0}, "India": {"total_seed": 1, "eligible": 1, "partial": 0, "ineligible": 0}, "Singapore": {"total_seed": 1, "eligible": 1, "partial": 0, "ineligible": 0}}, "total_candidates": 3, "eligible_candidates": 3, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"US": 1, "India": 1, "Singapore": 1}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )

    def _mk(ticker: str, ccy: str, market: str, r12: float, vol: float) -> MarketSnapshot:
        return MarketSnapshot(
            ticker=ticker,
            provider="yfinance",
            mode="LIVE",
            as_of="2026-08-10T00:00:00Z",
            is_stale=False,
            fallback_reason=None,
            seeded_input=False,
            latest_price=100.0,
            daily_return_pct=0.3,
            return_1m_pct=1.2,
            return_3m_pct=3.0,
            return_6m_pct=6.0,
            return_12m_pct=r12,
            realized_volatility=vol,
            drawdown_pct=-10.0,
            distance_from_52w_high_pct=-4.0,
            trading_currency=ccy,
            sector="Technology",
            portfolio_role="UNAVAILABLE",
            quality_score=70.0,
            growth_score=70.0,
            fx_required=(ccy != "USD"),
            fx_available=True,
            fx_rate_to_base=1.0 if ccy == "USD" else 80.0,
            missing_inputs=[],
            history_observations=252,
            raw_metrics={
                "returnOnEquity": 0.20,
                "operatingMargins": 0.18,
                "profitMargins": 0.16,
                "revenueGrowth": 0.14,
                "earningsGrowth": 0.12,
                "trailingPE": 20.0,
                "forwardPE": 18.0,
                "priceToBook": 3.0,
                "enterpriseToEbitda": 12.0,
                "marketCap": 1_000_000_000_000.0,
                "freeCashflow": 20_000_000_000.0,
                "operatingCashflow": 30_000_000_000.0,
                "debtToEquity": 70.0,
                "currentRatio": 1.8,
                "return_3m_pct": 3.0,
                "return_6m_pct": 6.0,
                "return_12m_pct": r12,
                "realized_volatility": vol,
                "max_drawdown_pct": -10.0,
                "distance_from_52w_high_pct": -4.0,
                "sector": "Technology",
            },
        )

    service._fetch_live_snapshot = lambda c, _base: _mk(c.ticker, c.trading_currency or "USD", c.market, 14.0 if c.market == "US" else (18.0 if c.market == "India" else 10.0), 0.16 if c.market == "US" else (0.22 if c.market == "India" else 0.14))  # type: ignore[method-assign]

    result = service.generate(
        RecommendationGenerateRequest(
            investable_amount=5000.0,
            market_data_mode="live",
            use_demo_portfolio=True,
            eligible_markets=["US", "India", "Singapore"],
        )
    )

    assert len(result.top_ranked_candidates) >= 3
    markets = {row.get("market") for row in result.top_ranked_candidates[:3]}
    assert markets.issubset({"US", "India", "Singapore"})
    assert abs((result.allocation_total + (result.residual_cash or 0.0)) - 5000.0) <= 1.0


def test_wave3_sensitivity_small_weight_shift_keeps_ranking_stable() -> None:
    service = RecommendationMVPService()

    def _item(ticker: str, combined_inputs: tuple[float, float, float, float, float], suitability: float = 52.0) -> dict[str, object]:
        quality, growth, valuation, momentum, risk = combined_inputs
        market = MarketSnapshot(
            ticker=ticker,
            provider="yfinance",
            mode="LIVE",
            as_of="2026-08-10T00:00:00Z",
            is_stale=False,
            fallback_reason=None,
            seeded_input=False,
            latest_price=100.0,
            daily_return_pct=0.1,
            return_1m_pct=1.0,
            return_3m_pct=3.0,
            return_6m_pct=6.0,
            return_12m_pct=12.0,
            realized_volatility=0.18,
            drawdown_pct=-12.0,
            distance_from_52w_high_pct=-5.0,
            trading_currency="USD",
            sector="Technology",
            portfolio_role="UNAVAILABLE",
            quality_score=quality,
            growth_score=growth,
            fx_required=False,
            fx_available=True,
            fx_rate_to_base=1.0,
            missing_inputs=[],
            history_observations=252,
            raw_metrics={"sector": "Technology"},
        )
        return {
            "candidate": CandidateInstrument(ticker, ticker, "UNAVAILABLE", "US", "US", "United States", "USD", "Equity", "US", "Technology", None),
            "market": market,
            "current_value": 0.0,
            "current_weight": 0.0,
            "quality_score": quality,
            "growth_score": growth,
            "valuation_score": valuation,
            "momentum_score": momentum,
            "risk_score": risk,
            "security_attractiveness_score": 0.0,
            "portfolio_suitability_score": suitability,
            "combined_recommendation_score": 0.0,
            "evidence_coverage": 0.95,
            "confidence": 0.9,
            "missing_fields": [],
            "factor_weights": {"QUALITY": 0.28, "GROWTH": 0.17, "VALUATION": 0.20, "MOMENTUM": 0.20, "RISK": 0.15},
            "challenge_flags": [],
        }

    payload = [
        _item("AAA", (88.0, 82.0, 76.0, 74.0, 71.0)),
        _item("BBB", (83.0, 80.0, 72.0, 71.0, 69.0)),
        _item("CCC", (79.0, 77.0, 70.0, 68.0, 67.0)),
        _item("DDD", (66.0, 65.0, 64.0, 63.0, 62.0)),
        _item("EEE", (54.0, 56.0, 58.0, 55.0, 57.0)),
        _item("FFF", (48.0, 49.0, 50.0, 52.0, 51.0)),
    ]

    result = service._build_sensitivity_from_payload(payload, 5000.0)

    assert result["classification"] == "STABLE"
    assert result["base_top_n"] == ["AAA", "BBB", "CCC"]
    assert all(s["ranking_jaccard_with_base"] >= 0.6667 for s in result["scenarios"])
    assert all(s["action_jaccard_with_base"] == 1.0 for s in result["scenarios"])


def test_wave3_sensitivity_fragile_fixture_is_unstable() -> None:
    service = RecommendationMVPService()

    def _item(ticker: str, combined_inputs: tuple[float, float, float, float, float], suitability: float = 60.0) -> dict[str, object]:
        quality, growth, valuation, momentum, risk = combined_inputs
        market = MarketSnapshot(
            ticker=ticker,
            provider="yfinance",
            mode="LIVE",
            as_of="2026-08-10T00:00:00Z",
            is_stale=False,
            fallback_reason=None,
            seeded_input=False,
            latest_price=100.0,
            daily_return_pct=0.1,
            return_1m_pct=1.0,
            return_3m_pct=3.0,
            return_6m_pct=6.0,
            return_12m_pct=12.0,
            realized_volatility=0.18,
            drawdown_pct=-12.0,
            distance_from_52w_high_pct=-5.0,
            trading_currency="USD",
            sector="Technology",
            portfolio_role="UNAVAILABLE",
            quality_score=quality,
            growth_score=growth,
            fx_required=False,
            fx_available=True,
            fx_rate_to_base=1.0,
            missing_inputs=[],
            history_observations=252,
            raw_metrics={"sector": "Technology"},
        )
        return {
            "candidate": CandidateInstrument(ticker, ticker, "UNAVAILABLE", "US", "US", "United States", "USD", "Equity", "US", "Technology", None),
            "market": market,
            "current_value": 0.0,
            "current_weight": 0.0,
            "quality_score": quality,
            "growth_score": growth,
            "valuation_score": valuation,
            "momentum_score": momentum,
            "risk_score": risk,
            "security_attractiveness_score": 0.0,
            "portfolio_suitability_score": suitability,
            "combined_recommendation_score": 0.0,
            "evidence_coverage": 0.95,
            "confidence": 0.9,
            "missing_fields": [],
            "factor_weights": {"QUALITY": 0.28, "GROWTH": 0.17, "VALUATION": 0.20, "MOMENTUM": 0.20, "RISK": 0.15},
            "challenge_flags": [],
        }

    payload = [
        _item("AAA", (55.0, 43.0, 34.0, 89.0, 23.0)),
        _item("BBB", (50.0, 36.0, 66.0, 22.0, 88.0)),
        _item("CCC", (60.0, 56.0, 58.0, 83.0, 28.0)),
        _item("DDD", (51.0, 47.0, 84.0, 21.0, 52.0)),
        _item("EEE", (80.0, 92.0, 39.0, 35.0, 85.0)),
        _item("FFF", (62.0, 31.0, 37.0, 35.0, 33.0)),
        _item("GGG", (25.0, 83.0, 50.0, 58.0, 34.0)),
        _item("HHH", (71.0, 30.0, 80.0, 25.0, 35.0)),
    ]

    result = service._build_sensitivity_from_payload(payload, 5000.0)

    assert result["classification"] == "UNSTABLE"
    assert any(s["ranking_jaccard_with_base"] < 0.7 for s in result["scenarios"])


def _mk_live_snapshot(
    ticker: str,
    *,
    currency: str = "USD",
    sector: str = "Technology",
    quality: float = 70.0,
    growth: float = 68.0,
    ret3m: float = 5.0,
    ret6m: float = 8.0,
    ret12m: float = 12.0,
    vol: float = 0.18,
    drawdown: float = -12.0,
    dist52w: float = -6.0,
    fx_available: bool = True,
    market_cap: float | None = 1e10,
    earnings_q_growth: float | None = 0.22,
    trading_days: int = 252,
    median_daily_value: float | None = 5e8,
    median_daily_volume: float | None = 5e5,
    liquidity_score: float | None = 92.0,
    liquidity_status: str = "PASS",
    raw_overrides: dict[str, float | str | None] | None = None,
) -> MarketSnapshot:
    return MarketSnapshot(
        ticker=ticker,
        provider="yfinance",
        mode="LIVE",
        as_of="2026-08-10T00:00:00Z",
        is_stale=False,
        fallback_reason=None,
        seeded_input=False,
        latest_price=100.0,
        daily_return_pct=0.5,
        return_1m_pct=ret3m / 3.0,
        return_3m_pct=ret3m,
        return_6m_pct=ret6m,
        return_12m_pct=ret12m,
        realized_volatility=vol,
        drawdown_pct=drawdown,
        distance_from_52w_high_pct=dist52w,
        trading_currency=currency,
        sector=sector,
        portfolio_role="UNAVAILABLE",
        quality_score=quality,
        growth_score=growth,
        fx_required=(currency != "USD"),
        fx_available=fx_available,
        fx_rate_to_base=1.0 if fx_available else None,
        missing_inputs=[] if fx_available else ["fx_rate"],
        history_observations=trading_days,
        raw_metrics={
            "returnOnEquity": 0.2,
            "operatingMargins": 0.2,
            "profitMargins": 0.2,
            "freeCashflow": 1000.0,
            "operatingCashflow": 1200.0,
            "debtToEquity": 50.0,
            "currentRatio": 1.5,
            "revenueGrowth": 0.12,
            "earningsGrowth": 0.15,
            "earningsQuarterlyGrowth": earnings_q_growth,
            "trailingPE": 20.0,
            "forwardPE": 18.0,
            "priceToBook": 3.0,
            "enterpriseToEbitda": 14.0,
            "marketCap": market_cap,
            "median_daily_value": median_daily_value,
            "median_daily_volume": median_daily_volume,
            "trading_days": trading_days,
            "active_trading_days": max(0, trading_days - 2),
            "zero_volume_days": 2,
            "liquidity_score": liquidity_score,
            "liquidity_status": liquidity_status,
            "return_3m_pct": ret3m,
            "return_6m_pct": ret6m,
            "return_12m_pct": ret12m,
            "realized_volatility": vol,
            "max_drawdown_pct": drawdown,
            "distance_from_52w_high_pct": dist52w,
            "sector": sector,
            **(raw_overrides or {}),
        },
    )


def test_wave3_unseen_tickers_are_feature_driven() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0  # type: ignore[method-assign]

    candidates = [
        CandidateInstrument("KNOWN1", "Known One", "UNAVAILABLE", "US", "US", "United States", "USD", "Equity", "US", "Technology", None),
        CandidateInstrument("UNSEEN_X1", "Unseen One", "UNAVAILABLE", "US", "US", "United States", "USD", "Equity", "US", "Technology", None),
        CandidateInstrument("KNOWN2", "Known Two", "UNAVAILABLE", "US", "US", "United States", "USD", "Equity", "US", "Technology", None),
    ]

    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        candidates,
        {"markets": {"US": {"total_seed": 3, "eligible": 3, "partial": 0, "ineligible": 0}}, "total_candidates": 3, "eligible_candidates": 3, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"US": 3}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )
    service._select_holdings = lambda _use_demo, _snap: [  # type: ignore[method-assign]
        Holding(holding_id="h1", ticker="BASE", name="Base", quantity=1, market_value=10000.0, geography="US", currency="USD", asset_class="Equity", sector="Industrials", theme="Base")
    ]

    by_ticker = {
        "KNOWN1": _mk_live_snapshot("KNOWN1", quality=82.0, growth=79.0, ret3m=9.0, ret6m=13.0, ret12m=19.0, vol=0.12, drawdown=-8.0, dist52w=-3.0),
        "UNSEEN_X1": _mk_live_snapshot("UNSEEN_X1", quality=82.0, growth=79.0, ret3m=9.0, ret6m=13.0, ret12m=19.0, vol=0.12, drawdown=-8.0, dist52w=-3.0),
        "KNOWN2": _mk_live_snapshot("KNOWN2", quality=65.0, growth=60.0, ret3m=2.0, ret6m=4.0, ret12m=7.0, vol=0.24, drawdown=-18.0, dist52w=-12.0),
    }
    service._fetch_live_snapshot = lambda c, _base: by_ticker.get(c.ticker)  # type: ignore[method-assign]

    result = service.generate(
        RecommendationGenerateRequest(
            investable_amount=5000.0,
            market_data_mode="live",
            use_demo_portfolio=False,
            eligible_markets=["US"],
        )
    )

    rows = {r.ticker: r for r in result.recommendations if r.ticker in {"KNOWN1", "UNSEEN_X1"}}
    assert rows["KNOWN1"].action == rows["UNSEEN_X1"].action
    assert abs(rows["KNOWN1"].score - rows["UNSEEN_X1"].score) < 0.01


def test_wave3_identifier_rename_invariance() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0  # type: ignore[method-assign]

    base_symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    renamed = {"AAA": "RN_AAA", "BBB": "RN_BBB", "CCC": "RN_CCC"}

    base_metrics = {
        "AAA": dict(quality=86.0, growth=83.0, ret3m=11.0, ret6m=16.0, ret12m=22.0, vol=0.11, drawdown=-7.0, dist52w=-2.0),
        "BBB": dict(quality=78.0, growth=76.0, ret3m=8.0, ret6m=11.0, ret12m=16.0, vol=0.14, drawdown=-9.0, dist52w=-4.0),
        "CCC": dict(quality=74.0, growth=73.0, ret3m=6.0, ret6m=9.0, ret12m=13.0, vol=0.16, drawdown=-10.0, dist52w=-5.0),
        "DDD": dict(quality=62.0, growth=58.0, ret3m=1.0, ret6m=3.0, ret12m=6.0, vol=0.23, drawdown=-17.0, dist52w=-11.0),
        "EEE": dict(quality=59.0, growth=55.0, ret3m=0.0, ret6m=1.0, ret12m=2.0, vol=0.26, drawdown=-20.0, dist52w=-13.0),
    }

    def _run(symbols: list[str]) -> tuple[list[str], dict[str, str]]:
        candidates = [
            CandidateInstrument(t, t, "UNAVAILABLE", "US", "US", "United States", "USD", "Equity", "US", "Technology", None)
            for t in symbols
        ]
        service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
            candidates,
            {"markets": {"US": {"total_seed": len(candidates), "eligible": len(candidates), "partial": 0, "ineligible": 0}}, "total_candidates": len(candidates), "eligible_candidates": len(candidates), "partial_candidates": 0, "ineligible_candidates": 0},
            {"eligible_by_market": {"US": len(candidates)}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
            [],
        )
        service._select_holdings = lambda _use_demo, _snap: [  # type: ignore[method-assign]
            Holding(holding_id="h1", ticker="BASE", name="Base", quantity=1, market_value=10000.0, geography="US", currency="USD", asset_class="Equity", sector="Industrials", theme="Base")
        ]

        def _fetch(candidate, _base):
            original = next((k for k, v in renamed.items() if v == candidate.ticker), candidate.ticker)
            return _mk_live_snapshot(candidate.ticker, **base_metrics[original])

        service._fetch_live_snapshot = _fetch  # type: ignore[method-assign]
        result = service.generate(
            RecommendationGenerateRequest(
                investable_amount=5000.0,
                market_data_mode="live",
                use_demo_portfolio=False,
                eligible_markets=["US"],
            )
        )
        ranked = [row["ticker"] for row in result.top_ranked_candidates[:5]]
        actions = {r.ticker: r.action for r in result.recommendations if r.ticker in symbols}
        return ranked, actions

    base_rank, base_actions = _run(base_symbols)
    renamed_symbols = [renamed.get(t, t) for t in base_symbols]
    renamed_rank, renamed_actions = _run(renamed_symbols)

    inv = {v: k for k, v in renamed.items()}
    mapped_rank = [inv.get(t, t) for t in renamed_rank]
    mapped_actions = {inv.get(k, k): v for k, v in renamed_actions.items()}

    assert base_rank == mapped_rank
    assert base_actions == mapped_actions


def test_wave3_permutation_invariance_for_ranking() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0  # type: ignore[method-assign]

    universe = {
        "US": ["U1", "U2", "U3"],
        "India": ["I1.NS", "I2.NS"],
        "Singapore": ["S1.SI", "S2.SI"],
    }
    metrics = {
        "U1": dict(quality=85.0, growth=80.0, ret3m=10.0, ret6m=15.0, ret12m=20.0, vol=0.13, drawdown=-8.0, dist52w=-3.0),
        "U2": dict(quality=78.0, growth=76.0, ret3m=8.0, ret6m=12.0, ret12m=16.0, vol=0.15, drawdown=-9.0, dist52w=-4.0),
        "U3": dict(quality=70.0, growth=66.0, ret3m=4.0, ret6m=6.0, ret12m=10.0, vol=0.19, drawdown=-12.0, dist52w=-7.0),
        "I1.NS": dict(quality=83.0, growth=79.0, ret3m=9.0, ret6m=14.0, ret12m=19.0, vol=0.14, drawdown=-9.0, dist52w=-4.0),
        "I2.NS": dict(quality=72.0, growth=68.0, ret3m=5.0, ret6m=8.0, ret12m=12.0, vol=0.20, drawdown=-13.0, dist52w=-8.0),
        "S1.SI": dict(quality=76.0, growth=71.0, ret3m=7.0, ret6m=10.0, ret12m=14.0, vol=0.16, drawdown=-10.0, dist52w=-5.0),
        "S2.SI": dict(quality=64.0, growth=60.0, ret3m=2.0, ret6m=4.0, ret12m=7.0, vol=0.24, drawdown=-18.0, dist52w=-12.0),
    }

    def _discover(markets: list[str]) -> list[CandidateInstrument]:
        out: list[CandidateInstrument] = []
        for market in markets:
            for ticker in universe[market]:
                ccy = "USD" if market == "US" else ("INR" if market == "India" else "SGD")
                out.append(CandidateInstrument(ticker, ticker, "UNAVAILABLE", market, None, None, ccy, "Equity", market.upper(), "Technology", None))
        return out

    def _run(markets: list[str], shuffle: bool) -> list[str]:
        candidates = _discover(markets)
        if shuffle:
            random.seed(42)
            random.shuffle(candidates)
        service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
            candidates,
            {"markets": {m: {"total_seed": len(universe[m]), "eligible": len(universe[m]), "partial": 0, "ineligible": 0} for m in markets}, "total_candidates": len(candidates), "eligible_candidates": len(candidates), "partial_candidates": 0, "ineligible_candidates": 0},
            {"eligible_by_market": {m: len(universe[m]) for m in markets}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
            [],
        )
        service._select_holdings = lambda _use_demo, _snap: [  # type: ignore[method-assign]
            Holding(holding_id="h1", ticker="BASE", name="Base", quantity=1, market_value=10000.0, geography="US", currency="USD", asset_class="Equity", sector="Industrials", theme="Base")
        ]

        def _fetch(candidate, _base):
            data = metrics[candidate.ticker]
            ccy = "USD" if candidate.market == "US" else ("INR" if candidate.market == "India" else "SGD")
            return _mk_live_snapshot(candidate.ticker, currency=ccy, **data)

        service._fetch_live_snapshot = _fetch  # type: ignore[method-assign]

        result = service.generate(
            RecommendationGenerateRequest(
                investable_amount=5000.0,
                market_data_mode="live",
                use_demo_portfolio=False,
                eligible_markets=markets,
            )
        )
        return [row["ticker"] for row in result.top_ranked_candidates[:7]]

    base_rank = _run(["US", "India", "Singapore"], shuffle=False)
    permuted_rank = _run(["Singapore", "US", "India"], shuffle=True)
    assert base_rank == permuted_rank


def test_wave3_provider_failure_never_fabricates_buy_add() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0 if from_ccy == to_ccy else None  # type: ignore[method-assign]

    candidates = [
        CandidateInstrument("OK1", "OK1", "UNAVAILABLE", "US", "US", "United States", "USD", "Equity", "US", "Technology", None),
        CandidateInstrument("NO_DATA", "NO_DATA", "UNAVAILABLE", "US", "US", "United States", "USD", "Equity", "US", "Technology", None),
        CandidateInstrument("FXMISS.SI", "FXMISS.SI", "UNAVAILABLE", "Singapore", "SGX", "Singapore", "SGD", "Equity", "SINGAPORE", "Financials", None),
    ]

    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        candidates,
        {"markets": {"US": {"total_seed": 2, "eligible": 2, "partial": 0, "ineligible": 0}, "Singapore": {"total_seed": 1, "eligible": 1, "partial": 0, "ineligible": 0}}, "total_candidates": 3, "eligible_candidates": 3, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"US": 2, "Singapore": 1}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )
    service._select_holdings = lambda _use_demo, _snap: [  # type: ignore[method-assign]
        Holding(holding_id="h1", ticker="BASE", name="Base", quantity=1, market_value=10000.0, geography="US", currency="USD", asset_class="Equity", sector="Industrials", theme="Base")
    ]

    def _fetch(candidate, _base):
        if candidate.ticker == "NO_DATA":
            return None
        if candidate.ticker == "FXMISS.SI":
            return _mk_live_snapshot("FXMISS.SI", currency="SGD", fx_available=False)
        return _mk_live_snapshot("OK1", quality=68.0, growth=66.0, ret3m=4.0, ret6m=7.0, ret12m=10.0)

    service._fetch_live_snapshot = _fetch  # type: ignore[method-assign]

    result = service.generate(
        RecommendationGenerateRequest(
            investable_amount=5000.0,
            market_data_mode="live",
            use_demo_portfolio=False,
            eligible_markets=["US", "Singapore"],
        )
    )

    for row in result.recommendations:
        if row.market_data_mode == "UNAVAILABLE" or "fx_rate" in row.unavailable_inputs:
            assert row.action not in {"BUY", "ADD"}
            assert row.seeded_input is False


def test_wave3_live_path_has_no_seeded_actionable_inputs() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0  # type: ignore[method-assign]

    candidates = [
        CandidateInstrument("LIVE1", "LIVE1", "UNAVAILABLE", "US", "US", "United States", "USD", "Equity", "US", "Technology", None),
        CandidateInstrument("LIVE2", "LIVE2", "UNAVAILABLE", "US", "US", "United States", "USD", "Equity", "US", "Technology", None),
    ]
    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        candidates,
        {"markets": {"US": {"total_seed": 2, "eligible": 2, "partial": 0, "ineligible": 0}}, "total_candidates": 2, "eligible_candidates": 2, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"US": 2}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )
    service._select_holdings = lambda _use_demo, _snap: [  # type: ignore[method-assign]
        Holding(holding_id="h1", ticker="BASE", name="Base", quantity=1, market_value=10000.0, geography="US", currency="USD", asset_class="Equity", sector="Industrials", theme="Base")
    ]
    by_ticker = {
        "LIVE1": _mk_live_snapshot("LIVE1", quality=88.0, growth=84.0, ret3m=10.0, ret6m=14.0, ret12m=20.0, vol=0.12, drawdown=-7.0, dist52w=-2.0),
        "LIVE2": _mk_live_snapshot("LIVE2", quality=74.0, growth=70.0, ret3m=6.0, ret6m=9.0, ret12m=14.0, vol=0.16, drawdown=-10.0, dist52w=-4.0),
    }
    service._fetch_live_snapshot = lambda c, _base: deepcopy(by_ticker[c.ticker])  # type: ignore[method-assign]

    result = service.generate(
        RecommendationGenerateRequest(
            investable_amount=5000.0,
            market_data_mode="live",
            use_demo_portfolio=False,
            eligible_markets=["US"],
        )
    )

    actionable = [r for r in result.recommendations if r.action in {"BUY", "ADD"}]
    assert all(r.seeded_input is False for r in result.recommendations)
    assert all(r.market_data_provider != "development_seed" for r in result.recommendations)
    assert all(r.seeded_input is False for r in actionable)


def test_wave3_attribute_invariance_identical_inputs_different_tickers() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0  # type: ignore[method-assign]

    candidates = [
        CandidateInstrument("ALPHA_X", "Alpha", "UNAVAILABLE", "US", "US", "United States", "USD", "Equity", "US", "Technology", None),
        CandidateInstrument("BETA_Y", "Beta", "UNAVAILABLE", "US", "US", "United States", "USD", "Equity", "US", "Technology", None),
    ]
    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        candidates,
        {"markets": {"US": {"total_seed": 2, "eligible": 2, "partial": 0, "ineligible": 0}}, "total_candidates": 2, "eligible_candidates": 2, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"US": 2}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )
    service._select_holdings = lambda _use_demo, _snap: [  # type: ignore[method-assign]
        Holding(holding_id="h1", ticker="BASE", name="Base", quantity=1, market_value=10000.0, geography="US", currency="USD", asset_class="Equity", sector="Industrials", theme="Base")
    ]
    service._fetch_live_snapshot = lambda c, _base: _mk_live_snapshot(  # type: ignore[method-assign]
        c.ticker,
        quality=82.0,
        growth=79.0,
        ret3m=9.0,
        ret6m=13.0,
        ret12m=19.0,
        vol=0.12,
        drawdown=-8.0,
        dist52w=-3.0,
        sector="Technology",
    )

    result = service.generate(
        RecommendationGenerateRequest(
            investable_amount=5000.0,
            market_data_mode="live",
            use_demo_portfolio=False,
            eligible_markets=["US"],
        )
    )

    rows = {r.ticker: r for r in result.recommendations if r.ticker in {"ALPHA_X", "BETA_Y"}}
    alpha = rows["ALPHA_X"]
    beta = rows["BETA_Y"]

    def _component_value(row, name: str):
        comp = next(c for c in row.components if c.name == name)
        return comp.value

    assert _component_value(alpha, "security_attractiveness") == _component_value(beta, "security_attractiveness")
    assert _component_value(alpha, "portfolio_suitability") == _component_value(beta, "portfolio_suitability")
    assert alpha.score == beta.score
    assert alpha.confidence == beta.confidence
    assert alpha.action == beta.action


def test_wave3_attribute_invariance_holding_status_exception_isolated() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0  # type: ignore[method-assign]

    candidates = [
        CandidateInstrument("ALPHA_X", "Alpha", "UNAVAILABLE", "US", "US", "United States", "USD", "Equity", "US", "Technology", None),
        CandidateInstrument("BETA_Y", "Beta", "UNAVAILABLE", "US", "US", "United States", "USD", "Equity", "US", "Technology", None),
    ]
    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        candidates,
        {"markets": {"US": {"total_seed": 2, "eligible": 2, "partial": 0, "ineligible": 0}}, "total_candidates": 2, "eligible_candidates": 2, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"US": 2}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )
    service._select_holdings = lambda _use_demo, _snap: [  # type: ignore[method-assign]
        Holding(holding_id="h1", ticker="ALPHA_X", name="Alpha", quantity=1, market_value=12000.0, geography="US", currency="USD", asset_class="Equity", sector="Technology", theme="Base"),
        Holding(holding_id="h2", ticker="BASE", name="Base", quantity=1, market_value=8000.0, geography="US", currency="USD", asset_class="Equity", sector="Industrials", theme="Base"),
    ]
    service._fetch_live_snapshot = lambda c, _base: _mk_live_snapshot(  # type: ignore[method-assign]
        c.ticker,
        quality=82.0,
        growth=79.0,
        ret3m=9.0,
        ret6m=13.0,
        ret12m=19.0,
        vol=0.12,
        drawdown=-8.0,
        dist52w=-3.0,
        sector="Technology",
    )

    result = service.generate(
        RecommendationGenerateRequest(
            investable_amount=5000.0,
            market_data_mode="live",
            use_demo_portfolio=False,
            eligible_markets=["US"],
        )
    )

    rows = {r.ticker: r for r in result.recommendations if r.ticker in {"ALPHA_X", "BETA_Y"}}
    alpha = rows["ALPHA_X"]
    beta = rows["BETA_Y"]

    def _component_value(row, name: str):
        comp = next(c for c in row.components if c.name == name)
        return comp.value

    # Attractiveness and confidence remain data-driven and equal.
    assert _component_value(alpha, "security_attractiveness") == _component_value(beta, "security_attractiveness")
    assert alpha.confidence == beta.confidence
    # Suitability/combined/action are allowed to differ because one ticker is an existing holding.
    assert _component_value(alpha, "portfolio_suitability") != _component_value(beta, "portfolio_suitability")
    assert alpha.score != beta.score or alpha.action != beta.action


def test_wave3_synthetic_technology_concentration_without_real_tickers_and_rename_invariance() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0  # type: ignore[method-assign]

    def _run(holdings: list[Holding]) -> dict[str, str]:
        service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
            [],
            {"markets": {"US": {"total_seed": 0, "eligible": 0, "partial": 0, "ineligible": 0}}, "total_candidates": 0, "eligible_candidates": 0, "partial_candidates": 0, "ineligible_candidates": 0},
            {"eligible_by_market": {"US": 0}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
            [],
        )
        service._select_holdings = lambda _use_demo, _snap: holdings  # type: ignore[method-assign]
        service._fetch_live_snapshot = lambda c, _base: None  # type: ignore[method-assign]

        result = service.generate(
            RecommendationGenerateRequest(
                investable_amount=5000.0,
                market_data_mode="live",
                use_demo_portfolio=False,
                eligible_markets=["US"],
            )
        )
        return {r.ticker: r.action for r in result.recommendations}

    tech_heavy = [
        Holding(holding_id="h1", ticker="SYNTH_T1", name="Synth T1", quantity=1, market_value=70000.0, geography="US", currency="USD", asset_class="Equity", sector="Technology", theme="Core"),
        Holding(holding_id="h2", ticker="SYNTH_T2", name="Synth T2", quantity=1, market_value=25000.0, geography="US", currency="USD", asset_class="Equity", sector="Technology", theme="Core"),
        Holding(holding_id="h3", ticker="SYNTH_O1", name="Synth O1", quantity=1, market_value=5000.0, geography="US", currency="USD", asset_class="Equity", sector="Industrials", theme="Core"),
    ]
    non_tech_heavy = [
        Holding(holding_id="h1", ticker="SYNTH_I1", name="Synth I1", quantity=1, market_value=70000.0, geography="US", currency="USD", asset_class="Equity", sector="Industrials", theme="Core"),
        Holding(holding_id="h2", ticker="SYNTH_F1", name="Synth F1", quantity=1, market_value=25000.0, geography="US", currency="USD", asset_class="Equity", sector="Financials", theme="Core"),
        Holding(holding_id="h3", ticker="SYNTH_O1", name="Synth O1", quantity=1, market_value=5000.0, geography="US", currency="USD", asset_class="Equity", sector="Industrials", theme="Core"),
    ]

    tech_actions = _run(tech_heavy)
    base_actions = _run(non_tech_heavy)

    assert tech_actions["SYNTH_T1"] == "REDUCE"
    assert tech_actions["SYNTH_T2"] == "REDUCE"
    assert tech_actions["SYNTH_O1"] == "HOLD"
    assert base_actions["SYNTH_I1"] == "HOLD"
    assert base_actions["SYNTH_F1"] == "HOLD"

    renamed_tech_heavy = [
        Holding(holding_id="h1", ticker="RENAMED_T1", name="Renamed T1", quantity=1, market_value=70000.0, geography="US", currency="USD", asset_class="Equity", sector="Technology", theme="Core"),
        Holding(holding_id="h2", ticker="RENAMED_T2", name="Renamed T2", quantity=1, market_value=25000.0, geography="US", currency="USD", asset_class="Equity", sector="Technology", theme="Core"),
        Holding(holding_id="h3", ticker="RENAMED_O1", name="Renamed O1", quantity=1, market_value=5000.0, geography="US", currency="USD", asset_class="Equity", sector="Industrials", theme="Core"),
    ]
    renamed_actions = _run(renamed_tech_heavy)

    assert renamed_actions["RENAMED_T1"] == "REDUCE"
    assert renamed_actions["RENAMED_T2"] == "REDUCE"
    assert renamed_actions["RENAMED_O1"] == "HOLD"


def test_wave32_market_cap_bucket_classification_and_mid_small_presence() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0  # type: ignore[method-assign]

    candidates = [
        CandidateInstrument("IND_LG.NS", "Large", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Technology", None),
        CandidateInstrument("IND_MD.NS", "Mid", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Industrials", None),
        CandidateInstrument("IND_SM.NS", "Small", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Healthcare", None),
        CandidateInstrument("IND_UNK.NS", "Unknown", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Financials", None),
    ]
    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        candidates,
        {"markets": {"India": {"total_seed": 4, "eligible": 4, "partial": 0, "ineligible": 0}}, "total_candidates": 4, "eligible_candidates": 4, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"India": 4}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )
    by_ticker = {
        "IND_LG.NS": _mk_live_snapshot("IND_LG.NS", currency="INR", market_cap=8e12, sector="Technology"),
        "IND_MD.NS": _mk_live_snapshot("IND_MD.NS", currency="INR", market_cap=7e11, sector="Industrials"),
        "IND_SM.NS": _mk_live_snapshot("IND_SM.NS", currency="INR", market_cap=9e10, sector="Healthcare"),
        "IND_UNK.NS": _mk_live_snapshot("IND_UNK.NS", currency="INR", market_cap=None, sector="Financials"),
    }
    service._fetch_live_snapshot = lambda c, _base: by_ticker[c.ticker]  # type: ignore[method-assign]

    result = service.generate(
        RecommendationGenerateRequest(investable_amount=5000.0, market_data_mode="live", use_demo_portfolio=False, eligible_markets=["India"])
    )
    rows = {r["ticker"]: r for r in result.top_ranked_candidates}
    assert rows["IND_LG.NS"]["market_cap_bucket"] == "RELATIVE_LARGE"
    assert rows["IND_LG.NS"]["relative_market_cap_bucket"] == "RELATIVE_LARGE"
    assert rows["IND_MD.NS"]["market_cap_bucket"] in {"RELATIVE_MID", "RELATIVE_SMALL"}
    assert rows["IND_SM.NS"]["market_cap_bucket"] in {"RELATIVE_SMALL", "RELATIVE_MICRO_OR_UNKNOWN"}
    assert rows["IND_UNK.NS"]["market_cap_bucket"] == "UNKNOWN"


def test_wave32_transparency_trace_includes_raw_validated_bounds_and_normalized_scores() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0  # type: ignore[method-assign]

    candidates = [
        CandidateInstrument("TRACE1.NS", "Trace 1", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Industrials", None),
        CandidateInstrument("TRACE2.NS", "Trace 2", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Industrials", None),
        CandidateInstrument("TRACE3.NS", "Trace 3", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Industrials", None),
        CandidateInstrument("TRACE4.NS", "Trace 4", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Industrials", None),
        CandidateInstrument("TRACE5.NS", "Trace 5", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Industrials", None),
        CandidateInstrument("TRACE6.NS", "Trace 6", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Industrials", None),
    ]
    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        candidates,
        {"markets": {"India": {"total_seed": 6, "eligible": 6, "partial": 0, "ineligible": 0}}, "total_candidates": 6, "eligible_candidates": 6, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"India": 6}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )

    def _snap(ticker: str, eg: float) -> MarketSnapshot:
        return _mk_live_snapshot(
            ticker,
            currency="INR",
            sector="Industrials",
            quality=72.0,
            growth=70.0,
            ret3m=6.0,
            ret6m=9.0,
            ret12m=13.0,
            vol=0.18,
            drawdown=-11.0,
            dist52w=-6.0,
            market_cap=2e11,
            raw_overrides={"earningsGrowth": eg},
        )

    values = {
        "TRACE1.NS": 3.9,
        "TRACE2.NS": 0.7,
        "TRACE3.NS": 0.5,
        "TRACE4.NS": 0.4,
        "TRACE5.NS": 0.3,
        "TRACE6.NS": 0.2,
    }
    service._fetch_live_snapshot = lambda c, _base: _snap(c.ticker, values[c.ticker])  # type: ignore[method-assign]

    result = service.generate(
        RecommendationGenerateRequest(investable_amount=5000.0, market_data_mode="live", use_demo_portfolio=False, eligible_markets=["India"])
    )

    row = next(r for r in result.top_ranked_candidates if r["ticker"] == "TRACE1.NS")
    trace = row["factor_score_trace"]["earningsGrowth"]
    assert trace["raw_provider_value"] == 3.9
    assert trace["validated_value"] == 2.0
    assert trace["winsorized_or_capped"] is True
    assert trace["validation_flag"] == "winsorized_cap"
    assert trace["applicable_bounds"]["winsor_max"] == 2.0
    assert isinstance(trace["normalized_metric_score"], float)


def test_wave32_missing_review_metrics_are_explicitly_unavailable_with_reason() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0  # type: ignore[method-assign]

    candidate = CandidateInstrument("MISSRV.NS", "Missing Review", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Healthcare", None)
    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        [candidate],
        {"markets": {"India": {"total_seed": 1, "eligible": 1, "partial": 0, "ineligible": 0}}, "total_candidates": 1, "eligible_candidates": 1, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"India": 1}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )
    service._fetch_live_snapshot = lambda _c, _base: _mk_live_snapshot(  # type: ignore[method-assign]
        "MISSRV.NS",
        currency="INR",
        market_cap=4e11,
        raw_overrides={
            "freeCashflow": None,
            "operatingCashflow": None,
            "debtToEquity": None,
            "return_3m_pct": None,
            "return_6m_pct": None,
            "return_12m_pct": None,
            "realized_volatility": None,
            "max_drawdown_pct": None,
            "distance_from_52w_high_pct": None,
        },
    )

    result = service.generate(
        RecommendationGenerateRequest(investable_amount=5000.0, market_data_mode="live", use_demo_portfolio=False, eligible_markets=["India"])
    )
    row = next(r for r in result.top_ranked_candidates if r["ticker"] == "MISSRV.NS")
    assert row["operating_cash_flow"] == "UNAVAILABLE"
    assert row["operating_cash_flow_reason"] == "missing_or_non_numeric_provider_value"
    assert row["free_cash_flow"] == "UNAVAILABLE"
    assert row["free_cash_flow_reason"] == "missing_or_non_numeric_provider_value"
    assert row["debt_to_equity"] == "UNAVAILABLE"
    assert row["debt_to_equity_reason"] == "missing_or_non_numeric_provider_value"
    assert row["fcf_yield"] == "UNAVAILABLE"
    assert row["fcf_yield_reason"] == "free_cash_flow_unavailable"
    assert row["return_3m_pct"] == "UNAVAILABLE"
    assert row["return_6m_pct"] == "UNAVAILABLE"
    assert row["return_12m_pct"] == "UNAVAILABLE"
    assert row["volatility"] == "UNAVAILABLE"
    assert row["maximum_drawdown"] == "UNAVAILABLE"
    assert row["distance_from_52w_high"] == "UNAVAILABLE"


def test_wave32_relative_size_rename_does_not_change_ranking_order() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0  # type: ignore[method-assign]

    candidates = [
        CandidateInstrument("SIZ1.NS", "Size1", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Technology", None),
        CandidateInstrument("SIZ2.NS", "Size2", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Technology", None),
        CandidateInstrument("SIZ3.NS", "Size3", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Technology", None),
    ]
    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        candidates,
        {"markets": {"India": {"total_seed": 3, "eligible": 3, "partial": 0, "ineligible": 0}}, "total_candidates": 3, "eligible_candidates": 3, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"India": 3}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )
    by_ticker = {
        "SIZ1.NS": _mk_live_snapshot("SIZ1.NS", currency="INR", market_cap=9e12, quality=88.0, growth=82.0, ret12m=20.0),
        "SIZ2.NS": _mk_live_snapshot("SIZ2.NS", currency="INR", market_cap=7e11, quality=76.0, growth=73.0, ret12m=13.0),
        "SIZ3.NS": _mk_live_snapshot("SIZ3.NS", currency="INR", market_cap=9e10, quality=65.0, growth=61.0, ret12m=9.0),
    }
    service._fetch_live_snapshot = lambda c, _base: by_ticker[c.ticker]  # type: ignore[method-assign]

    result = service.generate(
        RecommendationGenerateRequest(investable_amount=5000.0, market_data_mode="live", use_demo_portfolio=False, eligible_markets=["India"])
    )
    ranked = [r["ticker"] for r in result.top_ranked_candidates if r["ticker"] in {"SIZ1.NS", "SIZ2.NS", "SIZ3.NS"}]
    assert ranked == ["SIZ1.NS", "SIZ2.NS", "SIZ3.NS"]
    assert {r["market_cap_bucket"] for r in result.top_ranked_candidates}.issubset(
        {"RELATIVE_LARGE", "RELATIVE_MID", "RELATIVE_SMALL", "RELATIVE_MICRO_OR_UNKNOWN", "UNKNOWN"}
    )


def test_wave32_fragility_fields_are_diagnostic_only() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0  # type: ignore[method-assign]

    candidates = [
        CandidateInstrument("FRG1.NS", "Frag1", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Technology", None),
        CandidateInstrument("FRG2.NS", "Frag2", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Technology", None),
    ]
    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        candidates,
        {"markets": {"India": {"total_seed": 2, "eligible": 2, "partial": 0, "ineligible": 0}}, "total_candidates": 2, "eligible_candidates": 2, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"India": 2}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )
    by_ticker = {
        "FRG1.NS": _mk_live_snapshot("FRG1.NS", currency="INR", market_cap=6e11, quality=82.0, growth=79.0, ret3m=10.0, ret6m=14.0, ret12m=18.0),
        "FRG2.NS": _mk_live_snapshot("FRG2.NS", currency="INR", market_cap=3e11, quality=74.0, growth=68.0, ret3m=5.0, ret6m=8.0, ret12m=11.0),
    }
    service._fetch_live_snapshot = lambda c, _base: by_ticker[c.ticker]  # type: ignore[method-assign]

    result = service.generate(
        RecommendationGenerateRequest(investable_amount=5000.0, market_data_mode="live", use_demo_portfolio=False, eligible_markets=["India"])
    )

    recs = {r.ticker: r for r in result.recommendations}
    ranked = {r["ticker"]: r for r in result.top_ranked_candidates}
    assert recs["FRG1.NS"].score > recs["FRG2.NS"].score
    assert recs["FRG1.NS"].action in {"BUY", "ADD", "HOLD", "RESEARCH", "AVOID"}
    assert ranked["FRG1.NS"]["strongest_factor"] in {"QUALITY", "GROWTH", "VALUATION", "MOMENTUM", "RISK"}
    assert ranked["FRG1.NS"]["second_strongest_factor"] in {"QUALITY", "GROWTH", "VALUATION", "MOMENTUM", "RISK"}
    assert isinstance(ranked["FRG1.NS"]["rank_without_strongest_factor"], int)
    assert isinstance(ranked["FRG1.NS"]["rank_change_without_strongest_factor"], int)
    assert isinstance(ranked["FRG1.NS"]["remains_top20_without_strongest_factor"], bool)


def test_wave32_regression_core_scores_and_actions_unchanged_for_frozen_fixture() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0  # type: ignore[method-assign]

    candidates = [
        CandidateInstrument("REG1.NS", "Reg1", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Technology", None),
        CandidateInstrument("REG2.NS", "Reg2", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Technology", None),
        CandidateInstrument("REG3.NS", "Reg3", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Technology", None),
    ]
    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        candidates,
        {"markets": {"India": {"total_seed": 3, "eligible": 3, "partial": 0, "ineligible": 0}}, "total_candidates": 3, "eligible_candidates": 3, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"India": 3}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )
    by_ticker = {
        "REG1.NS": _mk_live_snapshot("REG1.NS", currency="INR", market_cap=8e11, quality=84.0, growth=81.0, ret3m=11.0, ret6m=15.0, ret12m=21.0, vol=0.13, drawdown=-8.0, dist52w=-3.0),
        "REG2.NS": _mk_live_snapshot("REG2.NS", currency="INR", market_cap=4e11, quality=76.0, growth=72.0, ret3m=6.0, ret6m=9.0, ret12m=13.0, vol=0.18, drawdown=-11.0, dist52w=-6.0),
        "REG3.NS": _mk_live_snapshot("REG3.NS", currency="INR", market_cap=2e11, quality=68.0, growth=64.0, ret3m=2.0, ret6m=4.0, ret12m=8.0, vol=0.24, drawdown=-16.0, dist52w=-10.0),
    }
    service._fetch_live_snapshot = lambda c, _base: by_ticker[c.ticker]  # type: ignore[method-assign]

    result = service.generate(
        RecommendationGenerateRequest(investable_amount=5000.0, market_data_mode="live", use_demo_portfolio=False, eligible_markets=["India"])
    )
    recs = {r.ticker: r for r in result.recommendations}
    ranked = [r["ticker"] for r in result.top_ranked_candidates if r["ticker"] in {"REG1.NS", "REG2.NS", "REG3.NS"}]

    expected = {
        "REG1.NS": {"score": 57.39, "action": "RESEARCH", "q": 85.71, "g": 100.0, "v": 6.67, "m": 100.0, "r": 83.34, "disc": 74.51},
        "REG2.NS": {"score": 50.67, "action": "RESEARCH", "q": 85.71, "g": 100.0, "v": 13.33, "m": 66.67, "r": 50.0, "disc": 67.67},
        "REG3.NS": {"score": 43.96, "action": "AVOID", "q": 85.71, "g": 100.0, "v": 20.0, "m": 33.33, "r": 16.66, "disc": 60.82},
    }
    assert ranked == ["REG1.NS", "REG2.NS", "REG3.NS"]
    for ticker, checks in expected.items():
        row = recs[ticker]
        comps = {c.name: c.value for c in row.components}
        assert round(float(row.score), 2) == checks["score"]
        assert row.action == checks["action"]
        assert round(float(comps["quality"] or 0.0), 2) == checks["q"]
        assert round(float(comps["growth"] or 0.0), 2) == checks["g"]
        assert round(float(comps["valuation"] or 0.0), 2) == checks["v"]
        assert round(float(comps["momentum"] or 0.0), 2) == checks["m"]
        assert round(float(comps["risk"] or 0.0), 2) == checks["r"]
        disc = next(c for c in row.components if c.name == "discovery_score")
        assert round(float(disc.value or 0.0), 2) == checks["disc"]


def test_wave32_liquidity_fail_blocks_buy_add() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0  # type: ignore[method-assign]

    candidate = CandidateInstrument("ILLQ.NS", "Illiquid", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Industrials", None)
    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        [candidate],
        {"markets": {"India": {"total_seed": 1, "eligible": 1, "partial": 0, "ineligible": 0}}, "total_candidates": 1, "eligible_candidates": 1, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"India": 1}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )
    service._fetch_live_snapshot = lambda _c, _base: _mk_live_snapshot(  # type: ignore[method-assign]
        "ILLQ.NS",
        currency="INR",
        market_cap=2e11,
        liquidity_status="FAIL",
        liquidity_score=18.0,
        median_daily_value=8e5,
        median_daily_volume=3000.0,
        trading_days=100,
    )

    result = service.generate(
        RecommendationGenerateRequest(investable_amount=5000.0, market_data_mode="live", use_demo_portfolio=False, eligible_markets=["India"])
    )
    row = next(r for r in result.recommendations if r.ticker == "ILLQ.NS")
    assert row.action not in {"BUY", "ADD"}
    assert any("low_liquidity" in risk.lower() or "challenge flag: low_liquidity" in risk.lower() for risk in row.risks)


def test_wave32_discovery_score_improvement_available_vs_unavailable() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0  # type: ignore[method-assign]

    candidates = [
        CandidateInstrument("ACCEL.NS", "Accelerating", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Healthcare", None),
        CandidateInstrument("NOIMP.NS", "No Improvement", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Healthcare", None),
    ]
    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        candidates,
        {"markets": {"India": {"total_seed": 2, "eligible": 2, "partial": 0, "ineligible": 0}}, "total_candidates": 2, "eligible_candidates": 2, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"India": 2}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )
    by_ticker = {
        "ACCEL.NS": _mk_live_snapshot("ACCEL.NS", currency="INR", market_cap=5e11, earnings_q_growth=0.45),
        "NOIMP.NS": _mk_live_snapshot("NOIMP.NS", currency="INR", market_cap=5e11, earnings_q_growth=None),
    }
    service._fetch_live_snapshot = lambda c, _base: by_ticker[c.ticker]  # type: ignore[method-assign]

    result = service.generate(
        RecommendationGenerateRequest(investable_amount=5000.0, market_data_mode="live", use_demo_portfolio=False, eligible_markets=["India"])
    )
    ranked = {r["ticker"]: r for r in result.top_ranked_candidates}
    assert ranked["ACCEL.NS"]["improvement_status"] == "AVAILABLE"
    assert ranked["NOIMP.NS"]["improvement_status"] == "UNAVAILABLE"
    assert float(ranked["ACCEL.NS"]["discovery_score"]) >= float(ranked["NOIMP.NS"]["discovery_score"])


def test_wave32_smallcap_confidence_adjustment_and_outlier_records() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0  # type: ignore[method-assign]

    candidates = [
        CandidateInstrument("LARGEF.NS", "Large Fit", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Industrials", None),
        CandidateInstrument("SMALLF.NS", "Small Fit", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Industrials", None),
        CandidateInstrument("OUTLIER.NS", "Outlier", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Industrials", None),
    ]
    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        candidates,
        {"markets": {"India": {"total_seed": 3, "eligible": 3, "partial": 0, "ineligible": 0}}, "total_candidates": 3, "eligible_candidates": 3, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"India": 3}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )

    outlier_raw = {
        "trailingPE": -100.0,
        "debtToEquity": 1_000_000.0,
        "revenueGrowth": 20.0,
        "marketCap": 5e10,
    }
    by_ticker = {
        "LARGEF.NS": _mk_live_snapshot("LARGEF.NS", currency="INR", market_cap=9e12, liquidity_status="PASS", liquidity_score=90.0),
        "SMALLF.NS": _mk_live_snapshot("SMALLF.NS", currency="INR", market_cap=8e10, liquidity_status="WATCH", liquidity_score=55.0),
        "OUTLIER.NS": _mk_live_snapshot("OUTLIER.NS", currency="INR", market_cap=5e10, raw_overrides=outlier_raw),
    }
    service._fetch_live_snapshot = lambda c, _base: by_ticker[c.ticker]  # type: ignore[method-assign]

    result = service.generate(
        RecommendationGenerateRequest(investable_amount=5000.0, market_data_mode="live", use_demo_portfolio=False, eligible_markets=["India"])
    )

    rec_by_ticker = {r.ticker: r for r in result.recommendations if r.ticker in {"LARGEF.NS", "SMALLF.NS"}}
    assert rec_by_ticker["SMALLF.NS"].confidence <= rec_by_ticker["LARGEF.NS"].confidence

    ranked = {r["ticker"]: r for r in result.top_ranked_candidates}
    outlier_records = ranked["OUTLIER.NS"]["outlier_records"]
    assert "trailingPE" in outlier_records or "debtToEquity" in outlier_records or "revenueGrowth" in outlier_records


def test_wave32_sector_concentration_and_no_forced_discovery_quota() -> None:
    service = RecommendationMVPService()
    service._fx_rate = lambda from_ccy, to_ccy: 1.0  # type: ignore[method-assign]

    candidates = [
        CandidateInstrument(f"SEC{i}.NS", f"Sec {i}", "UNAVAILABLE", "India", "NSE", "India", "INR", "Equity", "INDIA", "Technology", None)
        for i in range(12)
    ]
    service._discover_candidates = lambda _markets: (  # type: ignore[method-assign]
        candidates,
        {"markets": {"India": {"total_seed": 12, "eligible": 12, "partial": 0, "ineligible": 0}}, "total_candidates": 12, "eligible_candidates": 12, "partial_candidates": 0, "ineligible_candidates": 0},
        {"eligible_by_market": {"India": 12}, "partial_by_market": {}, "ineligible_by_market": {}, "excluded_reasons": []},
        [],
    )

    def _snap(ticker: str) -> MarketSnapshot:
        return _mk_live_snapshot(
            ticker,
            currency="INR",
            sector="Technology",
            market_cap=5e9,
            liquidity_status="FAIL",
            liquidity_score=10.0,
            median_daily_value=1e5,
            median_daily_volume=500.0,
            trading_days=80,
            earnings_q_growth=None,
        )

    service._fetch_live_snapshot = lambda c, _base: _snap(c.ticker)  # type: ignore[method-assign]
    result = service.generate(
        RecommendationGenerateRequest(investable_amount=5000.0, market_data_mode="live", use_demo_portfolio=False, eligible_markets=["India"])
    )

    concentration = result.data_quality_summary["discovery_sector_concentration"]
    assert concentration["is_concentrated"] is True

    statuses = [row["discovery_status"] for row in result.top_ranked_candidates]
    assert statuses.count("DISCOVER") == 0
