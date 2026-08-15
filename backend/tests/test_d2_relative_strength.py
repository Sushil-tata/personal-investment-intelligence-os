from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from piios_backend.services.recommendation_mvp import (
	CandidateInstrument,
	MarketSnapshot,
	RecommendationMVPService,
)


class FakeBenchmarkHistoryProvider:
	def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
		self.frames = frames
		self.calls: list[str] = []

	def history(self, ticker: str, *, period: str, interval: str) -> SimpleNamespace:
		self.calls.append(ticker)
		return SimpleNamespace(frame=self.frames[ticker], as_of="2026-08-14T00:00:00Z")


def _payload_item(ticker: str, sector: str, returns: tuple[float, float, float]) -> dict[str, object]:
	ret3m, ret6m, ret12m = returns
	market = MarketSnapshot(
		ticker=ticker,
		provider="fixture",
		mode="LIVE",
		as_of="2026-08-14T00:00:00Z",
		is_stale=False,
		fallback_reason=None,
		seeded_input=False,
		latest_price=100.0,
		daily_return_pct=0.0,
		return_1m_pct=0.0,
		return_3m_pct=ret3m,
		return_6m_pct=ret6m,
		return_12m_pct=ret12m,
		realized_volatility=0.2,
		drawdown_pct=-10.0,
		distance_from_52w_high_pct=-5.0,
		trading_currency="INR",
		sector=sector,
		portfolio_role="UNAVAILABLE",
		quality_score=None,
		growth_score=None,
		fx_required=False,
		fx_available=True,
		fx_rate_to_base=1.0,
		missing_inputs=[],
		history_observations=253,
		raw_metrics={"sector": sector},
	)
	return {
		"candidate": CandidateInstrument(
			ticker,
			ticker,
			"UNAVAILABLE",
			"India",
			"NSE",
			"India",
			"INR",
			"Equity",
			"INDIA",
			sector,
			None,
		),
		"market": market,
		"review_metrics": {
			"return_3m_pct": {"value": ret3m, "reason": None},
			"return_6m_pct": {"value": ret6m, "reason": None},
			"return_12m_pct": {"value": ret12m, "reason": None},
		},
	}


def test_d2_excess_returns_use_injected_benchmark_history_for_positive_and_negative(monkeypatch) -> None:
	prices = [95.0] * 253
	prices[0] = 80.0
	prices[126] = 90.0
	prices[189] = 100.0
	prices[-1] = 110.0
	provider = FakeBenchmarkHistoryProvider(
		{"NIFTYBEES.NS": pd.DataFrame({"Close": prices}, index=pd.bdate_range("2025-08-27", periods=253))}
	)
	service = RecommendationMVPService()
	monkeypatch.setattr("piios_backend.services.recommendation_mvp.live_feeds.history", provider.history)

	benchmark = service._fetch_benchmark_returns("India")
	payload = [
		_payload_item("POSITIVE.NS", "Technology", (20.0, 30.0, 50.0)),
		_payload_item("NEGATIVE.NS", "Financials", (0.0, 10.0, 20.0)),
	]
	service._attach_relative_strength_diagnostics(payload, {"India": benchmark})

	positive = payload[0]["relative_strength"]
	negative = payload[1]["relative_strength"]
	assert provider.calls == ["NIFTYBEES.NS"]
	assert positive["excess_return_vs_index_3m_pct"] == 10.0
	assert positive["excess_return_vs_index_6m_pct"] == 7.7778
	assert positive["excess_return_vs_index_12m_pct"] == 12.5
	assert positive["why_own_instead_of_benchmark"] == "outperforming NIFTY50 by 7.8% over 6m"
	assert negative["excess_return_vs_index_3m_pct"] == -10.0
	assert negative["excess_return_vs_index_6m_pct"] == -12.2222
	assert negative["excess_return_vs_index_12m_pct"] == -17.5
	assert negative["why_own_instead_of_benchmark"] is None


def test_d2_sector_relative_excludes_self_and_sparse_sector_is_null() -> None:
	service = RecommendationMVPService()
	payload = [
		_payload_item("TARGET.NS", "Technology", (10.0, 10.0, 10.0)),
		_payload_item("PEER1.NS", "Technology", (2.0, 2.0, 2.0)),
		_payload_item("PEER2.NS", "Technology", (4.0, 4.0, 4.0)),
		_payload_item("PEER3.NS", "Technology", (100.0, 100.0, 100.0)),
		_payload_item("SPARSE1.NS", "Financials", (8.0, 8.0, 8.0)),
		_payload_item("SPARSE2.NS", "Financials", (6.0, 6.0, 6.0)),
	]
	benchmark = {
		"benchmark_name": "NIFTY50",
		"benchmark_ticker": "NIFTYBEES.NS",
		"return_3m_pct": 5.0,
		"return_6m_pct": 5.0,
		"return_12m_pct": 5.0,
		"unavailable_reason": None,
	}

	service._attach_relative_strength_diagnostics(payload, {"India": benchmark})

	target = payload[0]["relative_strength"]
	sparse = payload[4]["relative_strength"]
	assert target["sector_relative_return_3m_pct"] == 6.0
	assert target["sector_relative_return_6m_pct"] == 6.0
	assert target["sector_relative_return_12m_pct"] == 6.0
	assert sparse["sector_relative_return_3m_pct"] is None
	assert sparse["sector_relative_return_3m_pct_reason"] == "fewer_than_3_same_sector_peers:1"


def test_d2_fetches_each_market_benchmark_once_per_request() -> None:
	service = RecommendationMVPService()
	candidates = [
		_payload_item(f"NAME{index}.NS", "Technology", (5.0, 8.0, 12.0))["candidate"]
		for index in range(5)
	]
	benchmark_calls: list[str] = []
	service._resolve_markets_concurrently = lambda *_args: []  # type: ignore[method-assign]

	def _fetch(market: str) -> dict[str, object]:
		benchmark_calls.append(market)
		return {"benchmark_name": "NIFTY50", "benchmark_ticker": "NIFTYBEES.NS"}

	service._fetch_benchmark_returns = _fetch  # type: ignore[method-assign]
	service._resolve_request_market_data_concurrently(candidates, "live", "USD")  # type: ignore[arg-type]

	assert benchmark_calls == ["India"]
