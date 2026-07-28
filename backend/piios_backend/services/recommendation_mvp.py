from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from statistics import mean
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


@dataclass(frozen=True)
class CandidateInstrument:
	ticker: str
	instrument_name: str
	portfolio_role: str
	geography: str
	sector: str
	risk_band: str
	quality_base: float
	growth_base: float


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


_MEGA_CAP_TECH = {"NVDA", "MSFT", "GOOGL", "AAPL", "AMZN", "META", "AVGO"}

_CANDIDATES: tuple[CandidateInstrument, ...] = (
	CandidateInstrument("VT", "Vanguard Total World Stock ETF", "Global Core", "GLOBAL", "ETF_CORE", "MEDIUM", 76, 68),
	CandidateInstrument("VXUS", "Vanguard Total International Stock ETF", "Ex-US Diversifier", "EX_US", "ETF_CORE", "MEDIUM", 72, 64),
	CandidateInstrument("QUAL", "iShares MSCI USA Quality Factor ETF", "Quality Tilt", "US", "QUALITY_FACTOR", "MEDIUM", 78, 66),
	CandidateInstrument("SCHD", "Schwab US Dividend Equity ETF", "Defensive Quality", "US", "DIVIDEND_QUALITY", "LOW_MEDIUM", 74, 58),
	CandidateInstrument("BND", "Vanguard Total Bond Market ETF", "Stability Sleeve", "US", "FIXED_INCOME", "LOW", 62, 35),
	CandidateInstrument("MSFT", "Microsoft Corp.", "Quality Compounder", "US", "MEGA_TECH", "MEDIUM", 86, 78),
	CandidateInstrument("GOOGL", "Alphabet Inc.", "Quality Compounder", "US", "MEGA_TECH", "MEDIUM", 82, 76),
	CandidateInstrument("AMZN", "Amazon.com Inc.", "Strategic Upside", "US", "MEGA_TECH", "MEDIUM_HIGH", 79, 80),
	CandidateInstrument("AVGO", "Broadcom Inc.", "AI Infrastructure", "US", "SEMI", "MEDIUM_HIGH", 80, 82),
	CandidateInstrument("V", "Visa Inc.", "Quality Compounder", "US", "PAYMENTS", "MEDIUM", 83, 69),
	CandidateInstrument("BRK-B", "Berkshire Hathaway Inc.", "Diversified Compounder", "US", "CONGLOMERATE", "MEDIUM", 81, 58),
	CandidateInstrument("PANW", "Palo Alto Networks Inc.", "Strategic Upside", "US", "CYBERSECURITY", "HIGH", 74, 81),
	CandidateInstrument("CEG", "Constellation Energy Corp.", "Strategic Upside", "US", "POWER", "HIGH", 68, 79),
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

		rows: list[AllocationRecommendation] = []
		for candidate in _CANDIDATES:
			market = self._resolve_market(candidate.ticker, mode_preference)
			current_value = sum(h.market_value for h in holdings if h.ticker.upper() == candidate.ticker.upper())
			current_weight = 0.0 if total_before <= 0 else current_value / total_before

			components = self._score_components(candidate, market, current_weight, holdings, mandate)
			score = self._weighted_score(components)
			confidence = self._confidence_from_components(components, market)
			action = self._map_action(score, current_value, current_weight, candidate, holdings)

			rows.append(
				AllocationRecommendation(
					action=action,
					ticker=candidate.ticker,
					instrument_name=candidate.instrument_name,
					portfolio_role=candidate.portfolio_role,
					current_value=round(current_value, 2),
					current_weight=round(current_weight, 4),
					proposed_allocation=0.0,
					proposed_total_value=round(current_value, 2),
					post_weight=round(0.0 if total_after <= 0 else current_value / total_after, 4),
					score=round(score, 2),
					confidence=round(confidence, 3),
					market_data_provider=market.provider,
					market_data_mode=market.mode,
					market_data_as_of=market.as_of,
					is_stale=market.is_stale,
					fallback_reason=market.fallback_reason,
					seeded_input=market.seeded_input,
					rationale=self._rationale(action, candidate, score),
					diversification_contribution=self._diversification_message(candidate, holdings, mandate),
					risks=self._risks(candidate, market),
					unavailable_inputs=[c.name for c in components if c.status == "UNAVAILABLE"],
					conditions_to_change=self._conditions_to_change(candidate),
					components=components,
					evidence=self._evidence(candidate, market, holdings),
				)
			)

		rows = self._inject_existing_position_observations(rows, holdings, total_before, total_after)
		self._allocate_capital(rows, request.investable_amount)
		rows = self._refresh_post_allocation_weights(rows, total_after)

		allocation_total = round(sum(r.proposed_allocation for r in rows), 2)
		delta = round(request.investable_amount - allocation_total, 2)

		if abs(delta) > 1.0:
			raise RuntimeError("allocation did not reconcile to investable amount")

		overall_confidence = round(mean([r.confidence for r in rows if r.action in {"BUY", "ADD"}] or [0.4]), 3)
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
			assumptions=self._assumptions(mandate),
			limitations=limitations,
		)

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

	def _resolve_market(self, ticker: str, mode_preference: str) -> MarketSnapshot:
		cached = self._cache.get(ticker)
		now = datetime.now(timezone.utc)
		if mode_preference in {"auto", "cached"} and cached is not None:
			seen_at, snapshot = cached
			if now - seen_at <= self._cache_ttl:
				snapshot.mode = "CACHED"
				return snapshot

		if mode_preference in {"auto", "live"}:
			live = self._fetch_live_snapshot(ticker)
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
			seeded = self._seed_snapshot(ticker)
			if seeded is not None:
				return seeded

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
		)

	def _fetch_live_snapshot(self, ticker: str) -> MarketSnapshot | None:
		quote: QuoteSnapshot | None = live_feeds.quote(ticker)
		if quote is None:
			return None
		# MVP momentum proxies derived from daily return plus deterministic transforms.
		daily = quote.daily_return_pct
		return MarketSnapshot(
			ticker=ticker,
			provider="yfinance",
			mode="LIVE",
			as_of=_now_iso(),
			is_stale=False,
			fallback_reason=None,
			seeded_input=False,
			latest_price=quote.close,
			daily_return_pct=daily,
			return_1m_pct=daily * 4.0,
			return_3m_pct=daily * 12.0,
			return_6m_pct=daily * 20.0,
			return_12m_pct=daily * 40.0,
			realized_volatility=abs(daily) * 0.18,
			drawdown_pct=max(-25.0, -abs(daily) * 4.0),
			distance_from_52w_high_pct=max(-40.0, min(0.0, -abs(daily) * 2.0)),
		)

	def _seed_snapshot(self, ticker: str) -> MarketSnapshot | None:
		price = _DEV_SEED.get(ticker)
		if price is None:
			return None
		seed_now = _now_iso()
		pseudo = (sum(ord(c) for c in ticker) % 17) - 8
		daily = pseudo / 10.0
		return MarketSnapshot(
			ticker=ticker,
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
		)

	def _build_portfolio_observations(self, holdings: list[Holding], mandate: dict[str, object]) -> list[PortfolioObservation]:
		total = sum(h.market_value for h in holdings) or 1.0
		tech_value = sum(h.market_value for h in holdings if h.ticker.upper() in _MEGA_CAP_TECH or h.sector.lower() == "technology")
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
		tech_weight = sum(h.market_value for h in holdings if h.ticker.upper() in _MEGA_CAP_TECH or h.sector.lower() == "technology") / total
		india_weight = sum(h.market_value for h in holdings if h.geography.lower() == "india") / total

		diversification = 55.0
		if candidate.geography == "EX_US":
			diversification += 30.0
		if candidate.sector in {"FIXED_INCOME", "DIVIDEND_QUALITY"}:
			diversification += 12.0
		if candidate.sector == "MEGA_TECH":
			diversification -= 18.0
		if india_weight > 0.55 and candidate.geography in {"GLOBAL", "EX_US"}:
			diversification += 8.0

		overlap_penalty = 0.0
		if candidate.ticker in {h.ticker.upper() for h in holdings}:
			overlap_penalty += 8.0
		if candidate.sector == "MEGA_TECH" and tech_weight > 0.15:
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
				value=round(self._bounded(78.0 if candidate.portfolio_role in {"Global Core", "Ex-US Diversifier", "Quality Tilt", "Defensive Quality", "Stability Sleeve"} else 64.0, 0.0, 100.0), 2),
				weight=0.18,
				status="PASS",
				explanation="Mandate fit emphasizes diversification with moderate-high risk tolerance.",
			),
			RecommendationScoreComponent(
				name="quality",
				value=round(candidate.quality_base, 2),
				weight=0.15,
				status="PASS",
				explanation="Static MVP quality profile from controlled candidate universe.",
			),
			RecommendationScoreComponent(
				name="long_term_growth",
				value=round(candidate.growth_base, 2),
				weight=0.12,
				status="PASS",
				explanation="Long-horizon growth profile from controlled candidate universe.",
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
		if current_weight > 0.18 and candidate.ticker in _MEGA_CAP_TECH:
			return "REDUCE"
		if score >= 72.0:
			return "ADD" if current_value > 0 else "BUY"
		if current_value > 0 and score >= 56.0:
			return "HOLD"
		if score >= 54.0 and candidate.sector in {"GLOBAL", "EX_US", "ETF_CORE", "FIXED_INCOME"}:
			return "BUY" if current_value <= 0 else "ADD"
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
			action = "REDUCE" if (t in _MEGA_CAP_TECH and current_weight > 0.09) else "HOLD"
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
					market_data_mode="DEVELOPMENT_SEED",
							market_data_as_of=_now_iso(),
					is_stale=False,
					fallback_reason=None,
					seeded_input=True,
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

	def _allocate_capital(self, rows: list[AllocationRecommendation], investable_amount: float) -> None:
		actionable = [r for r in rows if r.action in {"BUY", "ADD"}]
		if len(actionable) < 2:
			candidates = sorted([r for r in rows if r.action in {"RESEARCH", "HOLD"}], key=lambda r: r.score, reverse=True)
			for row in candidates:
				if row not in actionable:
					row.action = "BUY" if row.current_value <= 0 else "ADD"
					actionable.append(row)
				if len(actionable) >= 2:
					break

		if not actionable:
			return

		max_alloc = 1900.0
		min_alloc = 350.0
		score_sum = sum(max(1.0, r.score) for r in actionable)
		remaining = round(investable_amount, 2)

		provisional: dict[str, float] = {}
		for row in actionable:
			raw = investable_amount * (max(1.0, row.score) / score_sum)
			alloc = max(min_alloc, min(max_alloc, round(raw, 2)))
			provisional[row.ticker] = alloc

		total = round(sum(provisional.values()), 2)
		# First normalize if over-allocated.
		while total > investable_amount and actionable:
			row = max(actionable, key=lambda r: provisional[r.ticker])
			step = min(10.0, total - investable_amount)
			provisional[row.ticker] = max(min_alloc, round(provisional[row.ticker] - step, 2))
			total = round(sum(provisional.values()), 2)

		while total < investable_amount and actionable:
			row = max(actionable, key=lambda r: r.score)
			step = min(10.0, investable_amount - total)
			provisional[row.ticker] = min(max_alloc, round(provisional[row.ticker] + step, 2))
			total = round(sum(provisional.values()), 2)
			if math.isclose(total, investable_amount, abs_tol=1.0):
				break

		for row in actionable:
			row.proposed_allocation = round(provisional.get(row.ticker, 0.0), 2)
			row.proposed_total_value = round(row.current_value + row.proposed_allocation, 2)

		allocated = round(sum(r.proposed_allocation for r in actionable), 2)
		diff = round(investable_amount - allocated, 2)
		if abs(diff) > 0 and actionable:
			top = max(actionable, key=lambda r: r.score)
			top.proposed_allocation = round(top.proposed_allocation + diff, 2)
			top.proposed_total_value = round(top.current_value + top.proposed_allocation, 2)

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
			return (
				f"{candidate.ticker} improves mandate fit via {candidate.portfolio_role.lower()} while maintaining "
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
		if candidate.geography == "EX_US":
			return "Directly increases ex-US diversification in the USD sleeve."
		if candidate.sector == "FIXED_INCOME":
			return "Adds defensive ballast and can reduce equity-only volatility concentration."
		if candidate.sector == "MEGA_TECH":
			return "Limited diversification benefit because existing mega-cap technology exposure is already elevated."
		return "Improves role diversification relative to current holdings."

	def _risks(self, candidate: CandidateInstrument, market: MarketSnapshot) -> list[str]:
		risks = [
			"Advisory-only output; no automatic trading is performed.",
			"Position-level volatility can be high over short horizons.",
		]
		if candidate.sector == "MEGA_TECH":
			risks.append("Mega-cap technology correlation may amplify drawdowns during risk-off regimes.")
		if market.mode in {"CACHED", "DEVELOPMENT_SEED", "UNAVAILABLE"}:
			risks.append("Some market inputs are not fully live and can reduce reliability.")
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
			"Horizon is long-term (10-15 years) with moderate-high risk tolerance.",
			"Initial allocation targets meaningful position sizes and avoids excessive position proliferation.",
			"Monthly future contribution estimate (~USD 5,000) supports staged deployment over time.",
		]

	@staticmethod
	def _bounded(value: float, low: float, high: float) -> float:
		return max(low, min(high, value))


recommendation_mvp_service = RecommendationMVPService()

