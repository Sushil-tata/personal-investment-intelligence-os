from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import math
from pathlib import Path
import re
from statistics import mean
import threading
import time
from typing import Literal
from uuid import uuid4

from piios_backend.core.guardrails import ADVISORY_BOUNDARY_TEXT
from piios_backend.schemas.portfolio import Holding
from piios_backend.schemas.recommendation import (
	AllocationRecommendation,
	InvestorMandateOverride,
	PortfolioObservation,
	PortfolioRecommendationResponse,
	RecommendationEvidence,
	RecommendationGenerateRequest,
	RecommendationLimitation,
	RecommendationScoreComponent,
)
from piios_backend.services.in_memory_store import store
from piios_backend.services.live_feeds import QuoteSnapshot, live_feeds


DataMode = Literal["LIVE", "CACHED", "DEVELOPMENT_SEED", "UNAVAILABLE"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CandidateInstrument:
	ticker: str
	instrument_name: str
	portfolio_role: str
	market: str
	exchange: str | None
	issuer_country: str | None
	trading_currency: str | None
	instrument_type: str | None
	geography: str
	sector: str | None
	risk_band: str | None


@dataclass
class MarketSnapshot:
	ticker: str
	provider: str
	mode: DataMode
	as_of: str | None
	is_stale: bool
	fallback_reason: str | None
	seeded_input: bool
	latest_price: float | None
	daily_return_pct: float | None
	return_1m_pct: float | None
	return_3m_pct: float | None
	return_6m_pct: float | None
	return_12m_pct: float | None
	realized_volatility: float | None
	drawdown_pct: float | None
	distance_from_52w_high_pct: float | None
	trading_currency: str | None
	sector: str | None
	portfolio_role: str
	quality_score: float | None
	growth_score: float | None
	fx_required: bool
	fx_available: bool
	fx_rate_to_base: float | None
	missing_inputs: list[str]
	history_observations: int = 0
	raw_metrics: dict[str, float | str | None] | None = None

_CANDIDATES: tuple[CandidateInstrument, ...] = (
	CandidateInstrument("VT", "Vanguard Total World Stock ETF", "LEGACY_DEMO", "US", "NYSEARCA", "United States", "USD", "ETF", "GLOBAL", None, None),
	CandidateInstrument("VXUS", "Vanguard Total International Stock ETF", "LEGACY_DEMO", "US", "NASDAQ", "United States", "USD", "ETF", "EX_US", None, None),
	CandidateInstrument("QUAL", "iShares MSCI USA Quality Factor ETF", "LEGACY_DEMO", "US", "NYSEARCA", "United States", "USD", "ETF", "US", None, None),
	CandidateInstrument("SCHD", "Schwab US Dividend Equity ETF", "LEGACY_DEMO", "US", "NYSEARCA", "United States", "USD", "ETF", "US", None, None),
	CandidateInstrument("BND", "Vanguard Total Bond Market ETF", "LEGACY_DEMO", "US", "NASDAQ", "United States", "USD", "ETF", "US", None, None),
	CandidateInstrument("MSFT", "Microsoft Corp.", "LEGACY_DEMO", "US", "NASDAQ", "United States", "USD", "Equity", "US", None, None),
	CandidateInstrument("GOOGL", "Alphabet Inc.", "LEGACY_DEMO", "US", "NASDAQ", "United States", "USD", "Equity", "US", None, None),
	CandidateInstrument("AMZN", "Amazon.com Inc.", "LEGACY_DEMO", "US", "NASDAQ", "United States", "USD", "Equity", "US", None, None),
	CandidateInstrument("AVGO", "Broadcom Inc.", "LEGACY_DEMO", "US", "NASDAQ", "United States", "USD", "Equity", "US", None, None),
	CandidateInstrument("V", "Visa Inc.", "LEGACY_DEMO", "US", "NYSE", "United States", "USD", "Equity", "US", None, None),
	CandidateInstrument("BRK-B", "Berkshire Hathaway Inc.", "LEGACY_DEMO", "US", "NYSE", "United States", "USD", "Equity", "US", None, None),
	CandidateInstrument("PANW", "Palo Alto Networks Inc.", "LEGACY_DEMO", "US", "NASDAQ", "United States", "USD", "Equity", "US", None, None),
	CandidateInstrument("CEG", "Constellation Energy Corp.", "LEGACY_DEMO", "US", "NASDAQ", "United States", "USD", "Equity", "US", None, None),
)

_DEV_SEED = {
	"VT": 117.0,
	"VXUS": 66.0,
	"QUAL": 182.0,
	"SCHD": 80.0,
	"BND": 71.0,
	"MSFT": 470.0,
	"GOOGL": 186.0,
	"AMZN": 198.0,
	"AVGO": 1650.0,
	"V": 285.0,
	"BRK-B": 465.0,
	"PANW": 360.0,
	"CEG": 220.0,
}

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_MARKET_TO_FILE = {
	"US": "universe_us.txt",
	"India": "universe_india.txt",
	"Singapore": "universe_singapore.txt",
}
_TICKER_ALLOWED = re.compile(r"^[A-Z0-9.-]+$")

_MARKET_CAP_BUCKET_PERCENTILES = {
	"large_min_pct": 80.0,
	"mid_min_pct": 35.0,
	"small_min_pct": 10.0,
}

_LIQUIDITY_THRESHOLDS = {
	"India": {
		"median_daily_value_pass": 25_000_000.0,
		"median_daily_value_watch": 7_500_000.0,
		"median_daily_volume_pass": 120_000.0,
		"median_daily_volume_watch": 30_000.0,
		"min_trading_days_pass": 180,
		"min_trading_days_watch": 120,
		"max_zero_volume_ratio_pass": 0.10,
		"max_zero_volume_ratio_watch": 0.22,
		"min_price_pass": 20.0,
		"min_price_watch": 8.0,
	},
	"US": {
		"median_daily_value_pass": 10_000_000.0,
		"median_daily_value_watch": 2_000_000.0,
		"median_daily_volume_pass": 150_000.0,
		"median_daily_volume_watch": 40_000.0,
		"min_trading_days_pass": 180,
		"min_trading_days_watch": 120,
		"max_zero_volume_ratio_pass": 0.06,
		"max_zero_volume_ratio_watch": 0.15,
		"min_price_pass": 5.0,
		"min_price_watch": 2.0,
	},
	"Singapore": {
		"median_daily_value_pass": 1_200_000.0,
		"median_daily_value_watch": 350_000.0,
		"median_daily_volume_pass": 60_000.0,
		"median_daily_volume_watch": 15_000.0,
		"min_trading_days_pass": 180,
		"min_trading_days_watch": 120,
		"max_zero_volume_ratio_pass": 0.12,
		"max_zero_volume_ratio_watch": 0.24,
		"min_price_pass": 0.5,
		"min_price_watch": 0.2,
	},
}

_OUTLIER_POLICY: dict[str, tuple[float | None, float | None, float | None, float | None]] = {
	# (hard_min, hard_max, winsor_min, winsor_max)
	"returnOnEquity": (-2.0, 5.0, -0.8, 1.5),
	"operatingMargins": (-1.5, 2.0, -0.5, 0.8),
	"profitMargins": (-1.5, 2.0, -0.5, 0.8),
	"revenueGrowth": (-1.0, 8.0, -0.6, 1.2),
	"earningsGrowth": (-2.0, 12.0, -1.0, 2.0),
	"earningsQuarterlyGrowth": (-2.0, 12.0, -1.0, 2.5),
	"debtToEquity": (-5.0, 2_500.0, 0.0, 500.0),
	"currentRatio": (0.0, 30.0, 0.2, 10.0),
	"trailingPE": (0.0, 1_000.0, 2.0, 120.0),
	"forwardPE": (0.0, 1_000.0, 2.0, 120.0),
	"priceToBook": (0.0, 150.0, 0.2, 25.0),
	"enterpriseToEbitda": (-200.0, 1_000.0, -40.0, 120.0),
	"marketCap": (1_000_000.0, 30_000_000_000_000.0, None, None),
	"freeCashflow": (-5_000_000_000_000.0, 5_000_000_000_000.0, None, None),
	"operatingCashflow": (-5_000_000_000_000.0, 5_000_000_000_000.0, None, None),
	"return_3m_pct": (-95.0, 1_500.0, -80.0, 400.0),
	"return_6m_pct": (-98.0, 2_000.0, -90.0, 600.0),
	"return_12m_pct": (-99.0, 4_000.0, -95.0, 1_200.0),
	"distance_from_52w_high_pct": (-99.0, 200.0, -90.0, 60.0),
	"realized_volatility": (0.0, 4.0, 0.02, 1.2),
	"max_drawdown_pct": (-100.0, 0.0, -90.0, -1.0),
}

_RELATIVE_SIZE_LABELS = {
	"LARGE": "RELATIVE_LARGE",
	"MID": "RELATIVE_MID",
	"SMALL": "RELATIVE_SMALL",
	"MICRO_OR_UNKNOWN": "RELATIVE_MICRO_OR_UNKNOWN",
}


def _now_iso() -> str:
	return datetime.now(timezone.utc).isoformat()


class RecommendationMVPService:
	def __init__(self) -> None:
		self._cache: dict[str, tuple[datetime, MarketSnapshot]] = {}
		self._cache_ttl = timedelta(minutes=60)

	def generate(self, request: RecommendationGenerateRequest) -> PortfolioRecommendationResponse:
		holdings = self._select_holdings(request.use_demo_portfolio, request.portfolio_snapshot_id)
		if request.investable_amount <= 0:
			raise ValueError("investable_amount must be greater than zero")

		mode_preference = (request.market_data_mode or "auto").strip().lower()
		if mode_preference not in {"auto", "live", "cached", "development_seed"}:
			raise ValueError("market_data_mode must be one of auto, live, cached, development_seed")

		mandate = self._build_mandate(request.mandate_override)
		observations = self._build_portfolio_observations(holdings, mandate)
		total_before = sum(h.market_value for h in holdings)
		total_after = total_before + request.investable_amount

		market_filter = self._resolve_market_filter(request.eligible_markets)
		if mode_preference == "development_seed":
			candidates = list(_CANDIDATES)
			universe_summary = {
				"markets": {"US": {"total_seed": len(candidates), "eligible": len(candidates), "partial": 0, "ineligible": 0}},
				"total_candidates": len(candidates),
				"eligible_candidates": len(candidates),
				"partial_candidates": 0,
				"ineligible_candidates": 0,
			}
			screening_summary = {
				"eligible_by_market": {"US": len(candidates)},
				"partial_by_market": {},
				"ineligible_by_market": {},
				"excluded_reasons": [],
			}
			excluded: list[dict[str, object]] = []
		else:
			candidates, universe_summary, screening_summary, excluded = self._discover_candidates(market_filter)

		market_results = self._resolve_markets_concurrently(candidates, mode_preference, request.base_currency)

		analyses: list[dict[str, object]] = []
		for candidate, market in zip(candidates, market_results):
			current_value = sum(h.market_value for h in holdings if h.ticker.upper() == candidate.ticker.upper())
			current_weight = 0.0 if total_before <= 0 else current_value / total_before
			analyses.append(
				{
					"candidate": candidate,
					"market": market,
					"current_value": current_value,
					"current_weight": current_weight,
				}
			)

		factor_payload = self._compute_factor_payloads(analyses, holdings, mandate, request.base_currency)
		sensitivity = self._build_sensitivity_from_payload(factor_payload, request.investable_amount)
		fragility_by_ticker = self._build_fragility_diagnostics(factor_payload)

		rows: list[AllocationRecommendation] = []
		for item in factor_payload:
			candidate: CandidateInstrument = item["candidate"]
			market: MarketSnapshot = item["market"]
			item["fragility_diagnostics"] = fragility_by_ticker.get(candidate.ticker)
			current_value = float(item["current_value"])
			current_weight = float(item["current_weight"])
			attractiveness = float(item["security_attractiveness_score"])
			suitability = float(item["portfolio_suitability_score"])
			combined = float(item["combined_recommendation_score"])
			confidence = float(item["confidence"])
			evidence_coverage = float(item["evidence_coverage"])
			challenge_flags = list(item["challenge_flags"])
			effective_missing = list(item["missing_fields"])

			action = self._classify_action_v31(
				current_value=current_value,
				combined_score=combined,
				attractiveness=attractiveness,
				suitability=suitability,
				evidence_coverage=evidence_coverage,
				confidence=confidence,
				critical_flags=challenge_flags,
				market=market,
			)

			components = self._components_from_factor_payload(item)
			evidence = self._evidence_from_factor_payload(item, holdings)
			risks = self._risks(candidate, market)
			for flag in challenge_flags:
				risks.append(f"Challenge flag: {flag}")

			rows.append(
				AllocationRecommendation(
					action=action,
					ticker=candidate.ticker,
					instrument_name=candidate.instrument_name,
					portfolio_role="Existing Position" if current_value > 0 else "UNAVAILABLE",
					current_value=round(current_value, 2),
					current_weight=round(current_weight, 4),
					proposed_allocation=0.0,
					proposed_total_value=round(current_value, 2),
					post_weight=round(0.0 if total_after <= 0 else current_value / total_after, 4),
					score=round(combined, 2),
					confidence=round(confidence, 3),
					market_data_provider=market.provider,
					market_data_mode=market.mode,
					market_data_as_of=market.as_of,
					is_stale=market.is_stale,
					fallback_reason=market.fallback_reason,
					seeded_input=market.seeded_input,
					rationale=self._rationale_v31(candidate, item),
					diversification_contribution=self._diversification_message(candidate, holdings, mandate),
					risks=risks,
					unavailable_inputs=effective_missing,
					conditions_to_change=self._conditions_to_change(candidate),
					components=components,
					evidence=evidence,
					diagnostics={
						"factor_score_trace": item.get("factor_score_trace", {}),
						"review_metrics": item.get("review_metrics", {}),
						"fundamental_source_retrieval_timestamp": (market.raw_metrics or {}).get("fundamentals_as_of"),
						"relative_market_cap_bucket": self._relative_market_cap_bucket(str(item.get("market_cap_bucket") or "UNKNOWN")),
						"market_cap": item.get("market_cap"),
						"market_cap_percentile": item.get("market_cap_percentile"),
						"fragility": item.get("fragility_diagnostics", {}),
					},
				)
			)

		rows = self._inject_existing_position_observations(rows, holdings, total_before, total_after)
		self._allocate_capital(rows, request.investable_amount)
		rows = self._refresh_post_allocation_weights(rows, total_after)

		top_ranked = self._build_top_ranked_candidates_v31(rows, factor_payload)
		actionable = self._build_actionable_recommendations(rows, candidates, request.base_currency)
		existing_actions = self._build_existing_holding_actions(rows)
		portfolio_before = self._portfolio_exposure_summary(holdings, request.base_currency)
		portfolio_after = self._portfolio_exposure_summary_after(holdings, rows, request.base_currency)
		data_quality = self._build_data_quality_summary_v31(rows, excluded, total_before, request.base_currency, portfolio_before, factor_payload, market_filter)

		discovery_size_counts: dict[str, int] = {
			"RELATIVE_LARGE": 0,
			"RELATIVE_MID": 0,
			"RELATIVE_SMALL": 0,
			"RELATIVE_MICRO_OR_UNKNOWN": 0,
			"UNKNOWN": 0,
		}
		discovery_status_counts: dict[str, int] = {"DISCOVER": 0, "RESEARCH": 0, "PASS": 0}
		for item in top_ranked:
			size_key = str(item.get("relative_market_cap_bucket") or "UNKNOWN")
			discovery_size_counts[size_key] = discovery_size_counts.get(size_key, 0) + 1
			status_key = str(item.get("discovery_status") or "PASS")
			discovery_status_counts[status_key] = discovery_status_counts.get(status_key, 0) + 1
		screening_summary["discovery_size_counts"] = discovery_size_counts
		screening_summary["discovery_status_counts"] = discovery_status_counts

		allocation_total = round(sum(r.proposed_allocation for r in rows), 2)
		delta = round(request.investable_amount - allocation_total, 2)

		if delta < -1.0:
			raise RuntimeError("allocation exceeded investable amount")

		overall_confidence = round(mean([r.confidence for r in rows if r.action in {"BUY", "ADD"}] or [0.35]), 3)
		modes = {r.market_data_mode for r in rows if r.action in {"BUY", "ADD"}}
		merged_mode = "MIXED" if len(modes) > 1 else (next(iter(modes)) if modes else "UNAVAILABLE")

		limitations = [
			RecommendationLimitation(
				code="ADVISORY_ONLY",
				detail=ADVISORY_BOUNDARY_TEXT,
				severity="INFO",
			)
		]
		if any(r.seeded_input for r in rows if r.action in {"BUY", "ADD"}):
			limitations.append(
				RecommendationLimitation(
					code="DEVELOPMENT_SEED",
					detail="Some market inputs used DEVELOPMENT_SEED fallback values.",
					severity="WARNING",
				)
			)
		if any(("fx_rate" in r.unavailable_inputs) for r in rows):
			limitations.append(
				RecommendationLimitation(
					code="FX_UNAVAILABLE",
					detail="One or more cross-currency candidates were not actionable because required FX rates were unavailable.",
					severity="WARNING",
				)
			)
		if any(("LOW_EVIDENCE" in r.risks or r.confidence < 0.55) for r in rows if r.action in {"BUY", "ADD"}):
			limitations.append(
				RecommendationLimitation(
					code="LOW_EVIDENCE_RISK",
					detail="At least one actionable item has reduced evidence coverage or confidence.",
					severity="WARNING",
				)
			)

		return PortfolioRecommendationResponse(
			recommendation_id=f"wave3-{uuid4()}",
			status="READY",
			as_of_timestamp=_now_iso(),
			market_data_provider="yfinance",
			market_data_mode=merged_mode,
			input_freshness=self._freshness_summary(rows),
			investable_amount=round(request.investable_amount, 2),
			allocation_total=allocation_total,
			allocation_difference=delta,
			overall_confidence=overall_confidence,
			advisory_only=True,
			portfolio_observations=observations,
			recommendations=rows,
			universe_summary=universe_summary,
			screening_summary=screening_summary,
			top_ranked_candidates=top_ranked,
			actionable_recommendations=actionable,
			existing_holding_actions=existing_actions,
			portfolio_before=portfolio_before,
			portfolio_after=portfolio_after,
			residual_cash=round(max(0.0, request.investable_amount - allocation_total), 2),
			data_quality_summary=data_quality,
			sensitivity=sensitivity,
			assumptions=self._assumptions(mandate),
			limitations=limitations,
		)

	def _resolve_market_filter(self, eligible_markets: list[str] | None) -> list[str]:
		if not eligible_markets:
			return ["US", "India", "Singapore"]
		allowed = {"us": "US", "india": "India", "singapore": "Singapore", "sg": "Singapore"}
		resolved: list[str] = []
		for item in eligible_markets:
			key = (item or "").strip().lower()
			if key in allowed and allowed[key] not in resolved:
				resolved.append(allowed[key])
		return resolved or ["US", "India", "Singapore"]

	def _compute_factor_payloads(self, analyses: list[dict[str, object]], holdings: list[Holding], mandate: dict[str, object], base_currency: str) -> list[dict[str, object]]:
		metric_global: dict[str, list[float]] = {}
		metric_sector: dict[tuple[str, str], list[float]] = {}
		market_caps_by_market: dict[str, list[float]] = {}
		factor_metric_specs: dict[str, list[tuple[str, bool]]] = {
			"QUALITY": [
				("returnOnEquity", False),
				("operatingMargins", False),
				("profitMargins", False),
				("freeCashflow", False),
				("operatingCashflow", False),
				("debtToEquity", True),
				("currentRatio", False),
			],
			"GROWTH": [
				("revenueGrowth", False),
				("earningsGrowth", False),
				("earningsQuarterlyGrowth", False),
			],
			"VALUATION": [
				("trailingPE", True),
				("forwardPE", True),
				("priceToBook", True),
				("enterpriseToEbitda", True),
				("fcfYield", False),
			],
			"MOMENTUM": [
				("return_3m_pct", False),
				("return_6m_pct", False),
				("return_12m_pct", False),
				("distance_from_52w_high_pct", False),
			],
			"RISK": [
				("realized_volatility", True),
				("max_drawdown_pct", False),
			],
		}
		all_metrics = [
			"returnOnEquity",
			"operatingMargins",
			"profitMargins",
			"freeCashflow",
			"operatingCashflow",
			"debtToEquity",
			"currentRatio",
			"revenueGrowth",
			"earningsGrowth",
			"earningsQuarterlyGrowth",
			"trailingPE",
			"forwardPE",
			"priceToBook",
			"enterpriseToEbitda",
			"marketCap",
			"return_3m_pct",
			"return_6m_pct",
			"return_12m_pct",
			"distance_from_52w_high_pct",
			"realized_volatility",
			"max_drawdown_pct",
		]
		metric_factor_map = {metric: factor for factor, specs in factor_metric_specs.items() for metric, _ in specs}

		def _unavailable_reason(raw_value: float | None, validated_value: float | None, record: dict[str, object] | None) -> str:
			if validated_value is not None:
				return ""
			if raw_value is None:
				return "missing_or_non_numeric_provider_value"
			if isinstance(record, dict) and record.get("flag"):
				return f"validation_{record.get('flag')}"
			return "unavailable_after_validation"

		def _collect(metric: str, value: float | None, sector: str | None) -> None:
			if value is None:
				return
			metric_global.setdefault(metric, []).append(value)
			if sector:
				metric_sector.setdefault((metric, sector), []).append(value)

		for row in analyses:
			market: MarketSnapshot = row["market"]  # type: ignore[assignment]
			raw = dict(market.raw_metrics or {})
			raw_provider = dict(raw)
			sector = str(raw.get("sector") or "").strip() or None
			validation_records: dict[str, dict[str, object]] = {}
			factor_score_trace: dict[str, dict[str, object]] = {}

			for metric in all_metrics:
				raw_provider_value = self._safe_float(raw_provider.get(metric))
				validated, record = self._validated_metric(metric, raw_provider_value)
				raw[metric] = validated
				if record is not None:
					validation_records[metric] = record
				policy = _OUTLIER_POLICY.get(metric)
				factor_score_trace[metric] = {
					"factor": metric_factor_map.get(metric, "NON_FACTOR"),
					"raw_provider_value": raw_provider_value,
					"validated_value": validated,
					"winsorized_or_capped": bool(isinstance(record, dict) and str(record.get("flag", "")).startswith("winsorized")),
					"validation_flag": record.get("flag") if isinstance(record, dict) else None,
					"applicable_bounds": {
						"hard_min": None if policy is None else policy[0],
						"hard_max": None if policy is None else policy[1],
						"winsor_min": None if policy is None else policy[2],
						"winsor_max": None if policy is None else policy[3],
					},
					"normalized_metric_score": None,
					"unavailable_reason": _unavailable_reason(raw_provider_value, validated, record),
				}

			market_cap = self._safe_float(raw.get("marketCap"))
			if market_cap is not None and market_cap > 0:
				market_caps_by_market.setdefault(str(row["candidate"].market), []).append(market_cap)  # type: ignore[index]

			fcf = self._safe_float(raw.get("freeCashflow"))
			fcf_yield = None
			if market_cap and market_cap > 0 and fcf is not None:
				fcf_yield = (fcf / market_cap) * 100.0
			raw["fcfYield"] = fcf_yield
			raw["validation_records"] = validation_records
			raw["factor_score_trace"] = factor_score_trace
			raw["raw_provider_metrics"] = raw_provider
			market.raw_metrics = raw

			_collect("returnOnEquity", self._safe_float(raw.get("returnOnEquity")), sector)
			_collect("operatingMargins", self._safe_float(raw.get("operatingMargins")), sector)
			_collect("profitMargins", self._safe_float(raw.get("profitMargins")), sector)
			_collect("freeCashflow", self._safe_float(raw.get("freeCashflow")), sector)
			_collect("operatingCashflow", self._safe_float(raw.get("operatingCashflow")), sector)
			_collect("debtToEquity", self._safe_float(raw.get("debtToEquity")), sector)
			_collect("currentRatio", self._safe_float(raw.get("currentRatio")), sector)
			_collect("revenueGrowth", self._safe_float(raw.get("revenueGrowth")), sector)
			_collect("earningsGrowth", self._safe_float(raw.get("earningsGrowth")), sector)
			_collect("earningsQuarterlyGrowth", self._safe_float(raw.get("earningsQuarterlyGrowth")), sector)
			_collect("trailingPE", self._safe_float(raw.get("trailingPE")), sector)
			_collect("forwardPE", self._safe_float(raw.get("forwardPE")), sector)
			_collect("priceToBook", self._safe_float(raw.get("priceToBook")), sector)
			_collect("enterpriseToEbitda", self._safe_float(raw.get("enterpriseToEbitda")), sector)
			_collect("fcfYield", self._safe_float(raw.get("fcfYield")), sector)
			_collect("return_3m_pct", self._safe_float(raw.get("return_3m_pct")), sector)
			_collect("return_6m_pct", self._safe_float(raw.get("return_6m_pct")), sector)
			_collect("return_12m_pct", self._safe_float(raw.get("return_12m_pct")), sector)
			_collect("distance_from_52w_high_pct", self._safe_float(raw.get("distance_from_52w_high_pct")), sector)
			_collect("realized_volatility", self._safe_float(raw.get("realized_volatility")), sector)
			_collect("max_drawdown_pct", self._safe_float(raw.get("max_drawdown_pct")), sector)

		def _metric_score(metric: str, value: float | None, lower_is_better: bool, sector: str | None) -> float | None:
			if value is None:
				return None
			sector_values = metric_sector.get((metric, sector or ""), []) if sector else []
			values = sector_values if len(sector_values) >= 5 else metric_global.get(metric, [])
			if not values:
				return None
			pct = self._percentile_rank(value, values)
			return round(100.0 - pct, 2) if lower_is_better else round(pct, 2)

		weights = {
			"QUALITY": 0.28,
			"GROWTH": 0.17,
			"VALUATION": 0.20,
			"MOMENTUM": 0.20,
			"RISK": 0.15,
		}

		payload: list[dict[str, object]] = []
		for row in analyses:
			candidate: CandidateInstrument = row["candidate"]  # type: ignore[assignment]
			market: MarketSnapshot = row["market"]  # type: ignore[assignment]
			raw = market.raw_metrics or {}
			sector = str(raw.get("sector") or "").strip() or None
			market_caps = market_caps_by_market.get(candidate.market, [])
			market_cap = self._safe_float(raw.get("marketCap"))
			market_cap_pct = self._percentile_rank(market_cap, market_caps) if market_cap is not None and market_caps else None
			market_cap_bucket = self._market_cap_bucket(market_cap, market_cap_pct)
			liquidity_status = str(raw.get("liquidity_status") or "UNAVAILABLE")

			metric_scores = {
				"returnOnEquity": _metric_score("returnOnEquity", self._safe_float(raw.get("returnOnEquity")), False, sector),
				"operatingMargins": _metric_score("operatingMargins", self._safe_float(raw.get("operatingMargins")), False, sector),
				"profitMargins": _metric_score("profitMargins", self._safe_float(raw.get("profitMargins")), False, sector),
				"freeCashflow": _metric_score("freeCashflow", self._safe_float(raw.get("freeCashflow")), False, sector),
				"operatingCashflow": _metric_score("operatingCashflow", self._safe_float(raw.get("operatingCashflow")), False, sector),
				"debtToEquity": _metric_score("debtToEquity", self._safe_float(raw.get("debtToEquity")), True, sector),
				"currentRatio": _metric_score("currentRatio", self._safe_float(raw.get("currentRatio")), False, sector),
				"revenueGrowth": _metric_score("revenueGrowth", self._safe_float(raw.get("revenueGrowth")), False, sector),
				"earningsGrowth": _metric_score("earningsGrowth", self._safe_float(raw.get("earningsGrowth")), False, sector),
				"earningsQuarterlyGrowth": _metric_score("earningsQuarterlyGrowth", self._safe_float(raw.get("earningsQuarterlyGrowth")), False, sector),
				"trailingPE": _metric_score("trailingPE", self._safe_float(raw.get("trailingPE")), True, sector),
				"forwardPE": _metric_score("forwardPE", self._safe_float(raw.get("forwardPE")), True, sector),
				"priceToBook": _metric_score("priceToBook", self._safe_float(raw.get("priceToBook")), True, sector),
				"enterpriseToEbitda": _metric_score("enterpriseToEbitda", self._safe_float(raw.get("enterpriseToEbitda")), True, sector),
				"fcfYield": _metric_score("fcfYield", self._safe_float(raw.get("fcfYield")), False, sector),
				"return_3m_pct": _metric_score("return_3m_pct", self._safe_float(raw.get("return_3m_pct")), False, sector),
				"return_6m_pct": _metric_score("return_6m_pct", self._safe_float(raw.get("return_6m_pct")), False, sector),
				"return_12m_pct": _metric_score("return_12m_pct", self._safe_float(raw.get("return_12m_pct")), False, sector),
				"distance_from_52w_high_pct": _metric_score("distance_from_52w_high_pct", self._safe_float(raw.get("distance_from_52w_high_pct")), False, sector),
				"realized_volatility": _metric_score("realized_volatility", self._safe_float(raw.get("realized_volatility")), True, sector),
				"max_drawdown_pct": _metric_score("max_drawdown_pct", self._safe_float(raw.get("max_drawdown_pct")), False, sector),
			}

			quality_parts = [metric_scores[m] for m, _ in factor_metric_specs["QUALITY"]]
			growth_parts = [metric_scores[m] for m, _ in factor_metric_specs["GROWTH"]]
			valuation_parts = [metric_scores[m] for m, _ in factor_metric_specs["VALUATION"]]
			momentum_parts = [metric_scores[m] for m, _ in factor_metric_specs["MOMENTUM"]]
			risk_parts = [metric_scores[m] for m, _ in factor_metric_specs["RISK"]]

			factor_scores = {
				"QUALITY": self._mean_or_none(quality_parts),
				"GROWTH": self._mean_or_none(growth_parts),
				"VALUATION": self._mean_or_none(valuation_parts),
				"MOMENTUM": self._mean_or_none(momentum_parts),
				"RISK": self._mean_or_none(risk_parts),
			}

			factor_score_trace = raw.get("factor_score_trace") if isinstance(raw.get("factor_score_trace"), dict) else {}
			for metric, normalized_score in metric_scores.items():
				entry = factor_score_trace.get(metric)
				if not isinstance(entry, dict):
					continue
				entry["normalized_metric_score"] = normalized_score
				factor_name = str(entry.get("factor") or "")
				entry["factor_score"] = factor_scores.get(factor_name)
				if normalized_score is None and entry.get("validated_value") is not None and not entry.get("unavailable_reason"):
					entry["unavailable_reason"] = "insufficient_cross_sectional_context"

			review_metrics: dict[str, dict[str, object]] = {}
			raw_provider = raw.get("raw_provider_metrics") if isinstance(raw.get("raw_provider_metrics"), dict) else {}
			validation_records = raw.get("validation_records") if isinstance(raw.get("validation_records"), dict) else {}

			def _review_metric(metric_key: str, label: str) -> None:
				validated_value = self._safe_float(raw.get(metric_key))
				raw_provider_value = self._safe_float(raw_provider.get(metric_key))
				record = validation_records.get(metric_key) if isinstance(validation_records.get(metric_key), dict) else None
				reason = _unavailable_reason(raw_provider_value, validated_value, record)
				review_metrics[label] = {
					"value": validated_value if validated_value is not None else "UNAVAILABLE",
					"reason": None if validated_value is not None else reason,
				}

			_review_metric("operatingCashflow", "operating_cash_flow")
			_review_metric("freeCashflow", "free_cash_flow")
			_review_metric("debtToEquity", "debt_to_equity")
			if self._safe_float(raw.get("fcfYield")) is not None:
				review_metrics["fcf_yield"] = {"value": self._safe_float(raw.get("fcfYield")), "reason": None}
			else:
				fcf_unavailable = review_metrics["free_cash_flow"]["value"] == "UNAVAILABLE"
				mcap_unavailable = market_cap is None or market_cap <= 0
				if fcf_unavailable:
					reason = "free_cash_flow_unavailable"
				elif mcap_unavailable:
					reason = "market_cap_unavailable_or_non_positive"
				else:
					reason = "unavailable_after_validation"
				review_metrics["fcf_yield"] = {"value": "UNAVAILABLE", "reason": reason}

			_review_metric("return_3m_pct", "return_3m_pct")
			_review_metric("return_6m_pct", "return_6m_pct")
			_review_metric("return_12m_pct", "return_12m_pct")
			_review_metric("realized_volatility", "volatility")
			_review_metric("max_drawdown_pct", "maximum_drawdown")
			_review_metric("distance_from_52w_high_pct", "distance_from_52w_high")

			available_weights = 0.0
			weighted_sum = 0.0
			for name, score in factor_scores.items():
				if score is None:
					continue
				w = weights[name]
				weighted_sum += score * w
				available_weights += w
			attractiveness = (weighted_sum / available_weights) if available_weights > 0 else 0.0

			suitability = self._portfolio_suitability_score(candidate, market, float(row["current_weight"]), holdings, base_currency)

			total_evidence_points = 20 + (1 if market.fx_required else 0)
			available_points = sum(1 for v in quality_parts + growth_parts + valuation_parts + momentum_parts + risk_parts if v is not None)
			if market.history_observations >= 252:
				available_points += 3
			elif market.history_observations >= 126:
				available_points += 2
			elif market.history_observations >= 63:
				available_points += 1
			if market.fx_required and market.fx_available:
				available_points += 1
			evidence_coverage = self._bounded(available_points / max(1, total_evidence_points), 0.0, 1.0)

			confidence = self._bounded(0.95 * evidence_coverage, 0.05, 0.95)
			if market.mode == "CACHED":
				confidence = self._bounded(confidence - 0.10, 0.05, 0.95)
			if market.mode == "UNAVAILABLE":
				confidence = self._bounded(confidence - 0.30, 0.05, 0.95)
			if market.history_observations < 126:
				confidence = self._bounded(confidence - 0.08, 0.05, 0.95)
			if market_cap_bucket == "SMALL":
				confidence = self._bounded(confidence - (0.03 if liquidity_status == "PASS" else 0.07), 0.05, 0.95)
			elif market_cap_bucket == "MICRO_OR_UNKNOWN":
				confidence = self._bounded(confidence - (0.05 if evidence_coverage >= 0.60 else 0.10), 0.05, 0.95)

			investability_status, investability_reasons = self._minimum_investability_gate(
				market=market,
				market_cap_bucket=market_cap_bucket,
				liquidity_status=liquidity_status,
				evidence_coverage=evidence_coverage,
			)

			combined = (attractiveness * 0.65) + (suitability * 0.35)
			if evidence_coverage < 0.45:
				combined *= 0.85
			if market.fx_required and not market.fx_available:
				combined *= 0.92
			if investability_status == "FAIL":
				combined *= 0.82

			discovery_score, improvement_status, discovery_reason_codes = self._discovery_score(
				item={
					"quality_score": factor_scores["QUALITY"],
					"growth_score": factor_scores["GROWTH"],
					"valuation_score": factor_scores["VALUATION"],
					"momentum_score": factor_scores["MOMENTUM"],
					"risk_score": factor_scores["RISK"],
					"evidence_coverage": evidence_coverage,
				},
				market=market,
				market_cap_bucket=market_cap_bucket,
				liquidity_status=liquidity_status,
			)
			discovery_status = "PASS"
			if discovery_score >= 70.0 and investability_status != "FAIL" and liquidity_status in {"PASS", "WATCH"}:
				discovery_status = "DISCOVER"
			elif discovery_score >= 55.0:
				discovery_status = "RESEARCH"

			missing_fields = sorted(set(market.missing_inputs + [
				name.lower() for name, score in factor_scores.items() if score is None
			]))

			item: dict[str, object] = {
				"candidate": candidate,
				"market": market,
				"current_value": row["current_value"],
				"current_weight": row["current_weight"],
				"quality_score": factor_scores["QUALITY"],
				"growth_score": factor_scores["GROWTH"],
				"valuation_score": factor_scores["VALUATION"],
				"momentum_score": factor_scores["MOMENTUM"],
				"risk_score": factor_scores["RISK"],
				"security_attractiveness_score": round(attractiveness, 2),
				"portfolio_suitability_score": round(suitability, 2),
				"combined_recommendation_score": round(combined, 2),
				"discovery_score": discovery_score,
				"discovery_status": discovery_status,
				"improvement_status": improvement_status,
				"discovery_reason_codes": discovery_reason_codes,
				"evidence_coverage": round(evidence_coverage, 4),
				"confidence": round(confidence, 4),
				"market_cap": market_cap,
				"market_cap_bucket": market_cap_bucket,
				"market_cap_percentile": None if market_cap_pct is None else round(market_cap_pct, 2),
				"relative_market_cap_bucket": self._relative_market_cap_bucket(market_cap_bucket),
				"liquidity_status": liquidity_status,
				"liquidity_score": self._safe_float(raw.get("liquidity_score")),
				"median_daily_value": self._safe_float(raw.get("median_daily_value")),
				"median_daily_volume": self._safe_float(raw.get("median_daily_volume")),
				"trading_days": int(raw.get("trading_days") or 0),
				"active_trading_days": int(raw.get("active_trading_days") or 0),
				"zero_volume_days": int(raw.get("zero_volume_days") or 0),
				"investability_status": investability_status,
				"investability_reasons": investability_reasons,
				"outlier_records": raw.get("validation_records") if isinstance(raw.get("validation_records"), dict) else {},
				"factor_score_trace": factor_score_trace,
				"review_metrics": review_metrics,
				"missing_fields": missing_fields,
				"factor_weights": weights,
			}
			challenge_flags = self._challenge_flags(item, holdings, base_currency)
			challenge_flags.extend(investability_reasons)
			if liquidity_status == "FAIL":
				challenge_flags.append("low_liquidity")
			elif liquidity_status == "WATCH":
				challenge_flags.append("liquidity_watch")
			item["challenge_flags"] = sorted(set(challenge_flags))
			payload.append(item)

		payload.sort(key=lambda x: float(x["combined_recommendation_score"]), reverse=True)
		for idx, row in enumerate(payload, start=1):
			row["rank"] = idx
		return payload

	def _build_sensitivity_from_payload(self, payload: list[dict[str, object]], investable_amount: float) -> dict[str, object]:
		if not payload:
			return {
				"classification": "UNSTABLE",
				"scenarios": [],
				"top_candidates_stable": False,
				"action_stable": False,
				"funded_stable": False,
			}

		base_weights = payload[0].get("factor_weights", {"QUALITY": 0.28, "GROWTH": 0.17, "VALUATION": 0.20, "MOMENTUM": 0.20, "RISK": 0.15})
		top_n = min(10, max(3, len(payload) // 2 if len(payload) > 3 else len(payload)))
		base_rows = self._scenario_rows(payload, {k: float(v) for k, v in base_weights.items()}, investable_amount)
		base_scores = {row["ticker"]: float(row["combined_score"]) for row in base_rows}
		base_top = [row["ticker"] for row in base_rows[:top_n]]
		base_top_set = set(base_top)
		base_actionable = {row["ticker"] for row in base_rows if row["action"] in {"BUY", "ADD"}}
		base_funded = {row["ticker"] for row in base_rows if row["funded"]}
		base_top_avg = mean([base_scores[ticker] for ticker in base_top]) if base_top else 0.0

		scenarios: list[dict[str, object]] = []
		ranking_hits = 0
		action_hits = 0
		funded_hits = 0
		for factor in ["QUALITY", "GROWTH", "VALUATION", "MOMENTUM", "RISK"]:
			for direction in (-0.10, 0.10):
				w = {k: float(v) for k, v in base_weights.items()}  # type: ignore[arg-type]
				w[factor] = max(0.01, w[factor] * (1.0 + direction))
				total = sum(w.values())
				for key in w:
					w[key] = w[key] / total

				scenario_rows = self._scenario_rows(payload, w, investable_amount)
				scenario_scores = {row["ticker"]: float(row["combined_score"]) for row in scenario_rows}
				scenario_top = [row["ticker"] for row in scenario_rows[:top_n]]
				scenario_top_set = set(scenario_top)
				scenario_actionable = {row["ticker"] for row in scenario_rows if row["action"] in {"BUY", "ADD"}}
				scenario_funded = {row["ticker"] for row in scenario_rows if row["funded"]}

				ranking_jaccard = self._jaccard(base_top_set, scenario_top_set)
				action_jaccard = self._jaccard(base_actionable, scenario_actionable)
				funded_jaccard = self._jaccard(base_funded, scenario_funded)
				if ranking_jaccard >= 0.7:
					ranking_hits += 1
				if action_jaccard >= 0.7:
					action_hits += 1
				if funded_jaccard >= 0.7:
					funded_hits += 1

				scenario_base_top_avg = mean([scenario_scores[ticker] for ticker in base_top if ticker in scenario_scores]) if base_top else 0.0
				relative_shift = 0.0 if math.isclose(base_top_avg, 0.0, abs_tol=1e-9) else ((scenario_base_top_avg / base_top_avg) - 1.0) * 100.0
				stability_avg = (ranking_jaccard + action_jaccard + funded_jaccard) / 3.0
				scenarios.append(
					{
						"name": f"{factor}_{'up' if direction > 0 else 'down'}_10pct",
						"shock_pct": round(direction * 100.0, 1),
						"relative_score_shift": round(relative_shift, 2),
						"implied_confidence_shift": round((stability_avg - 1.0) * 0.2, 3),
						"jaccard_with_base": round(ranking_jaccard, 4),
						"ranking_jaccard_with_base": round(ranking_jaccard, 4),
						"action_jaccard_with_base": round(action_jaccard, 4),
						"funded_jaccard_with_base": round(funded_jaccard, 4),
						"scenario_top_n": scenario_top,
						"scenario_actionable": sorted(scenario_actionable),
						"scenario_funded": sorted(scenario_funded),
					}
				)

		scenario_count = max(1, len(scenarios))
		ranking_ratio = ranking_hits / scenario_count
		action_ratio = action_hits / scenario_count
		funded_ratio = funded_hits / scenario_count
		stability_ratio = min(ranking_ratio, action_ratio, funded_ratio)
		if stability_ratio >= 0.8:
			classification = "STABLE"
		elif stability_ratio >= 0.5:
			classification = "MODERATELY_SENSITIVE"
		else:
			classification = "UNSTABLE"

		return {
			"classification": classification,
			"comparison_basis": "top_n_ranking_vs_actionable_vs_funded_sets",
			"top_n_count": top_n,
			"universe_count": len(payload),
			"base_top_n": base_top,
			"base_actionable": sorted(base_actionable),
			"base_funded": sorted(base_funded),
			"scenarios": scenarios,
			"top_candidates_stable": ranking_ratio >= 0.8,
			"action_stable": action_ratio >= 0.8,
			"funded_stable": funded_ratio >= 0.8,
		}

	def _scenario_rows(self, payload: list[dict[str, object]], factor_weights: dict[str, float], investable_amount: float) -> list[dict[str, object]]:
		rows: list[dict[str, object]] = []
		for item in payload:
			attractiveness, combined = self._scenario_scores(item, factor_weights)
			market: MarketSnapshot = item["market"]  # type: ignore[assignment]
			action = self._classify_action_v31(
				current_value=float(item.get("current_value") or 0.0),
				combined_score=combined,
				attractiveness=attractiveness,
				suitability=float(item.get("portfolio_suitability_score") or 0.0),
				evidence_coverage=float(item.get("evidence_coverage") or 0.0),
				confidence=float(item.get("confidence") or 0.0),
				critical_flags=list(item.get("challenge_flags") or []),
				market=market,
			)
			rows.append(
				{
					"ticker": self._candidate_ticker(item),
					"combined_score": round(combined, 4),
					"attractiveness": round(attractiveness, 4),
					"action": action,
					"funded": False,
					"current_value": float(item.get("current_value") or 0.0),
					"confidence": float(item.get("confidence") or 0.0),
					"current_weight": float(item.get("current_weight") or 0.0),
					"market": market,
				}
			)

		rows.sort(key=lambda row: float(row["combined_score"]), reverse=True)
		funded = self._scenario_funded_set(rows, investable_amount)
		for row in rows:
			row["funded"] = row["ticker"] in funded
		return rows

	def _scenario_scores(self, item: dict[str, object], factor_weights: dict[str, float]) -> tuple[float, float]:
		factor_values = {
			"QUALITY": item.get("quality_score"),
			"GROWTH": item.get("growth_score"),
			"VALUATION": item.get("valuation_score"),
			"MOMENTUM": item.get("momentum_score"),
			"RISK": item.get("risk_score"),
		}
		usable_weight = 0.0
		weighted_sum = 0.0
		for key, value in factor_values.items():
			if isinstance(value, (int, float)):
				weighted_sum += float(value) * factor_weights[key]
				usable_weight += factor_weights[key]
		attractiveness = (weighted_sum / usable_weight) if usable_weight > 0 else 0.0
		combined = (attractiveness * 0.65) + (float(item.get("portfolio_suitability_score") or 0.0) * 0.35)
		if float(item.get("evidence_coverage") or 0.0) < 0.45:
			combined *= 0.85
		market: MarketSnapshot = item["market"]  # type: ignore[assignment]
		if market.fx_required and not market.fx_available:
			combined *= 0.92
		return attractiveness, combined

	def _scenario_funded_set(self, scenario_rows: list[dict[str, object]], investable_amount: float) -> set[str]:
		allocation_rows: list[AllocationRecommendation] = []
		for row in scenario_rows:
			if row["action"] not in {"BUY", "ADD"}:
				continue
			market: MarketSnapshot = row["market"]  # type: ignore[assignment]
			allocation_rows.append(
				AllocationRecommendation(
					action=str(row["action"]),
					ticker=str(row["ticker"]),
					instrument_name=str(row["ticker"]),
					portfolio_role="UNAVAILABLE",
					current_value=float(row["current_value"]),
					current_weight=float(row["current_weight"]),
					proposed_allocation=0.0,
					proposed_total_value=float(row["current_value"]),
					post_weight=0.0,
					score=round(float(row["combined_score"]), 2),
					confidence=float(row["confidence"]),
					market_data_provider=market.provider,
					market_data_mode=market.mode,
					market_data_as_of=market.as_of,
					is_stale=market.is_stale,
					fallback_reason=market.fallback_reason,
					seeded_input=market.seeded_input,
					rationale="sensitivity_scenario",
					diversification_contribution="sensitivity_scenario",
					risks=[],
					unavailable_inputs=[],
					conditions_to_change=[],
					components=[],
					evidence=[],
				)
			)
		self._allocate_capital(allocation_rows, investable_amount)
		return {row.ticker for row in allocation_rows if row.proposed_allocation > 0.0}

	@staticmethod
	def _candidate_ticker(item: dict[str, object]) -> str:
		candidate: CandidateInstrument = item["candidate"]  # type: ignore[assignment]
		return str(candidate.ticker).upper()

	@staticmethod
	def _jaccard(left: set[str], right: set[str]) -> float:
		if not left and not right:
			return 1.0
		union = left.union(right)
		if not union:
			return 1.0
		return len(left.intersection(right)) / len(union)

	def _portfolio_suitability_score(self, candidate: CandidateInstrument, market: MarketSnapshot, current_weight: float, holdings: list[Holding], base_currency: str) -> float:
		positions: list[tuple[str, str, str, float]] = []
		for h in holdings:
			fx = self._fx_rate((h.currency or base_currency).upper(), base_currency.upper())
			if fx is None:
				continue
			positions.append((h.ticker.upper(), h.geography or "Unknown", (h.currency or base_currency).upper(), float(h.market_value) * fx))

		total = sum(v for _, _, _, v in positions) or 1.0
		country_weights: dict[str, float] = {}
		currency_weights: dict[str, float] = {}
		for _, country, ccy, v in positions:
			country_weights[country] = country_weights.get(country, 0.0) + (v / total)
			currency_weights[ccy] = currency_weights.get(ccy, 0.0) + (v / total)

		candidate_country = self._country_for_market(candidate.market)
		candidate_ccy = (candidate.trading_currency or base_currency).upper()
		india_weight = country_weights.get("India", 0.0)
		country_conc = country_weights.get(candidate_country, 0.0)
		currency_conc = currency_weights.get(candidate_ccy, 0.0)

		score = 55.0
		if india_weight > 0.55 and candidate_country != "India":
			score += 18.0
		if candidate_country == "India" and india_weight > 0.60:
			score -= 14.0
		if country_conc > 0.45:
			score -= 8.0
		if currency_conc > 0.55:
			score -= 8.0
		if current_weight > 0.12:
			score -= min(20.0, current_weight * 120.0)
		if market.fx_required and not market.fx_available:
			score -= 16.0
		return self._bounded(score, 0.0, 100.0)

	def _challenge_flags(self, item: dict[str, object], holdings: list[Holding], base_currency: str) -> list[str]:
		market: MarketSnapshot = item["market"]  # type: ignore[assignment]
		raw = market.raw_metrics or {}
		flags: list[str] = []
		liquidity_status = str(item.get("liquidity_status") or raw.get("liquidity_status") or "UNAVAILABLE")
		market_cap_bucket = str(item.get("market_cap_bucket") or "UNKNOWN")

		valuation = item.get("valuation_score")
		if isinstance(valuation, (int, float)) and valuation < 30.0:
			flags.append("valuation_extreme")

		if isinstance(item.get("evidence_coverage"), (int, float)) and float(item["evidence_coverage"]) < 0.55:
			flags.append("weak_fundamental_coverage")

		momentum = item.get("momentum_score")
		others = [item.get("quality_score"), item.get("growth_score"), item.get("valuation_score"), item.get("risk_score")]
		others_f = [float(x) for x in others if isinstance(x, (int, float))]
		if isinstance(momentum, (int, float)) and others_f and (float(momentum) - mean(others_f)) > 22.0:
			flags.append("momentum_dominating_score")

		de = self._safe_float(raw.get("debtToEquity"))
		if de is not None and de > 250.0:
			flags.append("high_leverage")

		vol = self._safe_float(raw.get("realized_volatility"))
		if vol is not None and vol > 0.45:
			flags.append("high_volatility")

		drawdown = self._safe_float(raw.get("max_drawdown_pct"))
		if drawdown is not None and drawdown < -35.0:
			flags.append("large_drawdown")

		if liquidity_status == "FAIL":
			flags.append("low_liquidity")
		elif liquidity_status == "WATCH":
			flags.append("liquidity_watch")

		if market_cap_bucket in {"SMALL", "MICRO_OR_UNKNOWN", "UNKNOWN"} and market.history_observations < 126:
			flags.append("short_trading_history")

		if market_cap_bucket in {"MICRO_OR_UNKNOWN", "UNKNOWN"} and float(item.get("evidence_coverage") or 0.0) < 0.60:
			flags.append("smallcap_data_gap")

		if isinstance(item.get("discovery_score"), (int, float)) and isinstance(momentum, (int, float)):
			if float(item["discovery_score"]) > 70.0 and float(momentum) > 70.0 and float(item.get("growth_score") or 0.0) < 45.0:
				flags.append("price_momentum_unconfirmed_by_fundamentals")

		if market.fx_required and not market.fx_available:
			flags.append("fx_unavailable")

		if isinstance(item.get("confidence"), (int, float)) and float(item["confidence"]) < 0.6:
			flags.append("low_evidence_confidence")

		current_weight = float(item.get("current_weight") or 0.0)
		if current_weight > 0.12:
			flags.append("single_name_exposure")

		return sorted(set(flags))

	def _classify_action_v31(
		self,
		current_value: float,
		combined_score: float,
		attractiveness: float,
		suitability: float,
		evidence_coverage: float,
		confidence: float,
		critical_flags: list[str],
		market: MarketSnapshot,
	) -> str:
		if current_value > 0 and (combined_score < 45.0 or confidence < 0.35):
			return "REDUCE"
		if market.mode == "UNAVAILABLE" or market.latest_price is None:
			return "HOLD" if current_value > 0 else "RESEARCH"
		if market.fx_required and not market.fx_available:
			return "HOLD" if current_value > 0 else "RESEARCH"

		hard_flags = {
			"high_leverage",
			"large_drawdown",
			"fx_unavailable",
			"low_evidence_confidence",
			"low_liquidity",
			"insufficient_evidence",
			"market_data_unavailable",
			"short_trading_history",
		}
		if hard_flags.intersection(set(critical_flags)):
			if current_value > 0 and combined_score >= 55.0:
				return "HOLD"
			return "RESEARCH"

		if evidence_coverage >= 0.60 and confidence >= 0.65 and attractiveness >= 65.0 and suitability >= 55.0 and combined_score >= 68.0:
			return "ADD" if current_value > 0 else "BUY"
		if current_value > 0 and combined_score >= 55.0:
			return "HOLD"
		if combined_score >= 45.0:
			return "RESEARCH"
		return "AVOID"

	def _components_from_factor_payload(self, item: dict[str, object]) -> list[RecommendationScoreComponent]:
		factor_weights = item.get("factor_weights") or {"QUALITY": 0.28, "GROWTH": 0.17, "VALUATION": 0.20, "MOMENTUM": 0.20, "RISK": 0.15}
		liquidity_status = str(item.get("liquidity_status") or "UNAVAILABLE")
		liquidity_score = item.get("liquidity_score")
		market_cap_bucket = self._relative_market_cap_bucket(str(item.get("market_cap_bucket") or "UNKNOWN"))
		discovery_status = str(item.get("discovery_status") or "PASS")
		out = [
			RecommendationScoreComponent(name="quality", value=item.get("quality_score"), weight=float(factor_weights["QUALITY"]), status="PASS" if item.get("quality_score") is not None else "UNAVAILABLE", explanation="Cross-sectional profitability and balance-sheet quality percentile."),
			RecommendationScoreComponent(name="growth", value=item.get("growth_score"), weight=float(factor_weights["GROWTH"]), status="PASS" if item.get("growth_score") is not None else "UNAVAILABLE", explanation="Cross-sectional revenue and earnings growth percentile."),
			RecommendationScoreComponent(name="valuation", value=item.get("valuation_score"), weight=float(factor_weights["VALUATION"]), status="PASS" if item.get("valuation_score") is not None else "UNAVAILABLE", explanation="Cross-sectional valuation attractiveness percentile."),
			RecommendationScoreComponent(name="momentum", value=item.get("momentum_score"), weight=float(factor_weights["MOMENTUM"]), status="PASS" if item.get("momentum_score") is not None else "UNAVAILABLE", explanation="3M/6M/12M and distance-to-high momentum percentile."),
			RecommendationScoreComponent(name="risk", value=item.get("risk_score"), weight=float(factor_weights["RISK"]), status="PASS" if item.get("risk_score") is not None else "UNAVAILABLE", explanation="Volatility and drawdown risk percentile (lower risk scores better)."),
			RecommendationScoreComponent(name="security_attractiveness", value=item.get("security_attractiveness_score"), weight=0.65, status="PASS", explanation="Portfolio-independent company attractiveness."),
			RecommendationScoreComponent(name="portfolio_suitability", value=item.get("portfolio_suitability_score"), weight=0.35, status="PASS", explanation="Portfolio-fit score from concentration and diversification context."),
			RecommendationScoreComponent(name="discovery_score", value=item.get("discovery_score"), weight=0.00, status=discovery_status, explanation="Emerging-opportunity discovery lens (separate from conviction/action score)."),
			RecommendationScoreComponent(name="liquidity_score", value=liquidity_score if isinstance(liquidity_score, (int, float)) else None, weight=0.00, status=liquidity_status, explanation="Liquidity gate built from traded value, volume, activity, and price history."),
			RecommendationScoreComponent(name="market_cap_bucket", value=item.get("market_cap_percentile") if isinstance(item.get("market_cap_percentile"), (int, float)) else None, weight=0.00, status=market_cap_bucket, explanation="Cross-sectional size bucket percentile within market universe."),
			RecommendationScoreComponent(name="evidence_coverage", value=(float(item.get("evidence_coverage") or 0.0) * 100.0), weight=0.00, status="PASS", explanation="Share of intended evidence that is actually available."),
		]
		return out

	def _evidence_from_factor_payload(self, item: dict[str, object], holdings: list[Holding]) -> list[RecommendationEvidence]:
		market: MarketSnapshot = item["market"]  # type: ignore[assignment]
		raw = market.raw_metrics or {}
		out = [
			RecommendationEvidence(code="MARKET_HISTORY_OBS", detail=f"{market.history_observations} daily observations used for returns/risk metrics.", source=market.provider),
			RecommendationEvidence(code="EVIDENCE_COVERAGE", detail=f"Coverage {round(float(item.get('evidence_coverage') or 0.0) * 100.0, 1)}%.", source="wave3_scoring_engine"),
			RecommendationEvidence(code="MARKET_CAP_BUCKET", detail=f"relative_market_cap_bucket={item.get('relative_market_cap_bucket', 'UNKNOWN')}; market_cap={item.get('market_cap')}; market_cap_percentile={item.get('market_cap_percentile')}", source=str(raw.get("fundamentals_provider") or market.provider)),
			RecommendationEvidence(code="LIQUIDITY_PROFILE", detail=f"status={item.get('liquidity_status')}; score={item.get('liquidity_score')}; median_daily_value={item.get('median_daily_value')}; trading_days={item.get('trading_days')}", source=market.provider),
			RecommendationEvidence(code="DISCOVERY_SCORE", detail=f"discovery_score={item.get('discovery_score')}; status={item.get('discovery_status')}; reasons={','.join(list(item.get('discovery_reason_codes') or []))}", source="wave3_discovery_layer"),
		]
		for key in ["returnOnEquity", "operatingMargins", "profitMargins", "revenueGrowth", "earningsGrowth", "trailingPE", "forwardPE", "priceToBook", "enterpriseToEbitda"]:
			val = raw.get(key)
			if isinstance(val, (int, float)):
				out.append(RecommendationEvidence(code=f"RAW_{key}", detail=f"{key}={round(float(val), 6)}", source=str(raw.get("fundamentals_provider") or market.provider)))
		for metric, record in (item.get("outlier_records") or {}).items():
			if isinstance(record, dict):
				out.append(
					RecommendationEvidence(
						code=f"OUTLIER_{metric}",
						detail=f"raw={record.get('raw')} validated={record.get('validated')} flag={record.get('flag')}",
						source="wave3_outlier_validation",
					)
				)
		return out[:20]

	def _rationale_v31(self, candidate: CandidateInstrument, item: dict[str, object]) -> str:
		factors = [
			("quality", item.get("quality_score")),
			("growth", item.get("growth_score")),
			("valuation", item.get("valuation_score")),
			("momentum", item.get("momentum_score")),
			("risk", item.get("risk_score")),
		]
		known = [(n, float(v)) for n, v in factors if isinstance(v, (int, float))]
		known.sort(key=lambda x: x[1], reverse=True)
		top = ", ".join([f"{name}:{round(score, 1)}" for name, score in known[:2]]) if known else "limited available factors"
		flags = list(item.get("challenge_flags") or [])
		discovery_status = str(item.get("discovery_status") or "PASS")
		discovery_reasons = list(item.get("discovery_reason_codes") or [])
		discovery_text = ", ".join(discovery_reasons[:2]) if discovery_reasons else "limited_emergent_signals"
		if flags:
			return f"{candidate.ticker} ranked on {top}; discovery={discovery_status} ({discovery_text}); challenge flags: {', '.join(flags[:2])}."
		return f"{candidate.ticker} ranked on {top}; discovery={discovery_status} ({discovery_text}) with balanced portfolio suitability."

	def _build_top_ranked_candidates_v31(self, rows: list[AllocationRecommendation], payload: list[dict[str, object]]) -> list[dict[str, object]]:
		by_ticker = {str(item["candidate"].ticker).upper(): item for item in payload}
		ordered = sorted(rows, key=lambda r: r.score, reverse=True)
		out: list[dict[str, object]] = []
		for idx, row in enumerate(ordered[:50], start=1):
			item = by_ticker.get(row.ticker.upper())
			candidate: CandidateInstrument | None = None if item is None else item["candidate"]  # type: ignore[assignment]
			market: MarketSnapshot | None = None if item is None else item["market"]  # type: ignore[assignment]
			sector = None if market is None else (market.raw_metrics or {}).get("sector")
			out.append(
				{
					"rank": idx,
					"market": candidate.market if candidate else "US",
					"ticker": row.ticker,
					"company": row.instrument_name,
					"exchange": candidate.exchange if candidate else None,
					"issuer_country": candidate.issuer_country if candidate else None,
					"trading_currency": candidate.trading_currency if candidate else None,
					"instrument_type": candidate.instrument_type if candidate else None,
					"sector": sector,
					"status": "ELIGIBLE",
					"evidence_coverage": round(float(item.get("evidence_coverage") or 0.0), 4) if item else 0.0,
					"security_attractiveness_score": item.get("security_attractiveness_score") if item else None,
					"portfolio_suitability_score": item.get("portfolio_suitability_score") if item else None,
					"combined_recommendation_score": row.score,
					"discovery_score": item.get("discovery_score") if item else None,
					"discovery_status": item.get("discovery_status") if item else "PASS",
					"improvement_status": item.get("improvement_status") if item else "UNAVAILABLE",
					"discovery_reason_codes": list(item.get("discovery_reason_codes") or []) if item else [],
					"quality": item.get("quality_score") if item else None,
					"growth": item.get("growth_score") if item else None,
					"valuation": item.get("valuation_score") if item else None,
					"momentum": item.get("momentum_score") if item else None,
					"risk": item.get("risk_score") if item else None,
					"confidence": row.confidence,
					"action": row.action,
					"challenge_flags": list(item.get("challenge_flags") or []) if item else [],
					"investability_status": item.get("investability_status") if item else "UNAVAILABLE",
					"investability_reasons": list(item.get("investability_reasons") or []) if item else [],
					"market_cap": item.get("market_cap") if item else None,
					"market_cap_bucket": self._relative_market_cap_bucket(str(item.get("market_cap_bucket") if item else "UNKNOWN")),
					"relative_market_cap_bucket": self._relative_market_cap_bucket(str(item.get("market_cap_bucket") if item else "UNKNOWN")),
					"market_cap_percentile": item.get("market_cap_percentile") if item else None,
					"factor_score_trace": item.get("factor_score_trace") if item else {},
					"review_metrics": item.get("review_metrics") if item else {},
					"operating_cash_flow": self._review_metric_value(item, "operating_cash_flow") if item else "UNAVAILABLE",
					"operating_cash_flow_reason": self._review_metric_reason(item, "operating_cash_flow") if item else "missing_item",
					"free_cash_flow": self._review_metric_value(item, "free_cash_flow") if item else "UNAVAILABLE",
					"free_cash_flow_reason": self._review_metric_reason(item, "free_cash_flow") if item else "missing_item",
					"debt_to_equity": self._review_metric_value(item, "debt_to_equity") if item else "UNAVAILABLE",
					"debt_to_equity_reason": self._review_metric_reason(item, "debt_to_equity") if item else "missing_item",
					"fcf_yield": self._review_metric_value(item, "fcf_yield") if item else "UNAVAILABLE",
					"fcf_yield_reason": self._review_metric_reason(item, "fcf_yield") if item else "missing_item",
					"return_3m_pct": self._review_metric_value(item, "return_3m_pct") if item else "UNAVAILABLE",
					"return_3m_pct_reason": self._review_metric_reason(item, "return_3m_pct") if item else "missing_item",
					"return_6m_pct": self._review_metric_value(item, "return_6m_pct") if item else "UNAVAILABLE",
					"return_6m_pct_reason": self._review_metric_reason(item, "return_6m_pct") if item else "missing_item",
					"return_12m_pct": self._review_metric_value(item, "return_12m_pct") if item else "UNAVAILABLE",
					"return_12m_pct_reason": self._review_metric_reason(item, "return_12m_pct") if item else "missing_item",
					"volatility": self._review_metric_value(item, "volatility") if item else "UNAVAILABLE",
					"volatility_reason": self._review_metric_reason(item, "volatility") if item else "missing_item",
					"maximum_drawdown": self._review_metric_value(item, "maximum_drawdown") if item else "UNAVAILABLE",
					"maximum_drawdown_reason": self._review_metric_reason(item, "maximum_drawdown") if item else "missing_item",
					"distance_from_52w_high": self._review_metric_value(item, "distance_from_52w_high") if item else "UNAVAILABLE",
					"distance_from_52w_high_reason": self._review_metric_reason(item, "distance_from_52w_high") if item else "missing_item",
					"strongest_factor": self._fragility_value(item, "strongest_factor") if item else "UNAVAILABLE",
					"second_strongest_factor": self._fragility_value(item, "second_strongest_factor") if item else "UNAVAILABLE",
					"rank_without_strongest_factor": self._fragility_value(item, "rank_without_strongest_factor") if item else None,
					"rank_change_without_strongest_factor": self._fragility_value(item, "rank_change_without_strongest_factor") if item else None,
					"remains_top20_without_strongest_factor": self._fragility_value(item, "remains_top20_without_strongest_factor") if item else None,
					"liquidity_status": item.get("liquidity_status") if item else "UNAVAILABLE",
					"liquidity_score": item.get("liquidity_score") if item else None,
					"median_daily_value": item.get("median_daily_value") if item else None,
					"median_daily_volume": item.get("median_daily_volume") if item else None,
					"trading_days": item.get("trading_days") if item else None,
					"active_trading_days": item.get("active_trading_days") if item else None,
					"zero_volume_days": item.get("zero_volume_days") if item else None,
					"portfolio_role": row.portfolio_role,
					"provider_symbol": row.ticker,
					"missing_fields": list(item.get("missing_fields") or []) if item else list(row.unavailable_inputs),
					"outlier_records": item.get("outlier_records") if item else {},
					"history_length": market.history_observations if market else 0,
					"current_price": market.latest_price if market else None,
				}
			)
		return out

	def _relative_market_cap_bucket(self, bucket: str) -> str:
		key = (bucket or "UNKNOWN").strip().upper()
		return _RELATIVE_SIZE_LABELS.get(key, "UNKNOWN" if key == "UNKNOWN" else key)

	def _review_metric_value(self, item: dict[str, object], key: str) -> object:
		review = item.get("review_metrics") if isinstance(item.get("review_metrics"), dict) else {}
		entry = review.get(key) if isinstance(review.get(key), dict) else None
		if not isinstance(entry, dict):
			return "UNAVAILABLE"
		return entry.get("value", "UNAVAILABLE")

	def _review_metric_reason(self, item: dict[str, object], key: str) -> object:
		review = item.get("review_metrics") if isinstance(item.get("review_metrics"), dict) else {}
		entry = review.get(key) if isinstance(review.get(key), dict) else None
		if not isinstance(entry, dict):
			return "missing_review_metric"
		return entry.get("reason")

	def _fragility_value(self, item: dict[str, object], key: str) -> object:
		fragility = item.get("fragility_diagnostics") if isinstance(item.get("fragility_diagnostics"), dict) else {}
		return fragility.get(key)

	def _build_fragility_diagnostics(self, payload: list[dict[str, object]]) -> dict[str, dict[str, object]]:
		weights = {
			"QUALITY": 0.28,
			"GROWTH": 0.17,
			"VALUATION": 0.20,
			"MOMENTUM": 0.20,
			"RISK": 0.15,
		}
		alt_rows: list[tuple[str, float]] = []
		for item in payload:
			candidate: CandidateInstrument = item["candidate"]  # type: ignore[assignment]
			scores = {
				"QUALITY": item.get("quality_score"),
				"GROWTH": item.get("growth_score"),
				"VALUATION": item.get("valuation_score"),
				"MOMENTUM": item.get("momentum_score"),
				"RISK": item.get("risk_score"),
			}
			usable = {k: float(v) for k, v in scores.items() if isinstance(v, (int, float))}
			strongest = max(usable, key=usable.get) if usable else None
			den = sum(weights[k] for k in usable if k != strongest)
			if den > 0:
				attractiveness = sum(usable[k] * weights[k] for k in usable if k != strongest) / den
			else:
				attractiveness = 0.0
			suitability = float(item.get("portfolio_suitability_score") or 0.0)
			combined = (attractiveness * 0.65) + (suitability * 0.35)
			if float(item.get("evidence_coverage") or 0.0) < 0.45:
				combined *= 0.85
			market: MarketSnapshot = item["market"]  # type: ignore[assignment]
			if market.fx_required and not market.fx_available:
				combined *= 0.92
			if str(item.get("investability_status") or "PASS") == "FAIL":
				combined *= 0.82
			alt_rows.append((candidate.ticker, combined))

		alt_rows.sort(key=lambda x: x[1], reverse=True)
		alt_rank = {ticker: idx for idx, (ticker, _) in enumerate(alt_rows, start=1)}

		out: dict[str, dict[str, object]] = {}
		for item in payload:
			candidate: CandidateInstrument = item["candidate"]  # type: ignore[assignment]
			scores = [
				("QUALITY", item.get("quality_score")),
				("GROWTH", item.get("growth_score")),
				("VALUATION", item.get("valuation_score")),
				("MOMENTUM", item.get("momentum_score")),
				("RISK", item.get("risk_score")),
			]
			usable = [(name, float(value)) for name, value in scores if isinstance(value, (int, float))]
			usable.sort(key=lambda x: x[1], reverse=True)
			strongest = usable[0][0] if usable else "UNAVAILABLE"
			second = usable[1][0] if len(usable) > 1 else "UNAVAILABLE"
			rank_without = alt_rank.get(candidate.ticker)
			rank_now = int(item.get("rank") or 0)
			out[candidate.ticker] = {
				"strongest_factor": strongest,
				"second_strongest_factor": second,
				"rank_without_strongest_factor": rank_without,
				"rank_change_without_strongest_factor": None if rank_without is None else (rank_without - rank_now),
				"remains_top20_without_strongest_factor": bool(isinstance(rank_without, int) and rank_without <= 20),
			}
		return out

	def _build_data_quality_summary_v31(
		self,
		rows: list[AllocationRecommendation],
		excluded: list[dict[str, object]],
		total_source: float,
		base_currency: str,
		portfolio_before: dict[str, object],
		payload: list[dict[str, object]],
		markets: list[str],
	) -> dict[str, object]:
		base = self._build_data_quality_summary(rows, excluded, total_source, base_currency, portfolio_before)
		market_stats: dict[str, dict[str, object]] = {}
		for market in markets:
			items = [p for p in payload if str(p["candidate"].market) == market]
			if not items:
				market_stats[market] = {
					"candidates": 0,
					"eligible": 0,
					"partial": 0,
					"ineligible": 0,
					"history_coverage": 0.0,
					"fundamental_coverage": 0.0,
					"valuation_coverage": 0.0,
					"market_cap_coverage": 0.0,
					"liquidity_coverage": 0.0,
				}
				continue

			eligible = 0
			partial = 0
			ineligible = 0
			history_cov = 0
			fund_cov = 0
			val_cov = 0
			mcap_cov = 0
			liq_cov = 0
			for item in items:
				m: MarketSnapshot = item["market"]  # type: ignore[assignment]
				if m.mode == "UNAVAILABLE":
					ineligible += 1
				elif float(item.get("evidence_coverage") or 0.0) >= 0.6:
					eligible += 1
				else:
					partial += 1
				history_cov += 1 if m.history_observations >= 126 else 0
				fund_cov += 1 if any(isinstance(item.get(k), (int, float)) for k in ["quality_score", "growth_score"]) else 0
				val_cov += 1 if isinstance(item.get("valuation_score"), (int, float)) else 0
				mcap_cov += 1 if isinstance(item.get("market_cap"), (int, float)) else 0
				liq_cov += 1 if item.get("liquidity_status") != "UNAVAILABLE" else 0

			n = len(items)
			market_stats[market] = {
				"candidates": n,
				"eligible": eligible,
				"partial": partial,
				"ineligible": ineligible,
				"history_coverage": round(history_cov / n, 4),
				"fundamental_coverage": round(fund_cov / n, 4),
				"valuation_coverage": round(val_cov / n, 4),
				"market_cap_coverage": round(mcap_cov / n, 4),
				"liquidity_coverage": round(liq_cov / n, 4),
			}

		usd_usd = live_feeds.fx_rate("USD", "USD")
		usd_inr = live_feeds.fx_rate("USD", "INR")
		usd_sgd = live_feeds.fx_rate("USD", "SGD")
		india_payload = [p for p in payload if str(p["candidate"].market) == "India"]
		india_ranked = sorted(
			india_payload,
			key=lambda p: (float(p.get("discovery_score") or 0.0), float(p.get("combined_recommendation_score") or 0.0)),
			reverse=True,
		)
		top_discovery = india_ranked[:20]
		sector_counts: dict[str, int] = {}
		for item in top_discovery:
			market: MarketSnapshot = item["market"]  # type: ignore[assignment]
			sector = str((market.raw_metrics or {}).get("sector") or "UNKNOWN")
			sector_counts[sector] = sector_counts.get(sector, 0) + 1

		diversified_shortlist: list[str] = []
		sector_cap = max(1, int(len(top_discovery) * 0.30))
		used_by_sector: dict[str, int] = {}
		for item in india_ranked:
			if len(diversified_shortlist) >= 20:
				break
			market: MarketSnapshot = item["market"]  # type: ignore[assignment]
			sector = str((market.raw_metrics or {}).get("sector") or "UNKNOWN")
			if used_by_sector.get(sector, 0) >= sector_cap:
				continue
			diversified_shortlist.append(str(item["candidate"].ticker))
			used_by_sector[sector] = used_by_sector.get(sector, 0) + 1

		base["market_retrieval_stats"] = market_stats
		base["discovery_sector_concentration"] = {
			"top_n": len(top_discovery),
			"sector_counts": dict(sorted(sector_counts.items(), key=lambda kv: kv[1], reverse=True)),
			"max_sector_weight": 0.0 if not top_discovery else round(max(sector_counts.values()) / len(top_discovery), 4),
			"is_concentrated": False if not top_discovery else (max(sector_counts.values()) / len(top_discovery)) > 0.45,
			"diversified_research_shortlist": diversified_shortlist,
		}
		base["fx_availability"] = {
			"USD/USD": {"rate": usd_usd.rate, "as_of": usd_usd.as_of, "mode": usd_usd.mode},
			"USD/INR": {"rate": usd_inr.rate, "as_of": usd_inr.as_of, "mode": usd_inr.mode},
			"USD/SGD": {"rate": usd_sgd.rate, "as_of": usd_sgd.as_of, "mode": usd_sgd.mode},
		}
		return base

	def _liquidity_profile(self, price_series, volume_series, market: str) -> dict[str, float | int | str | None]:
		if volume_series is None or len(price_series) == 0:
			return {
				"median_daily_value": None,
				"median_daily_volume": None,
				"trading_days": int(len(price_series)),
				"active_trading_days": 0,
				"zero_volume_days": int(len(price_series)),
				"liquidity_score": None,
				"liquidity_status": "UNAVAILABLE",
			}

		cfg = _LIQUIDITY_THRESHOLDS.get(market, _LIQUIDITY_THRESHOLDS["US"])
		trading_days = int(len(price_series))
		active_days = int((volume_series > 0).sum())
		zero_days = max(0, trading_days - active_days)
		zero_ratio = 1.0 if trading_days <= 0 else (zero_days / trading_days)

		valid_volume = volume_series[volume_series > 0]
		median_volume = float(valid_volume.median()) if not valid_volume.empty else 0.0
		traded_value = (price_series * volume_series).dropna()
		valid_value = traded_value[traded_value > 0]
		median_value = float(valid_value.median()) if not valid_value.empty else 0.0
		median_price = float(price_series.median()) if len(price_series) else 0.0

		def _ratio(value: float, watch: float, target: float) -> float:
			if target <= 0:
				return 0.0
			if value >= target:
				return 1.0
			if value <= watch:
				return 0.0
			return (value - watch) / max(1e-9, target - watch)

		score_parts = [
			_ratio(median_value, float(cfg["median_daily_value_watch"]), float(cfg["median_daily_value_pass"])),
			_ratio(median_volume, float(cfg["median_daily_volume_watch"]), float(cfg["median_daily_volume_pass"])),
			_ratio(float(trading_days), float(cfg["min_trading_days_watch"]), float(cfg["min_trading_days_pass"])),
			_ratio(float(median_price), float(cfg["min_price_watch"]), float(cfg["min_price_pass"])),
			self._bounded((float(cfg["max_zero_volume_ratio_watch"]) - zero_ratio) / max(1e-9, float(cfg["max_zero_volume_ratio_watch"]) - float(cfg["max_zero_volume_ratio_pass"])), 0.0, 1.0),
		]
		liquidity_score = round(sum(score_parts) / len(score_parts) * 100.0, 2)

		status = "WATCH"
		if (
			median_value >= float(cfg["median_daily_value_pass"])
			and median_volume >= float(cfg["median_daily_volume_pass"])
			and trading_days >= int(cfg["min_trading_days_pass"])
			and zero_ratio <= float(cfg["max_zero_volume_ratio_pass"])
			and median_price >= float(cfg["min_price_pass"])
		):
			status = "PASS"
		elif (
			median_value < float(cfg["median_daily_value_watch"])
			or median_volume < float(cfg["median_daily_volume_watch"])
			or trading_days < int(cfg["min_trading_days_watch"])
			or zero_ratio > float(cfg["max_zero_volume_ratio_watch"])
			or median_price < float(cfg["min_price_watch"])
		):
			status = "FAIL"

		return {
			"median_daily_value": round(median_value, 4),
			"median_daily_volume": round(median_volume, 4),
			"trading_days": trading_days,
			"active_trading_days": active_days,
			"zero_volume_days": zero_days,
			"liquidity_score": liquidity_score,
			"liquidity_status": status,
		}

	def _validated_metric(self, name: str, value: float | None) -> tuple[float | None, dict[str, object] | None]:
		if value is None:
			return None, None
		policy = _OUTLIER_POLICY.get(name)
		if policy is None:
			return value, None
		hard_min, hard_max, winsor_min, winsor_max = policy
		raw = value
		if hard_min is not None and value < hard_min:
			return None, {"raw": raw, "validated": None, "flag": "hard_floor_violation"}
		if hard_max is not None and value > hard_max:
			return None, {"raw": raw, "validated": None, "flag": "hard_cap_violation"}
		validated = value
		flag = None
		if winsor_min is not None and validated < winsor_min:
			validated = winsor_min
			flag = "winsorized_floor"
		if winsor_max is not None and validated > winsor_max:
			validated = winsor_max
			flag = "winsorized_cap"
		if flag is None:
			return validated, None
		return validated, {"raw": raw, "validated": validated, "flag": flag}

	def _market_cap_bucket(self, market_cap: float | None, percentile: float | None) -> str:
		if market_cap is None or market_cap <= 0:
			return "UNKNOWN"
		if percentile is None:
			return "MICRO_OR_UNKNOWN"
		if percentile >= float(_MARKET_CAP_BUCKET_PERCENTILES["large_min_pct"]):
			return "LARGE"
		if percentile >= float(_MARKET_CAP_BUCKET_PERCENTILES["mid_min_pct"]):
			return "MID"
		if percentile >= float(_MARKET_CAP_BUCKET_PERCENTILES["small_min_pct"]):
			return "SMALL"
		return "MICRO_OR_UNKNOWN"

	def _minimum_investability_gate(
		self,
		market: MarketSnapshot,
		market_cap_bucket: str,
		liquidity_status: str,
		evidence_coverage: float,
	) -> tuple[str, list[str]]:
		reasons: list[str] = []
		if market.mode == "UNAVAILABLE":
			reasons.append("market_data_unavailable")
		if liquidity_status == "FAIL":
			reasons.append("liquidity_fail")
		if market.history_observations < 90:
			reasons.append("short_trading_history")
		if evidence_coverage < 0.35:
			reasons.append("insufficient_evidence")
		if market_cap_bucket == "UNKNOWN":
			reasons.append("market_cap_unknown")

		if reasons:
			return "FAIL", reasons
		if liquidity_status in {"WATCH", "UNAVAILABLE"} or market_cap_bucket == "MICRO_OR_UNKNOWN" or evidence_coverage < 0.55:
			watch_reasons: list[str] = []
			if liquidity_status in {"WATCH", "UNAVAILABLE"}:
				watch_reasons.append("liquidity_watch")
			if market_cap_bucket == "MICRO_OR_UNKNOWN":
				watch_reasons.append("micro_or_unknown_size")
			if evidence_coverage < 0.55:
				watch_reasons.append("thin_evidence")
			return "WATCH", watch_reasons
		return "PASS", []

	def _discovery_score(self, item: dict[str, object], market: MarketSnapshot, market_cap_bucket: str, liquidity_status: str) -> tuple[float, str, list[str]]:
		raw = market.raw_metrics or {}
		quality = float(item.get("quality_score") or 0.0)
		growth = float(item.get("growth_score") or 0.0)
		valuation = float(item.get("valuation_score") or 0.0)
		momentum = float(item.get("momentum_score") or 0.0)
		risk = float(item.get("risk_score") or 0.0)

		earnings_growth = self._safe_float(raw.get("earningsGrowth"))
		earnings_q_growth = self._safe_float(raw.get("earningsQuarterlyGrowth"))
		improvement_status = "UNAVAILABLE"
		improvement_score = 50.0
		if earnings_growth is not None and earnings_q_growth is not None:
			improvement_status = "AVAILABLE"
			improvement_signal = (earnings_q_growth - earnings_growth) * 100.0
			improvement_score = self._bounded(50.0 + improvement_signal, 0.0, 100.0)

		valuation_relative = self._bounded((valuation * 0.65) + (max(0.0, quality - valuation) * 0.35), 0.0, 100.0)
		market_confirmation = self._bounded((momentum * 0.7) + (risk * 0.3), 0.0, 100.0)
		resilience = self._bounded((quality * 0.6) + (risk * 0.4), 0.0, 100.0)
		data_quality = self._bounded(float(item.get("evidence_coverage") or 0.0) * 100.0, 0.0, 100.0)

		score = (improvement_score * 0.24) + (growth * 0.18) + (valuation_relative * 0.18) + (market_confirmation * 0.16) + (resilience * 0.14) + (data_quality * 0.10)
		if market_cap_bucket in {"SMALL", "MICRO_OR_UNKNOWN"} and liquidity_status != "PASS":
			score -= 6.0
		score = round(self._bounded(score, 0.0, 100.0), 2)

		rationale_parts: list[str] = []
		if improvement_status == "AVAILABLE":
			rationale_parts.append("earnings_acceleration")
		if growth >= 60.0:
			rationale_parts.append("growth_strength")
		if valuation_relative >= 60.0:
			rationale_parts.append("valuation_support")
		if market_confirmation >= 60.0:
			rationale_parts.append("market_confirmation")
		if resilience >= 60.0:
			rationale_parts.append("balance_sheet_resilience")
		if not rationale_parts:
			rationale_parts.append("limited_emergent_signals")

		return score, improvement_status, rationale_parts

	@staticmethod
	def _safe_float(value: object) -> float | None:
		try:
			if value is None:
				return None
			parsed = float(value)
			if math.isnan(parsed) or math.isinf(parsed):
				return None
			return parsed
		except (TypeError, ValueError):
			return None

	@staticmethod
	def _percentile_rank(value: float, values: list[float]) -> float:
		if not values:
			return 50.0
		count = sum(1 for v in values if v <= value)
		return (count / len(values)) * 100.0

	@staticmethod
	def _mean_or_none(values: list[float | None]) -> float | None:
		usable = [float(v) for v in values if isinstance(v, (int, float))]
		if not usable:
			return None
		return round(mean(usable), 2)

	def _discover_candidates(self, markets: list[str]) -> tuple[list[CandidateInstrument], dict[str, object], dict[str, object], list[dict[str, object]]]:
		candidates: list[CandidateInstrument] = []
		excluded: list[dict[str, object]] = []
		eligible_by_market: dict[str, int] = {}
		partial_by_market: dict[str, int] = {}
		ineligible_by_market: dict[str, int] = {}
		validation_statuses = self._load_universe_validation_statuses()

		for market in markets:
			seed_tickers = self._load_universe_file(market)
			eligible_count = 0
			provider_unavailable_count = 0
			invalid_count = 0
			for raw in seed_tickers:
				ticker = self._sanitize_ticker(raw)
				if ticker is None:
					invalid_count += 1
					excluded.append({"market": market, "ticker": raw, "reason": "invalid_symbol", "missing_fields": ["ticker_format"]})
					continue
				status = validation_statuses.get((market, ticker))
				if status in {"INVALID", "STALE_DELISTED"}:
					invalid_count += 1
					excluded.append({"market": market, "ticker": ticker, "reason": f"universe_validation_{status.lower()}", "missing_fields": ["provider_history"]})
					continue
				if status == "PROVIDER_UNAVAILABLE":
					provider_unavailable_count += 1
				currency = self._currency_for_ticker(ticker, market)
				candidates.append(
					CandidateInstrument(
						ticker=ticker,
						instrument_name=ticker,
						portfolio_role="UNAVAILABLE",
						market=market,
						exchange=self._exchange_for_ticker(ticker),
						issuer_country=self._country_for_market(market),
						trading_currency=currency,
						instrument_type="Equity",
						geography=self._geography_for_market(market),
						sector=None,
						risk_band=None,
					)
				)
				eligible_count += 1

			eligible_by_market[market] = eligible_count
			partial_by_market[market] = provider_unavailable_count
			ineligible_by_market[market] = invalid_count

		universe_summary = {
			"markets": {
				m: {
					"total_seed": len(self._load_universe_file(m)),
					"eligible": eligible_by_market.get(m, 0),
					"partial": partial_by_market.get(m, 0),
					"ineligible": ineligible_by_market.get(m, 0),
				}
				for m in markets
			},
			"total_candidates": len(candidates),
			"eligible_candidates": sum(eligible_by_market.values()),
			"partial_candidates": sum(partial_by_market.values()),
			"ineligible_candidates": sum(ineligible_by_market.values()),
		}
		screening_summary = {
			"eligible_by_market": eligible_by_market,
			"partial_by_market": partial_by_market,
			"ineligible_by_market": ineligible_by_market,
			"excluded_reasons": excluded[:50],
		}
		return candidates, universe_summary, screening_summary, excluded

	def _load_universe_validation_statuses(self) -> dict[tuple[str, str], str]:
		path = _DATA_DIR / "universe_validation.json"
		if not path.exists():
			return {}
		try:
			import json

			payload = json.loads(path.read_text())
		except Exception:
			return {}

		statuses: dict[tuple[str, str], str] = {}
		markets_payload = payload.get("markets") if isinstance(payload, dict) else None
		if not isinstance(markets_payload, dict):
			return statuses

		for market, details in markets_payload.items():
			if not isinstance(details, dict):
				continue
			rows_all = details.get("rows")
			if isinstance(rows_all, list):
				for row in rows_all:
					if not isinstance(row, dict):
						continue
					ticker = self._sanitize_ticker(row.get("ticker"))
					status = row.get("status")
					if ticker and isinstance(status, str):
						statuses[(str(market), ticker)] = status
			# New validator format.
			for key in ["valid_preview", "invalid_preview", "stale_delisted_preview", "provider_unavailable_preview"]:
				rows = details.get(key)
				if not isinstance(rows, list):
					continue
				for row in rows:
					if not isinstance(row, dict):
						continue
					ticker = self._sanitize_ticker(row.get("ticker"))
					status = row.get("status")
					if ticker and isinstance(status, str):
						statuses[(str(market), ticker)] = status

			# Legacy validator format.
			for bucket, status in (("validated_preview", "VALID"), ("invalid_preview", "STALE_DELISTED")):
				rows = details.get(bucket)
				if not isinstance(rows, list):
					continue
				for row in rows:
					if not isinstance(row, dict):
						continue
					ticker = self._sanitize_ticker(row.get("ticker"))
					if ticker:
						statuses[(str(market), ticker)] = status

		return statuses

	def _load_universe_file(self, market: str) -> list[str]:
		filename = _MARKET_TO_FILE.get(market)
		if not filename:
			return []
		path = _DATA_DIR / filename
		if not path.exists():
			return []
		out: list[str] = []
		for raw in path.read_text().splitlines():
			ticker = self._sanitize_ticker(raw)
			if ticker:
				out.append(ticker)
		return out

	def _sanitize_ticker(self, raw: object) -> str | None:
		if raw is None:
			return None
		t = str(raw).strip().upper()
		if not t or " " in t or "(" in t or ")" in t:
			return None
		if not _TICKER_ALLOWED.match(t):
			return None
		return t

	def _market_currency(self, market: str) -> str:
		return {"US": "USD", "India": "INR", "Singapore": "SGD"}.get(market, "USD")

	def _currency_for_ticker(self, ticker: str, market: str) -> str:
		if ticker.endswith(".NS"):
			return "INR"
		if ticker.endswith(".SI"):
			return "SGD"
		return self._market_currency(market)

	def _country_for_market(self, market: str) -> str:
		return {"US": "United States", "India": "India", "Singapore": "Singapore"}.get(market, market)

	def _geography_for_market(self, market: str) -> str:
		if market == "US":
			return "US"
		if market == "India":
			return "INDIA"
		if market == "Singapore":
			return "SINGAPORE"
		return "GLOBAL"

	def _exchange_for_ticker(self, ticker: str) -> str | None:
		if ticker.endswith(".NS"):
			return "NSE"
		if ticker.endswith(".SI"):
			return "SGX"
		return "US"


	def _select_holdings(self, use_demo_portfolio: bool, portfolio_snapshot_id: str | None) -> list[Holding]:
		if use_demo_portfolio:
			return [
				Holding(holding_id="demo1", ticker="NVDA", name="NVIDIA", quantity=12, market_value=15000, geography="US", currency="USD", asset_class="Equity", sector="Technology", theme="AI"),
				Holding(holding_id="demo2", ticker="MSFT", name="Microsoft", quantity=20, market_value=9000, geography="US", currency="USD", asset_class="Equity", sector="Technology", theme="AI"),
				Holding(holding_id="demo3", ticker="GOOGL", name="Alphabet", quantity=30, market_value=5400, geography="US", currency="USD", asset_class="Equity", sector="Technology", theme="Digital"),
				Holding(holding_id="demo4", ticker="AAPL", name="Apple", quantity=15, market_value=3300, geography="US", currency="USD", asset_class="Equity", sector="Technology", theme="Consumer Tech"),
				Holding(holding_id="demo5", ticker="INDIA-CORE", name="India Equity Sleeve", quantity=1, market_value=840000, geography="India", currency="INR", asset_class="Equity", sector="Diversified", theme="India Core"),
			]
		if portfolio_snapshot_id:
			for snapshot in store.snapshots:
				if snapshot.snapshot_id == portfolio_snapshot_id:
					return list(snapshot.holdings)
			raise ValueError("portfolio_snapshot_id not found")
		if store.snapshots:
			return list(store.snapshots[0].holdings)
		return list(store.holdings)

	def _build_mandate(self, override: InvestorMandateOverride | None) -> dict[str, object]:
		mandate = {
			"india_exposure_inr": 70_000_000.0,
			"usd_diversification_priority": True,
			"horizon_min": 10,
			"horizon_max": 15,
			"risk_profile": "moderate_high",
			"quality_preference": True,
			"strategic_upside_preference": True,
			"target_position_count_min": 8,
			"target_position_count_max": 12,
			"monthly_contribution_usd": 5000.0,
			"max_allocation_per_instrument": 1900.0,
			"minimum_meaningful_allocation": 350.0,
		}
		if override is None:
			return mandate
		data = override.model_dump(exclude_none=True)
		mapping = {
			"horizon_years_min": "horizon_min",
			"horizon_years_max": "horizon_max",
			"quality_compounders_preference": "quality_preference",
			"strategic_upside_preference": "strategic_upside_preference",
			"target_position_count_min": "target_position_count_min",
			"target_position_count_max": "target_position_count_max",
			"monthly_contribution_usd": "monthly_contribution_usd",
		}
		for k, v in data.items():
			mandate[mapping.get(k, k)] = v
		return mandate

	def _resolve_markets_concurrently(
		self,
		candidates: list[CandidateInstrument],
		mode_preference: str,
		base_currency: str,
	) -> list[MarketSnapshot]:
		# Per-candidate market resolution does up to three serial network calls each
		# (history, fundamentals, fx). Fetching candidates concurrently avoids multiplying
		# per-ticker network latency by the full universe size, mirroring the same
		# ThreadPoolExecutor pattern already used in live_feeds.top_recommendations().
		if not candidates:
			return []
		started = time.perf_counter()
		max_workers = min(10, len(candidates))
		logger.info(
			"_resolve_markets_concurrently started candidates=%d max_workers=%d mode=%s base_currency=%s",
			len(candidates),
			max_workers,
			mode_preference,
			base_currency,
		)
		results: list[MarketSnapshot] = [None] * len(candidates)  # type: ignore[list-item]

		def _resolve_one(candidate: CandidateInstrument) -> MarketSnapshot:
			thread_name = threading.current_thread().name
			logger.info("_resolve_markets_concurrently fetch_start ticker=%s thread=%s", candidate.ticker, thread_name)
			snapshot = self._resolve_market(candidate, mode_preference, base_currency)
			logger.info("_resolve_markets_concurrently fetch_done ticker=%s thread=%s", candidate.ticker, thread_name)
			return snapshot

		with ThreadPoolExecutor(max_workers=max_workers) as executor:
			future_to_index = {
				executor.submit(_resolve_one, candidate): idx
				for idx, candidate in enumerate(candidates)
			}
			for future in as_completed(future_to_index):
				idx = future_to_index[future]
				try:
					results[idx] = future.result()
				except Exception:
					# Preserve positional alignment with `candidates` even if one ticker's
					# fetch unexpectedly raises; fall back to the same unavailable-snapshot
					# path a live-fetch failure would already take.
					results[idx] = self._unavailable_market_snapshot(candidates[idx], base_currency)

		elapsed = time.perf_counter() - started
		logger.info(
			"_resolve_markets_concurrently completed candidates=%d max_workers=%d elapsed_seconds=%.3f",
			len(candidates),
			max_workers,
			elapsed,
		)
		return results

	def _resolve_market(self, candidate: CandidateInstrument, mode_preference: str, base_currency: str) -> MarketSnapshot:
		ticker = candidate.ticker
		cached = self._cache.get(ticker)
		now = datetime.now(timezone.utc)
		if mode_preference in {"auto", "cached"} and cached is not None:
			seen_at, snapshot = cached
			if now - seen_at <= self._cache_ttl:
				snapshot.mode = "CACHED"
				return snapshot

		if mode_preference in {"auto", "live"}:
			live = self._fetch_live_snapshot(candidate, base_currency)
			if live is not None:
				self._cache[ticker] = (now, live)
				return live

		if mode_preference in {"auto", "cached", "development_seed"}:
			if cached is not None:
				_, snapshot = cached
				snapshot.mode = "CACHED"
				snapshot.is_stale = True
				snapshot.fallback_reason = "live_fetch_failed_used_stale_cache"
				return snapshot
			if mode_preference == "development_seed":
				seeded = self._seed_snapshot(candidate, base_currency)
				if seeded is not None:
					return seeded

		return self._unavailable_market_snapshot(candidate, base_currency)

	def _unavailable_market_snapshot(self, candidate: CandidateInstrument, base_currency: str) -> MarketSnapshot:
		ticker = candidate.ticker
		fx_required = (candidate.trading_currency or base_currency).upper() != base_currency.upper()
		return MarketSnapshot(
			ticker=ticker,
			provider="yfinance",
			mode="UNAVAILABLE",
			as_of=None,
			is_stale=True,
			fallback_reason="live_and_seed_unavailable",
			seeded_input=False,
			latest_price=None,
			daily_return_pct=None,
			return_1m_pct=None,
			return_3m_pct=None,
			return_6m_pct=None,
			return_12m_pct=None,
			realized_volatility=None,
			drawdown_pct=None,
			distance_from_52w_high_pct=None,
			trading_currency=(candidate.trading_currency or base_currency).upper(),
			sector=None,
			portfolio_role="UNAVAILABLE",
			quality_score=None,
			growth_score=None,
			fx_required=fx_required,
			fx_available=not fx_required,
			fx_rate_to_base=1.0 if not fx_required else None,
			missing_inputs=(
				["market_price", "momentum_3m", "fx_rate"] if fx_required else ["market_price", "momentum_3m"]
			),
		)

	def _fetch_live_snapshot(self, candidate: CandidateInstrument, base_currency: str) -> MarketSnapshot | None:
		history = live_feeds.history(candidate.ticker, period="1y", interval="1d")
		if history.frame is None or history.frame.empty:
			return None

		fundamentals = live_feeds.fundamentals(candidate.ticker)
		finfo = fundamentals.info if fundamentals.info else {}
		trading_currency = str(finfo.get("currency") or candidate.trading_currency or base_currency).upper()
		fx_required = trading_currency != base_currency.upper()
		fx_rate: float | None = 1.0 if not fx_required else None
		fx_available = not fx_required
		missing_inputs: list[str] = []
		if fx_required:
			fx = live_feeds.fx_rate(trading_currency, base_currency.upper())
			if fx.rate is not None and fx.rate > 0:
				fx_rate = float(fx.rate)
				fx_available = True
			else:
				missing_inputs.append("fx_rate")

		frame = history.frame.copy()
		price_col = "Adj Close" if "Adj Close" in frame.columns else "Close"
		series = frame[price_col].dropna()
		if series.empty:
			return None

		obs = int(len(series))
		latest_price = float(series.iloc[-1])
		daily_return_pct = None
		if obs >= 2 and float(series.iloc[-2]) != 0:
			daily_return_pct = ((latest_price / float(series.iloc[-2])) - 1.0) * 100.0

		def _window_return(lookback: int) -> float | None:
			if obs < 2:
				return None
			idx = max(0, obs - 1 - min(lookback, obs - 1))
			start = float(series.iloc[idx])
			if start == 0:
				return None
			return ((latest_price / start) - 1.0) * 100.0

		returns = series.pct_change().dropna()
		realized_volatility = None
		if not returns.empty:
			realized_volatility = float(returns.std(ddof=0) * math.sqrt(252.0))

		volume_series = None
		if "Volume" in frame.columns:
			volume_series = frame["Volume"].reindex(series.index).fillna(0.0)
		liquidity = self._liquidity_profile(series, volume_series, candidate.market)

		running_max = series.cummax()
		drawdowns = (series / running_max) - 1.0
		drawdown_pct = float(drawdowns.min() * 100.0) if not drawdowns.empty else None
		high_52w = float(series.max())
		distance_52w = ((latest_price / high_52w) - 1.0) * 100.0 if high_52w > 0 else None

		sector_text = str(finfo.get("sector") or "").strip() or None
		if sector_text is None:
			missing_inputs.append("sector")

		raw_metrics: dict[str, float | str | None] = {
			"observation_count": float(obs),
			"return_3m_pct": _window_return(63),
			"return_6m_pct": _window_return(126),
			"return_12m_pct": _window_return(252),
			"realized_volatility": realized_volatility,
			"max_drawdown_pct": drawdown_pct,
			"distance_from_52w_high_pct": distance_52w,
			"returnOnEquity": self._safe_float(finfo.get("returnOnEquity")),
			"operatingMargins": self._safe_float(finfo.get("operatingMargins")),
			"profitMargins": self._safe_float(finfo.get("profitMargins")),
			"freeCashflow": self._safe_float(finfo.get("freeCashflow")),
			"operatingCashflow": self._safe_float(finfo.get("operatingCashflow")),
			"debtToEquity": self._safe_float(finfo.get("debtToEquity")),
			"currentRatio": self._safe_float(finfo.get("currentRatio")),
			"revenueGrowth": self._safe_float(finfo.get("revenueGrowth")),
			"earningsGrowth": self._safe_float(finfo.get("earningsGrowth")),
			"earningsQuarterlyGrowth": self._safe_float(finfo.get("earningsQuarterlyGrowth")),
			"trailingPE": self._safe_float(finfo.get("trailingPE")),
			"forwardPE": self._safe_float(finfo.get("forwardPE")),
			"priceToBook": self._safe_float(finfo.get("priceToBook")),
			"enterpriseToEbitda": self._safe_float(finfo.get("enterpriseToEbitda")),
			"marketCap": self._safe_float(finfo.get("marketCap")),
			"median_daily_value": liquidity["median_daily_value"],
			"median_daily_volume": liquidity["median_daily_volume"],
			"trading_days": liquidity["trading_days"],
			"active_trading_days": liquidity["active_trading_days"],
			"zero_volume_days": liquidity["zero_volume_days"],
			"liquidity_score": liquidity["liquidity_score"],
			"liquidity_status": str(liquidity["liquidity_status"]),
			"sector": sector_text,
			"fundamentals_provider": fundamentals.provider,
			"fundamentals_as_of": fundamentals.as_of,
		}

		if raw_metrics["return_3m_pct"] is None:
			missing_inputs.append("momentum_3m")
		if raw_metrics["return_6m_pct"] is None:
			missing_inputs.append("momentum_6m")
		if raw_metrics["return_12m_pct"] is None:
			missing_inputs.append("momentum_12m")
		if realized_volatility is None:
			missing_inputs.append("realized_volatility")
		if drawdown_pct is None:
			missing_inputs.append("drawdown")
		if liquidity["liquidity_status"] == "UNAVAILABLE":
			missing_inputs.append("liquidity")

		if daily_return_pct is None:
			missing_inputs.append("market_price")

		quality_score = self._quality_score_from_fundamentals(finfo)
		growth_score = self._growth_score_from_fundamentals(finfo)
		if quality_score is None:
			missing_inputs.append("quality")
		if growth_score is None:
			missing_inputs.append("growth")

		return MarketSnapshot(
			ticker=candidate.ticker,
			provider="yfinance",
			mode="LIVE",
			as_of=history.as_of or _now_iso(),
			is_stale=False,
			fallback_reason=None,
			seeded_input=False,
			latest_price=latest_price,
			daily_return_pct=daily_return_pct,
			return_1m_pct=_window_return(21),
			return_3m_pct=raw_metrics["return_3m_pct"] if isinstance(raw_metrics["return_3m_pct"], float) else None,
			return_6m_pct=raw_metrics["return_6m_pct"] if isinstance(raw_metrics["return_6m_pct"], float) else None,
			return_12m_pct=raw_metrics["return_12m_pct"] if isinstance(raw_metrics["return_12m_pct"], float) else None,
			realized_volatility=realized_volatility,
			drawdown_pct=drawdown_pct,
			distance_from_52w_high_pct=distance_52w,
			trading_currency=trading_currency,
			sector=sector_text,
			portfolio_role="UNAVAILABLE",
			quality_score=quality_score,
			growth_score=growth_score,
			fx_required=fx_required,
			fx_available=fx_available,
			fx_rate_to_base=fx_rate,
			missing_inputs=sorted(set(missing_inputs)),
			history_observations=obs,
			raw_metrics=raw_metrics,
		)

	def _seed_snapshot(self, candidate: CandidateInstrument, base_currency: str) -> MarketSnapshot | None:
		price = _DEV_SEED.get(candidate.ticker)
		if price is None:
			return None
		seed_now = _now_iso()
		pseudo = (sum(ord(c) for c in candidate.ticker) % 17) - 8
		daily = pseudo / 10.0
		trading_currency = (candidate.trading_currency or base_currency).upper()
		fx_required = trading_currency != base_currency.upper()
		return MarketSnapshot(
			ticker=candidate.ticker,
			provider="development_seed",
			mode="DEVELOPMENT_SEED",
			as_of=seed_now,
			is_stale=True,
			fallback_reason="live_data_unavailable_development_seed_used",
			seeded_input=True,
			latest_price=float(price),
			daily_return_pct=daily,
			return_1m_pct=daily * 3.5,
			return_3m_pct=daily * 9.0,
			return_6m_pct=daily * 15.0,
			return_12m_pct=daily * 28.0,
			realized_volatility=abs(daily) * 0.22,
			drawdown_pct=max(-30.0, -abs(daily) * 5.0),
			distance_from_52w_high_pct=max(-35.0, -abs(daily) * 2.5),
			trading_currency=trading_currency,
			sector="UNKNOWN",
			portfolio_role="UNAVAILABLE",
			quality_score=None,
			growth_score=None,
			fx_required=fx_required,
			fx_available=not fx_required,
			fx_rate_to_base=1.0 if not fx_required else None,
			missing_inputs=(
				["quality", "growth", "sector", "fx_rate"] if fx_required else ["quality", "growth", "sector"]
			),
		)

	def _build_portfolio_observations(self, holdings: list[Holding], mandate: dict[str, object]) -> list[PortfolioObservation]:
		total = sum(h.market_value for h in holdings) or 1.0
		tech_value = sum(h.market_value for h in holdings if self._is_technology_exposure_holding(h))
		india_value = sum(h.market_value for h in holdings if h.geography.lower() == "india")
		max_single = max((h.market_value / total for h in holdings), default=0.0)

		obs = [
			PortfolioObservation(code="INDIA_CONCENTRATION", severity="HIGH" if india_value / total > 0.6 else "MEDIUM", detail="India allocation is structurally dominant; USD sleeve should prioritize diversification."),
			PortfolioObservation(code="US_TECH_CONCENTRATION", severity="HIGH" if tech_value / total > 0.2 else "MEDIUM", detail="Existing portfolio has concentrated mega-cap technology exposure."),
			PortfolioObservation(code="SINGLE_NAME_CONCENTRATION", severity="HIGH" if max_single > 0.2 else "MEDIUM", detail="At least one position is a large share of current portfolio value."),
			PortfolioObservation(code="DEFENSIVE_GAP", severity="MEDIUM", detail="A stabilizing sleeve can reduce volatility concentration across growth assets."),
		]
		if bool(mandate.get("usd_diversification_priority", True)):
			obs.append(PortfolioObservation(code="USD_DIVERSIFICATION_MANDATE", severity="INFO", detail="USD sleeve is configured as geographic and currency diversification."))
		return obs

	def _score_components(
		self,
		candidate: CandidateInstrument,
		market: MarketSnapshot,
		current_weight: float,
		holdings: list[Holding],
		mandate: dict[str, object],
	) -> list[RecommendationScoreComponent]:
		total = sum(h.market_value for h in holdings) or 1.0
		tech_weight = sum(h.market_value for h in holdings if self._is_technology_exposure_holding(h)) / total
		india_weight = sum(h.market_value for h in holdings if h.geography.lower() == "india") / total

		diversification = 52.0
		if candidate.market != "India":
			diversification += 8.0
		if india_weight > 0.55 and candidate.market != "India":
			diversification += 12.0
		if candidate.market == "Singapore":
			diversification += 4.0

		overlap_penalty = 0.0
		if candidate.ticker in {h.ticker.upper() for h in holdings}:
			overlap_penalty += 8.0
		if tech_weight > 0.15 and market.sector and market.sector.upper() == "TECHNOLOGY":
			overlap_penalty += 15.0

		concentration_penalty = 0.0
		if current_weight > 0.12:
			concentration_penalty = min(30.0, current_weight * 140.0)

		trend_score = self._bounded((market.return_3m_pct or 0.0) + 50.0, 0.0, 100.0) if market.return_3m_pct is not None else None
		vol_score = self._bounded(100.0 - ((market.realized_volatility or 0.0) * 200.0), 0.0, 100.0) if market.realized_volatility is not None else None
		drawdown_score = self._bounded(100.0 + (market.drawdown_pct or -30.0), 0.0, 100.0) if market.drawdown_pct is not None else None

		data_quality = 100.0
		if market.mode == "CACHED":
			data_quality = 72.0
		elif market.mode == "DEVELOPMENT_SEED":
			data_quality = 58.0
		elif market.mode == "UNAVAILABLE":
			data_quality = 25.0
		if market.fx_required and not market.fx_available:
			data_quality = min(data_quality, 35.0)

		portfolio_fit = self._bounded(diversification - overlap_penalty - (8.0 if market.fx_required and not market.fx_available else 0.0), 0.0, 100.0)

		components = [
			RecommendationScoreComponent(
				name="diversification_contribution",
				value=round(self._bounded(diversification, 0.0, 100.0), 2),
				weight=0.22,
				status="PASS",
				explanation="Higher score for ex-US/global and defensive diversification contributions.",
			),
			RecommendationScoreComponent(
				name="portfolio_fit",
				value=round(portfolio_fit, 2),
				weight=0.18,
				status="PASS",
				explanation="Portfolio fit derived from concentration overlap, diversification profile, and FX readiness.",
			),
			RecommendationScoreComponent(
				name="quality",
				value=None if market.quality_score is None else round(market.quality_score, 2),
				weight=0.15,
				status="UNAVAILABLE" if market.quality_score is None else "PASS",
				explanation="Quality score derived from available provider fundamentals.",
			),
			RecommendationScoreComponent(
				name="long_term_growth",
				value=None if market.growth_score is None else round(market.growth_score, 2),
				weight=0.12,
				status="UNAVAILABLE" if market.growth_score is None else "PASS",
				explanation="Growth score derived from available provider fundamentals.",
			),
			RecommendationScoreComponent(
				name="momentum_3m",
				value=None if trend_score is None else round(trend_score, 2),
				weight=0.10,
				status="UNAVAILABLE" if trend_score is None else "PASS",
				explanation="3-month trend proxy from available market history.",
			),
			RecommendationScoreComponent(
				name="volatility_penalty",
				value=None if vol_score is None else round(vol_score, 2),
				weight=0.08,
				status="UNAVAILABLE" if vol_score is None else "PASS",
				explanation="Realized-volatility transformed score (higher is better).",
			),
			RecommendationScoreComponent(
				name="drawdown_penalty",
				value=None if drawdown_score is None else round(drawdown_score, 2),
				weight=0.05,
				status="UNAVAILABLE" if drawdown_score is None else "PASS",
				explanation="Maximum drawdown transformed score (higher is better).",
			),
			RecommendationScoreComponent(
				name="concentration_penalty",
				value=round(self._bounded(100.0 - concentration_penalty, 0.0, 100.0), 2),
				weight=0.05,
				status="PASS",
				explanation="Penalty on adding to already-concentrated existing positions.",
			),
			RecommendationScoreComponent(
				name="overlap_penalty",
				value=round(self._bounded(100.0 - overlap_penalty, 0.0, 100.0), 2),
				weight=0.03,
				status="PASS",
				explanation="Penalty for overlapping existing mega-cap technology concentration.",
			),
			RecommendationScoreComponent(
				name="data_quality",
				value=round(data_quality, 2),
				weight=0.02,
				status="WARNING" if data_quality < 80 else "PASS",
				explanation="Data-mode quality score (LIVE > CACHED > DEVELOPMENT_SEED > UNAVAILABLE).",
			),
			RecommendationScoreComponent(
				name="fx_readiness",
				value=100.0 if (not market.fx_required or market.fx_available) else None,
				weight=0.02,
				status="UNAVAILABLE" if (market.fx_required and not market.fx_available) else "PASS",
				explanation="Cross-currency allocation requires a live FX conversion rate.",
			),
		]
		return components

	def _weighted_score(self, components: list[RecommendationScoreComponent]) -> float:
		usable = [c for c in components if c.value is not None]
		if not usable:
			return 0.0
		total_weight = sum(c.weight for c in usable)
		if total_weight <= 0:
			return 0.0
		return sum((c.value or 0.0) * (c.weight / total_weight) for c in usable)

	def _confidence_from_components(self, components: list[RecommendationScoreComponent], market: MarketSnapshot) -> float:
		missing = len([c for c in components if c.status == "UNAVAILABLE"])
		confidence = 0.88 - (missing * 0.05)
		if market.mode == "CACHED":
			confidence -= 0.10
		elif market.mode == "DEVELOPMENT_SEED":
			confidence -= 0.22
		elif market.mode == "UNAVAILABLE":
			confidence -= 0.35
		if market.is_stale:
			confidence -= 0.05
		return self._bounded(confidence, 0.05, 0.95)

	def _map_action(
		self,
		score: float,
		current_value: float,
		current_weight: float,
		candidate: CandidateInstrument,
		holdings: list[Holding],
	) -> str:
		if current_weight > 0.18:
			return "REDUCE"
		if score >= 72.0:
			return "ADD" if current_value > 0 else "BUY"
		if current_value > 0 and score >= 56.0:
			return "HOLD"
		if score >= 48.0:
			return "RESEARCH"
		return "AVOID"

	def _inject_existing_position_observations(
		self,
		rows: list[AllocationRecommendation],
		holdings: list[Holding],
		total_before: float,
		total_after: float,
	) -> list[AllocationRecommendation]:
		covered = {r.ticker.upper() for r in rows}
		for h in holdings:
			t = h.ticker.upper()
			if t in covered:
				continue
			current_weight = 0.0 if total_before <= 0 else h.market_value / total_before
			action = "REDUCE" if (self._is_technology_exposure_holding(h) and current_weight > 0.09) else "HOLD"
			rows.append(
				AllocationRecommendation(
					action=action,
					ticker=t,
					instrument_name=h.name,
					portfolio_role="Existing Position",
					current_value=round(h.market_value, 2),
					current_weight=round(current_weight, 4),
					proposed_allocation=0.0,
					proposed_total_value=round(h.market_value, 2),
					post_weight=round(0.0 if total_after <= 0 else h.market_value / total_after, 4),
					score=58.0 if action == "HOLD" else 42.0,
					confidence=0.65,
					market_data_provider="local_portfolio_snapshot",
					market_data_mode="UNAVAILABLE",
							market_data_as_of=_now_iso(),
					is_stale=False,
					fallback_reason=None,
					seeded_input=False,
					rationale="Existing position review based on concentration and diversification rules.",
					diversification_contribution="Observation only; no new capital allocated.",
					risks=["Concentration can increase drawdown risk."],
					unavailable_inputs=[],
					conditions_to_change=["Re-evaluate after next contribution cycle."],
					components=[],
					evidence=[RecommendationEvidence(code="CURRENT_HOLDING", detail="Position exists in current portfolio.", source="portfolio_snapshot")],
				)
			)
		return rows

	def _is_technology_exposure_holding(self, holding: Holding) -> bool:
		sector_text = (holding.sector or "").strip().lower()
		if not sector_text:
			# Missing sector degrades this signal by not treating the holding as technology concentration.
			return False
		keywords = ("technology", "information technology", "semiconductor", "software")
		return any(token in sector_text for token in keywords)

	def _allocate_capital(self, rows: list[AllocationRecommendation], investable_amount: float) -> None:
		actionable = [r for r in rows if r.action in {"BUY", "ADD"}]
		if not actionable:
			return

		max_alloc = 1900.0
		min_alloc = 350.0
		score_sum = sum(max(1.0, r.score) for r in actionable)
		provisional: dict[str, float] = {}
		for row in actionable:
			raw = investable_amount * (max(1.0, row.score) / score_sum)
			alloc = max(min_alloc, min(max_alloc, round(raw, 2)))
			provisional[row.ticker] = alloc

		total = round(sum(provisional.values()), 2)
		# First normalize if over-allocated.
		while total > investable_amount and actionable:
			adjustable = [r for r in actionable if provisional[r.ticker] > (min_alloc + 0.01)]
			if not adjustable:
				break
			row = max(adjustable, key=lambda r: provisional[r.ticker])
			step = min(10.0, total - investable_amount)
			provisional[row.ticker] = max(min_alloc, round(provisional[row.ticker] - step, 2))
			total = round(sum(provisional.values()), 2)

		while total < investable_amount and actionable:
			adjustable = [r for r in actionable if provisional[r.ticker] < (max_alloc - 0.01)]
			if not adjustable:
				break
			row = max(adjustable, key=lambda r: r.score)
			step = min(10.0, investable_amount - total)
			provisional[row.ticker] = min(max_alloc, round(provisional[row.ticker] + step, 2))
			total = round(sum(provisional.values()), 2)
			if math.isclose(total, investable_amount, abs_tol=1.0):
				break

		for row in actionable:
			row.proposed_allocation = round(provisional.get(row.ticker, 0.0), 2)
			row.proposed_total_value = round(row.current_value + row.proposed_allocation, 2)

	def _refresh_post_allocation_weights(
		self,
		rows: list[AllocationRecommendation],
		total_after: float,
	) -> list[AllocationRecommendation]:
		if total_after <= 0:
			return rows
		for row in rows:
			row.post_weight = round(row.proposed_total_value / total_after, 4)
		rows.sort(key=lambda r: (r.proposed_allocation, r.score), reverse=True)
		return rows

	def _freshness_summary(self, rows: list[AllocationRecommendation]) -> str:
		modes = {r.market_data_mode for r in rows if r.action in {"BUY", "ADD"}}
		if not modes:
			return "UNAVAILABLE"
		if modes == {"LIVE"}:
			return "LIVE"
		if "LIVE" in modes and len(modes) > 1:
			return "MIXED"
		if modes == {"CACHED"}:
			return "CACHED"
		if modes == {"DEVELOPMENT_SEED"}:
			return "DEVELOPMENT_SEED"
		return "MIXED"

	def _rationale(self, action: str, candidate: CandidateInstrument, score: float) -> str:
		if action in {"BUY", "ADD"}:
			role_text = candidate.portfolio_role.lower() if candidate.portfolio_role != "UNAVAILABLE" else "current evidence profile"
			return (
				f"{candidate.ticker} improves mandate fit via {role_text} while maintaining "
				f"local score discipline ({round(score, 1)})."
			)
		if action == "REDUCE":
			return "Position flagged for concentration control under diversification-first mandate."
		if action == "HOLD":
			return "Existing position retained without new capital while higher-diversification opportunities are funded."
		if action == "RESEARCH":
			return "Candidate is promising but requires additional supporting evidence before capital allocation."
		return "Candidate deprioritized due to lower current portfolio fit under configured guardrails."

	def _diversification_message(self, candidate: CandidateInstrument, holdings: list[Holding], mandate: dict[str, object]) -> str:
		if candidate.market != "India":
			return "Improves cross-market diversification relative to India-dominant holdings."
		return "Diversification contribution is limited versus current market concentration profile."

	def _risks(self, candidate: CandidateInstrument, market: MarketSnapshot) -> list[str]:
		risks = [
			"Advisory-only output; no automatic trading is performed.",
			"Position-level volatility can be high over short horizons.",
		]
		if market.mode in {"CACHED", "DEVELOPMENT_SEED", "UNAVAILABLE"}:
			risks.append("Some market inputs are not fully live and can reduce reliability.")
		if market.fx_required and not market.fx_available:
			risks.append("Required FX conversion rate was unavailable for cross-currency allocation.")
		return risks

	def _conditions_to_change(self, candidate: CandidateInstrument) -> list[str]:
		return [
			"Re-run recommendation after next monthly contribution or material portfolio change.",
			"Reassess if concentration thresholds or mandate assumptions change.",
			f"Re-evaluate {candidate.ticker} if data quality status worsens.",
		]

	def _evidence(self, candidate: CandidateInstrument, market: MarketSnapshot, holdings: list[Holding]) -> list[RecommendationEvidence]:
		out = [
			RecommendationEvidence(code="MANDATE_CONTEXT", detail="USD sleeve configured for diversification and resilience.", source="configured_mandate"),
			RecommendationEvidence(code="PORTFOLIO_SNAPSHOT", detail="Current holdings and weights used for concentration analysis.", source="portfolio_snapshot"),
		]
		if market.latest_price is not None:
			out.append(RecommendationEvidence(code="MARKET_PRICE", detail=f"Latest usable price {market.latest_price}.", source=market.provider))
		if market.return_3m_pct is not None:
			out.append(RecommendationEvidence(code="TREND_3M", detail=f"3-month return proxy {round(market.return_3m_pct, 2)}%.", source=market.provider))
		return out

	def _assumptions(self, mandate: dict[str, object]) -> list[str]:
		return [
			"India exposure remains materially larger than USD sleeve and motivates diversification-focused deployment.",
			"Candidate discovery starts from configured cross-market universes (US, India, Singapore) and validates evidence at runtime.",
			"Horizon is long-term (10-15 years) with moderate-high risk tolerance.",
			"Initial allocation targets meaningful position sizes and avoids excessive position proliferation.",
			"Monthly future contribution estimate (~USD 5,000) supports staged deployment over time.",
		]

	def _portfolio_role_from_characteristics(self, market: str, sector: str | None) -> str:
		if market != "India":
			return "GEOGRAPHIC_DIVERSIFIER"
		if sector and sector.lower() in {"utilities", "consumer defensive", "healthcare"}:
			return "DEFENSIVE"
		return "UNAVAILABLE"

	def _quality_score_from_fundamentals(self, info: dict[str, object]) -> float | None:
		values: list[float] = []
		roe = info.get("returnOnEquity")
		if isinstance(roe, (int, float)):
			values.append(self._bounded(float(roe) * 250.0, 0.0, 100.0))
		margin = info.get("profitMargins")
		if isinstance(margin, (int, float)):
			values.append(self._bounded(float(margin) * 250.0, 0.0, 100.0))
		de = info.get("debtToEquity")
		if isinstance(de, (int, float)):
			values.append(self._bounded(100.0 - min(100.0, float(de) / 2.5), 0.0, 100.0))
		if not values:
			return None
		return round(mean(values), 2)

	def _growth_score_from_fundamentals(self, info: dict[str, object]) -> float | None:
		values: list[float] = []
		rev = info.get("revenueGrowth")
		if isinstance(rev, (int, float)):
			values.append(self._bounded((float(rev) + 0.2) * 250.0, 0.0, 100.0))
		earn = info.get("earningsGrowth")
		if isinstance(earn, (int, float)):
			values.append(self._bounded((float(earn) + 0.2) * 250.0, 0.0, 100.0))
		if not values:
			return None
		return round(mean(values), 2)

	def _build_top_ranked_candidates(self, rows: list[AllocationRecommendation], candidates: list[CandidateInstrument]) -> list[dict[str, object]]:
		meta = {c.ticker.upper(): c for c in candidates}
		ranked = sorted(rows, key=lambda r: r.score, reverse=True)
		out: list[dict[str, object]] = []
		for row in ranked[:20]:
			c = meta.get(row.ticker.upper())
			out.append(
				{
					"market": c.market if c else "US",
					"ticker": row.ticker,
					"company": row.instrument_name,
					"exchange": c.exchange if c else None,
					"issuer_country": c.issuer_country if c else None,
					"trading_currency": c.trading_currency if c else "USD",
					"instrument_type": c.instrument_type if c else "Equity",
					"status": "ELIGIBLE",
					"evidence_coverage": "FULL" if not row.unavailable_inputs else "PARTIAL",
					"security_attractiveness_score": row.score,
					"portfolio_suitability_score": round(min(100.0, row.score + 2.0), 2),
					"combined_recommendation_score": row.score,
					"confidence": row.confidence,
					"action": row.action,
					"challenge_flags": list(row.unavailable_inputs),
					"portfolio_role": row.portfolio_role,
					"provider_symbol": row.ticker,
					"missing_fields": list(row.unavailable_inputs),
					"top_positive_contributors": [
						{"name": comp.name, "value": comp.value, "weight": comp.weight}
						for comp in sorted([x for x in row.components if x.value is not None], key=lambda x: x.value or 0.0, reverse=True)[:3]
					],
					"top_negative_contributors": [
						{"name": comp.name, "value": comp.value, "weight": comp.weight}
						for comp in sorted([x for x in row.components if x.value is not None], key=lambda x: x.value or 0.0)[:3]
					],
					"metric_evidence": [{"code": ev.code, "detail": ev.detail, "source": ev.source} for ev in row.evidence],
				}
			)
		return out

	def _build_actionable_recommendations(self, rows: list[AllocationRecommendation], candidates: list[CandidateInstrument], base_currency: str) -> list[dict[str, object]]:
		meta = {c.ticker.upper(): c for c in candidates}
		out: list[dict[str, object]] = []
		for row in rows:
			if row.action not in {"BUY", "ADD"}:
				continue
			c = meta.get(row.ticker.upper())
			local_ccy = (c.trading_currency if c and c.trading_currency else base_currency).upper()
			fx = self._fx_rate(base_currency, local_ccy)
			allocation_local = None if fx is None else row.proposed_allocation * fx
			units = None
			price = self._cache.get(row.ticker, (None, None))[1].latest_price if row.ticker in self._cache else None
			if allocation_local is not None and price and price > 0:
				units = round(allocation_local / price, 4)
			out.append(
				{
					"ticker": row.ticker,
					"action": row.action,
					"allocation_usd": round(row.proposed_allocation, 2),
					"allocation_local": None if allocation_local is None else round(allocation_local, 2),
					"local_currency": local_ccy,
					"units": units,
					"fx_available": fx is not None,
					"score": row.score,
					"confidence": row.confidence,
				}
			)
		return out

	def _build_existing_holding_actions(self, rows: list[AllocationRecommendation]) -> list[dict[str, object]]:
		return [
			{
				"ticker": row.ticker,
				"action": row.action,
				"current_value": row.current_value,
				"current_weight": row.current_weight,
				"score": row.score,
			}
			for row in rows
			if row.portfolio_role == "Existing Position"
		]

	def _portfolio_exposure_summary(self, holdings: list[Holding], base_currency: str) -> dict[str, object]:
		positions = []
		missing_fx_pairs: list[str] = []
		for h in holdings:
			fx = self._fx_rate((h.currency or base_currency).upper(), base_currency.upper())
			if fx is None:
				base_value = None
				missing_fx_pairs.append(f"{(h.currency or base_currency).upper()}/{base_currency.upper()}")
			else:
				base_value = float(h.market_value) * fx
			positions.append(
				{
					"ticker": h.ticker,
					"country": h.geography or "Unknown",
					"currency": (h.currency or base_currency).upper(),
					"sector": h.sector or "Unknown",
					"local_value": float(h.market_value),
					"base_value": base_value,
				}
			)
		return self._build_exposure_summary_from_positions(positions, base_currency, missing_fx_pairs)

	def _portfolio_exposure_summary_after(self, holdings: list[Holding], rows: list[AllocationRecommendation], base_currency: str) -> dict[str, object]:
		positions = []
		missing_fx_pairs: list[str] = []
		for h in holdings:
			fx = self._fx_rate((h.currency or base_currency).upper(), base_currency.upper())
			if fx is None:
				base_value = None
				missing_fx_pairs.append(f"{(h.currency or base_currency).upper()}/{base_currency.upper()}")
			else:
				base_value = float(h.market_value) * fx
			positions.append(
				{
					"ticker": h.ticker.upper(),
					"country": h.geography or "Unknown",
					"currency": (h.currency or base_currency).upper(),
					"sector": h.sector or "Unknown",
					"local_value": float(h.market_value),
					"base_value": base_value,
				}
			)

		lookup = {p["ticker"]: p for p in positions}
		for row in rows:
			if row.proposed_allocation <= 0:
				continue
			key = row.ticker.upper()
			entry = lookup.get(key)
			if entry is None:
				entry = {"ticker": key, "country": "Unknown", "currency": base_currency.upper(), "sector": "Unknown", "local_value": 0.0, "base_value": 0.0}
				positions.append(entry)
				lookup[key] = entry
			if entry["base_value"] is None:
				continue
			entry["base_value"] += row.proposed_allocation
			entry["local_value"] += row.proposed_allocation

		return self._build_exposure_summary_from_positions(positions, base_currency, missing_fx_pairs)

	def _build_exposure_summary_from_positions(self, positions: list[dict[str, object]], base_currency: str, missing_fx_pairs: list[str]) -> dict[str, object]:
		known_positions = [p for p in positions if p["base_value"] is not None]
		total = sum(float(p["base_value"]) for p in known_positions) or 1.0
		by_country: dict[str, float] = {}
		by_currency: dict[str, float] = {}
		by_sector: dict[str, float] = {}
		for p in known_positions:
			v = float(p["base_value"])
			by_country[str(p["country"])] = by_country.get(str(p["country"]), 0.0) + v
			by_currency[str(p["currency"])] = by_currency.get(str(p["currency"]), 0.0) + v
			by_sector[str(p["sector"])] = by_sector.get(str(p["sector"]), 0.0) + v

		top_positions = sorted(known_positions, key=lambda x: float(x["base_value"]), reverse=True)[:10]
		top_weights = [float(p["base_value"]) / total for p in top_positions]
		concentration = {
			"top1_weight": round(top_weights[0], 4) if top_weights else 0.0,
			"top3_weight": round(sum(top_weights[:3]), 4),
			"top5_weight": round(sum(top_weights[:5]), 4),
			"position_count": len(positions),
		}

		def _to_pct_rows(source: dict[str, float], key_name: str) -> list[dict[str, object]]:
			return [
				{key_name: k, "base_value": round(v, 2), "percentage": round(v / total, 4)}
				for k, v in sorted(source.items(), key=lambda item: item[1], reverse=True)
			]

		return {
			"base_currency": base_currency.upper(),
			"total_value": round(total, 2),
			"country_exposure": _to_pct_rows(by_country, "country"),
			"currency_exposure": _to_pct_rows(by_currency, "currency"),
			"sector_exposure": _to_pct_rows(by_sector, "sector"),
			"concentration": concentration,
			"top_positions": [
				{
					"ticker": p["ticker"],
					"country": p["country"],
					"currency": p["currency"],
					"sector": p["sector"],
					"local_value": round(float(p["local_value"]), 2),
					"base_value": round(float(p["base_value"]), 2),
					"weight": round(float(p["base_value"]) / total, 4),
				}
				for p in top_positions
			],
			"valuation_breakdown": {
				"equity_pct": 1.0,
				"cash_pct": 0.0,
				"other_pct": 0.0,
				"missing_fx_pairs": sorted(set(missing_fx_pairs)),
				"known_value_coverage": round((len(known_positions) / len(positions)), 4) if positions else 1.0,
			},
		}

	def _build_data_quality_summary(
		self,
		rows: list[AllocationRecommendation],
		excluded: list[dict[str, object]],
		total_source: float,
		base_currency: str,
		portfolio_before: dict[str, object],
	) -> dict[str, object]:
		providers = sorted({r.market_data_provider for r in rows if r.market_data_provider})
		latest = {r.ticker: r.market_data_as_of for r in rows if r.market_data_as_of and r.action in {"BUY", "ADD", "RESEARCH"}}
		missing_inputs: list[str] = []
		for row in rows:
			for item in row.unavailable_inputs:
				missing_inputs.append(f"{row.ticker}:{item}")
		total_authoritative = float(portfolio_before.get("total_value") or 0.0)
		return {
			"providers": providers,
			"latest_timestamps": latest,
			"missing_inputs": sorted(set(missing_inputs))[:200],
			"excluded_securities": excluded[:50],
			"portfolio_total_mismatch": abs(total_source - total_authoritative) > max(1.0, 0.05 * max(total_authoritative, 1.0)),
			"portfolio_total_source": round(total_source, 2),
			"portfolio_total_authoritative": round(total_authoritative, 2),
			"base_currency": base_currency.upper(),
		}

	def _build_sensitivity_summary(self, rows: list[AllocationRecommendation], actionable: list[dict[str, object]]) -> dict[str, object]:
		if not actionable:
			return {"classification": "LOW_SIGNAL", "scenarios": [], "top_candidates_stable": False}
		top = sorted([r for r in rows if r.action in {"BUY", "ADD"}], key=lambda r: r.score, reverse=True)[:5]
		scenarios: list[dict[str, object]] = []
		for shock in (-10.0, -5.0, 5.0, 10.0):
			scenarios.append(
				{
					"name": f"market_shock_{int(shock)}pct",
					"shock_pct": shock,
					"relative_score_shift": round(shock * 0.15, 2),
					"implied_confidence_shift": round(shock * -0.002, 3),
				}
			)
		return {
			"classification": "MEDIUM",
			"scenarios": scenarios,
			"top_candidates_stable": len(top) >= 3,
		}

	def _fx_rate(self, from_currency: str, to_currency: str) -> float | None:
		fc = from_currency.upper()
		tc = to_currency.upper()
		if fc == tc:
			return 1.0
		snap = live_feeds.fx_rate(fc, tc)
		if snap.rate is not None and snap.rate > 0:
			return float(snap.rate)
		return None

	@staticmethod
	def _bounded(value: float, low: float, high: float) -> float:
		return max(low, min(high, value))


recommendation_mvp_service = RecommendationMVPService()

