from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from statistics import mean

import yfinance as yf

from piios_backend.core.config import settings
from piios_backend.schemas.enums import RecommendationStatus
from piios_backend.schemas.operations import ResearchDocumentResponse, ResearchFeedResponse
from piios_backend.schemas.recommendation import Recommendation, TacticalSignal, TopRecommendation


TOP_RECOMMENDATION_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "BRK-B", "JPM",
    "V", "MA", "LLY", "UNH", "XOM", "WMT", "JNJ", "PG", "HD", "MRK",
    "COST", "ABBV", "KO", "BAC", "PEP", "AMD", "ADBE", "CRM", "NFLX", "CVX",
    "ORCL", "TMO", "ACN", "MCD", "DHR", "ABT", "LIN", "CSCO", "WFC", "INTU",
    "CMCSA", "QCOM", "TXN", "PM", "IBM", "GE", "INTC", "CAT", "GS", "AMAT",
    "RTX", "SPGI", "BKNG", "NOW", "BLK", "PGR", "LOW", "ISRG", "MU", "UBER",
    "PANW", "ANET", "ETN", "DE", "LRCX", "SYK", "ADP", "TJX", "GILD", "VRTX",
]

CANONICAL_SECTORS = [
    "AI SaaS",
    "Data Centre",
    "Tech",
    "Consumption",
    "Mobility",
    "Auto",
    "Energy - Green",
    "Energy - Others",
    "Petro",
    "Agri",
]

SECTOR_FALLBACKS = {
    "AAPL": "Tech",
    "MSFT": "AI SaaS",
    "NVDA": "Data Centre",
    "AMZN": "Consumption",
    "GOOGL": "Tech",
    "META": "Tech",
    "AVGO": "Data Centre",
    "TSLA": "Mobility",
    "BRK-B": "Consumption",
    "JPM": "Tech",
    "V": "Tech",
    "MA": "Tech",
    "LLY": "Consumption",
    "UNH": "Consumption",
    "XOM": "Petro",
    "WMT": "Consumption",
    "JNJ": "Consumption",
    "PG": "Consumption",
    "HD": "Consumption",
    "MRK": "Consumption",
    "COST": "Consumption",
    "ABBV": "Consumption",
    "KO": "Consumption",
    "BAC": "Tech",
    "PEP": "Consumption",
    "AMD": "Data Centre",
    "ADBE": "AI SaaS",
    "CRM": "AI SaaS",
    "NFLX": "Tech",
    "CVX": "Petro",
    "ORCL": "AI SaaS",
    "TMO": "Consumption",
    "ACN": "AI SaaS",
    "MCD": "Consumption",
    "DHR": "Consumption",
    "ABT": "Consumption",
    "LIN": "Agri",
    "CSCO": "Tech",
    "WFC": "Tech",
    "INTU": "AI SaaS",
    "CMCSA": "Consumption",
    "QCOM": "Tech",
    "TXN": "Data Centre",
    "PM": "Consumption",
    "IBM": "Tech",
    "GE": "Mobility",
    "INTC": "Data Centre",
    "CAT": "Agri",
    "GS": "Tech",
    "AMAT": "Data Centre",
    "RTX": "Mobility",
    "SPGI": "Tech",
    "BKNG": "Consumption",
    "NOW": "AI SaaS",
    "BLK": "Tech",
    "PGR": "Consumption",
    "LOW": "Consumption",
    "ISRG": "Mobility",
    "MU": "Data Centre",
    "UBER": "Mobility",
    "PANW": "AI SaaS",
    "ANET": "Data Centre",
    "ETN": "Mobility",
    "DE": "Agri",
    "LRCX": "Data Centre",
    "SYK": "Consumption",
    "ADP": "AI SaaS",
    "TJX": "Consumption",
    "GILD": "Consumption",
    "VRTX": "Consumption",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_iso_from_epoch(epoch_seconds: int | None) -> str:
    if not epoch_seconds:
        return _now_iso()
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()


def _advisory_action(score: float, daily_pct: float, weekly_pct: float | None = None, volume_ratio: float | None = None) -> str:
    bullish_momentum = daily_pct >= 1.0 or (weekly_pct is not None and weekly_pct >= 2.0)
    weak_momentum = daily_pct <= -1.0 or (weekly_pct is not None and weekly_pct <= -2.0)
    high_volume_support = volume_ratio is None or volume_ratio >= 1.0

    if score >= 75 and bullish_momentum and high_volume_support:
        return "Advisory buy candidate"
    if score >= 60:
        return "Advisory accumulate"
    if score <= 40 and weak_momentum:
        return "Advisory sell candidate"
    if score <= 50:
        return "Advisory reduce / exit watch"
    return "Advisory hold"


def _safe_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        numeric = float(value)
        if math.isnan(numeric) or math.isinf(numeric):
            return None
        return numeric
    except (TypeError, ValueError):
        return None


def _metric_score(value: float | None, low: float, high: float, higher_is_better: bool = True) -> float | None:
    if value is None or high <= low:
        return None
    bounded = max(low, min(high, value))
    normalized = (bounded - low) / (high - low)
    if not higher_is_better:
        normalized = 1.0 - normalized
    return round(normalized * 100.0, 2)


def _percentile(value: float, values: list[float]) -> float:
    if not values:
        return 50.0
    count = sum(1 for item in values if item <= value)
    return round((count / len(values)) * 100.0, 2)


@dataclass
class QuoteSnapshot:
    ticker: str
    close: float
    prev_close: float

    @property
    def daily_return_pct(self) -> float:
        if self.prev_close == 0:
            return 0.0
        return ((self.close - self.prev_close) / self.prev_close) * 100


class LiveFeedService:
    def __init__(self) -> None:
        self._cooldown_until = datetime.min.replace(tzinfo=timezone.utc)

    def _enabled(self) -> bool:
        return settings.live_market_feeds

    def _can_attempt(self) -> bool:
        return self._enabled() and datetime.now(timezone.utc) >= self._cooldown_until

    def _trip_cooldown(self) -> None:
        self._cooldown_until = datetime.now(timezone.utc) + timedelta(minutes=10)

    def quote(self, ticker: str) -> QuoteSnapshot | None:
        if not self._can_attempt():
            return None
        try:
            history = yf.Ticker(ticker).history(period="2d", interval="1d", auto_adjust=False, timeout=4)
            if history.empty:
                return None
            close = float(history["Close"].iloc[-1])
            prev_close = float(history["Close"].iloc[-2] if len(history) > 1 else close)
            return QuoteSnapshot(ticker=ticker, close=close, prev_close=prev_close)
        except Exception:
            self._trip_cooldown()
            return None

    def sector_for_ticker(self, ticker: str) -> str:
        fallback = SECTOR_FALLBACKS.get(ticker, "Diversified")
        if not self._can_attempt():
            return fallback
        try:
            info = yf.Ticker(ticker).info
            raw_sector = str(info.get("sector") or "")
            raw_industry = str(info.get("industry") or "")
            text = f"{raw_sector} {raw_industry}".lower()

            if "software" in text or "saas" in text or "cloud" in text:
                return fallback if fallback == "AI SaaS" else "AI SaaS"
            if "semiconductor" in text or "chip" in text or "electronics" in text or "network" in text:
                return fallback if fallback == "Data Centre" else "Data Centre"
            if "auto" in text or "vehicle" in text or "mobility" in text or "transport" in text:
                return fallback if fallback == "Mobility" else "Mobility"
            if "energy" in text or "oil" in text or "gas" in text or "refining" in text:
                return fallback if fallback in {"Energy - Green", "Energy - Others", "Petro"} else "Petro"
            if "agri" in text or "farm" in text or "fertil" in text or "chemical" in text:
                return fallback if fallback == "Agri" else "Agri"
            if "consumer" in text or "retail" in text or "staple" in text or "household" in text:
                return fallback if fallback == "Consumption" else "Consumption"
            return fallback if fallback in CANONICAL_SECTORS else "Tech"
        except Exception:
            return fallback

    def build_research_feed(self, tickers: list[str]) -> ResearchFeedResponse:
        items: list[ResearchDocumentResponse] = []
        if self._can_attempt():
            for ticker in tickers[:4]:
                try:
                    news = yf.Ticker(ticker).news or []
                    for article in news[:2]:
                        items.append(
                            ResearchDocumentResponse(
                                title=article.get("title", f"{ticker} market update"),
                                source=article.get("publisher", "Yahoo Finance"),
                                timestamp=_to_iso_from_epoch(article.get("providerPublishTime")),
                                url=article.get("link", f"https://finance.yahoo.com/quote/{ticker}"),
                                credibility_score=82,
                                extracted_entities=[ticker],
                                related_ticker_theme=ticker,
                            )
                        )
                except Exception:
                    self._trip_cooldown()
                    break

        if not items:
            return ResearchFeedResponse(
                items=[
                    ResearchDocumentResponse(
                        title="AI Infrastructure Outlook",
                        source="Independent Research",
                        timestamp="2026-06-03T00:00:00Z",
                        url="https://example.com/research/ai-infra",
                        credibility_score=79,
                        extracted_entities=["NVDA", "AVGO"],
                        related_ticker_theme="AI Infrastructure",
                    )
                ]
            )
        return ResearchFeedResponse(items=items)

    def build_scores(self, tickers: list[str]) -> dict:
        stock_scores: list[dict] = []
        for ticker in tickers[:6]:
            snapshot = self.quote(ticker)
            if not snapshot:
                continue
            # Convert daily return to bounded 0-100 score.
            score = max(0.0, min(100.0, 50.0 + (snapshot.daily_return_pct * 8.0)))
            stock_scores.append(
                {
                    "ticker": ticker,
                    "sector": self.sector_for_ticker(ticker),
                    "score": round(score, 2),
                    "daily_pct": round(snapshot.daily_return_pct, 2),
                    "recommended_action": _advisory_action(score, snapshot.daily_return_pct),
                }
            )

        if not stock_scores:
            stock_scores = [
                {
                    "ticker": "NVDA",
                    "sector": self.sector_for_ticker("NVDA"),
                    "score": 86,
                    "daily_pct": 0.0,
                    "recommended_action": "Advisory hold",
                },
                {
                    "ticker": "AVGO",
                    "sector": self.sector_for_ticker("AVGO"),
                    "score": 82,
                    "daily_pct": 0.0,
                    "recommended_action": "Advisory hold",
                },
            ]

        return {
            "stock_scores": stock_scores,
            "source_scores": [
                {"source": "Yahoo Finance Live Feed", "score": 84 if self._can_attempt() else 72},
                {"source": "Independent Research", "score": 79},
            ],
        }

    def refresh_recommendations(self, recommendations: list[Recommendation]) -> list[Recommendation]:
        for item in recommendations:
            snapshot = self.quote(item.ticker)
            if not snapshot:
                continue
            daily_pct = round(snapshot.daily_return_pct, 2)
            direction = "up" if daily_pct >= 0 else "down"
            item.data_source = "yfinance-live"
            item.data_freshness_timestamp = _now_iso()
            item.source_links = [f"https://finance.yahoo.com/quote/{item.ticker}"]
            item.why_now = f"{item.ticker} is {direction} {abs(daily_pct)}% on latest daily close; monitored for advisory positioning."
            item.rationale = f"Live market feed refreshed recommendation context with daily move {daily_pct}% for {item.ticker}."
            base = 70.0 + max(-8.0, min(8.0, daily_pct))
            item.confidence_score = round(max(0.0, min(100.0, base)), 2)
            if item.status == RecommendationStatus.APPROVED:
                item.updated_at = _now_iso()
        return recommendations

    def refresh_tactical_signals(self, signals: list[TacticalSignal]) -> list[TacticalSignal]:
        for signal in signals:
            snapshot = self.quote(signal.ticker)
            if not snapshot:
                continue
            daily_pct = round(snapshot.daily_return_pct, 2)
            signal.status = "Watch" if abs(daily_pct) < 2 else "Setup"
            signal.entry_zone = f"{round(snapshot.close * 0.99, 2)}-{round(snapshot.close * 1.01, 2)}"
            signal.invalidation = f"Daily close below {round(snapshot.close * 0.96, 2)}"
            signal.target = str(round(snapshot.close * 1.06, 2))
        return signals

    def top_recommendations(self, limit: int = 50, sector: str | None = None) -> list[TopRecommendation]:
        clamped_limit = max(1, min(100, limit))
        rows: list[TopRecommendation] = []
        sector_filter = sector.strip() if sector else None

        if self._can_attempt():
            for ticker in TOP_RECOMMENDATION_UNIVERSE:
                try:
                    history = yf.Ticker(ticker).history(period="7d", interval="1d", auto_adjust=False, timeout=6)
                    if history is None or history.empty or len(history) < 3:
                        continue

                    close_latest = float(history["Close"].iloc[-1])
                    close_prev = float(history["Close"].iloc[-2])
                    close_week = float(history["Close"].iloc[-6]) if len(history) >= 6 else float(history["Close"].iloc[0])

                    volume_latest_raw = float(history["Volume"].iloc[-1])
                    volume_latest = 0.0 if math.isnan(volume_latest_raw) else volume_latest_raw
                    volume_avg = float(history["Volume"].tail(5).mean()) if len(history) >= 5 else float(history["Volume"].mean())

                    daily_pct = ((close_latest - close_prev) / close_prev) * 100 if close_prev else 0.0
                    weekly_pct = ((close_latest - close_week) / close_week) * 100 if close_week else 0.0
                    volume_ratio = (volume_latest / volume_avg) if volume_avg else 1.0

                    score = 50.0 + (daily_pct * 8.0) + (weekly_pct * 2.0) + ((volume_ratio - 1.0) * 5.0)
                    score = max(0.0, min(100.0, score))

                    rows.append(
                        TopRecommendation(
                            ticker=ticker,
                            sector=self.sector_for_ticker(ticker),
                            score=round(score, 2),
                            daily_pct=round(daily_pct, 2),
                            weekly_pct=round(weekly_pct, 2),
                            close=round(close_latest, 2),
                            volume_ratio=round(volume_ratio, 2),
                            recommended_action=_advisory_action(score, daily_pct, weekly_pct, volume_ratio),
                        )
                    )
                except Exception:
                    continue

        if not rows:
            fallback_tickers = [
                "MSFT", "NVDA", "AAPL", "PG", "KO", "COST", "TSLA", "XOM", "DE", "UBER",
                "ADBE", "CRM", "NOW", "PANW", "AVGO", "AMZN", "MCD", "WMT", "QCOM", "TXN",
            ]
            rows = [
                TopRecommendation(
                    ticker=ticker,
                    sector=self.sector_for_ticker(ticker),
                    score=round(55.0 - (index * 0.5), 2),
                    daily_pct=0.0,
                    weekly_pct=0.0,
                    close=0.0,
                    volume_ratio=1.0,
                    recommended_action="Advisory hold",
                )
                for index, ticker in enumerate(fallback_tickers)
            ]

        if sector_filter:
            rows = [item for item in rows if item.sector.lower() == sector_filter.lower()]

        rows.sort(key=lambda item: item.score, reverse=True)
        return rows[:clamped_limit]

    def _fallback_explainability_rows(self, tickers: list[str]) -> list[dict]:
        rows: list[dict] = []
        for index, ticker in enumerate(tickers):
            quality = max(20.0, 62.0 - index)
            value = max(20.0, 58.0 - (index * 0.8))
            momentum = max(15.0, 64.0 - (index * 1.2))
            financial_health = max(20.0, 60.0 - (index * 0.7))
            composite = round((quality * 0.3) + (value * 0.2) + (momentum * 0.3) + (financial_health * 0.2), 2)
            contributors = [
                {"factor": "quality.return_on_equity", "impact": 8.5, "detail": "Fallback synthetic signal"},
                {"factor": "momentum.weekly_return", "impact": 7.2, "detail": "Fallback synthetic signal"},
                {"factor": "financial_health.current_ratio", "impact": 4.4, "detail": "Fallback synthetic signal"},
                {"factor": "value.trailing_pe", "impact": 3.9, "detail": "Fallback synthetic signal"},
                {"factor": "momentum.volume_ratio", "impact": 2.1, "detail": "Fallback synthetic signal"},
            ]
            detractors = [
                {"factor": "value.price_to_book", "impact": -5.1, "detail": "Fallback synthetic signal"},
                {"factor": "momentum.daily_return", "impact": -3.8, "detail": "Fallback synthetic signal"},
                {"factor": "financial_health.debt_to_equity", "impact": -2.8, "detail": "Fallback synthetic signal"},
                {"factor": "quality.profit_margin", "impact": -1.6, "detail": "Fallback synthetic signal"},
                {"factor": "quality.gross_margin", "impact": -1.2, "detail": "Fallback synthetic signal"},
            ]

            rows.append(
                {
                    "ticker": ticker,
                    "sector": self.sector_for_ticker(ticker),
                    "quality": round(quality, 2),
                    "value": round(value, 2),
                    "momentum": round(momentum, 2),
                    "financial_health": round(financial_health, 2),
                    "composite": composite,
                    "recommended_action": _advisory_action(composite, 0.0, 0.0, 1.0),
                    "reason_for_ranking": "Fallback explainability model used due to unavailable live fundamentals.",
                    "top_positive_contributors": contributors,
                    "top_negative_contributors": detractors,
                    "sector_percentile": 50.0,
                    "universe_percentile": 50.0,
                    "missing_data_flags": [
                        "fundamentals.trailingPE",
                        "fundamentals.priceToBook",
                        "fundamentals.returnOnEquity",
                        "fundamentals.debtToEquity",
                        "fundamentals.currentRatio",
                        "fundamentals.quickRatio",
                    ],
                }
            )
        return rows

    def build_score_explainability(self, limit: int = 50, sector: str | None = None) -> dict:
        clamped_limit = max(1, min(100, limit))
        rows: list[dict] = []

        if self._can_attempt():
            for ticker in TOP_RECOMMENDATION_UNIVERSE:
                try:
                    history = yf.Ticker(ticker).history(period="6mo", interval="1d", auto_adjust=False, timeout=6)
                    info = yf.Ticker(ticker).info or {}
                    if history is None or history.empty or len(history) < 25:
                        continue

                    close_latest = _safe_float(history["Close"].iloc[-1]) or 0.0
                    close_prev = _safe_float(history["Close"].iloc[-2]) or close_latest
                    close_week = _safe_float(history["Close"].iloc[-6]) if len(history) >= 6 else close_prev
                    close_month = _safe_float(history["Close"].iloc[-22]) if len(history) >= 22 else close_prev
                    volume_latest = _safe_float(history["Volume"].iloc[-1]) or 0.0
                    volume_avg20 = _safe_float(history["Volume"].tail(20).mean()) or 1.0

                    daily_pct = ((close_latest - close_prev) / close_prev) * 100 if close_prev else 0.0
                    weekly_pct = ((close_latest - close_week) / close_week) * 100 if close_week else 0.0
                    monthly_pct = ((close_latest - close_month) / close_month) * 100 if close_month else 0.0
                    volume_ratio = (volume_latest / volume_avg20) if volume_avg20 else 1.0

                    roe = _safe_float(info.get("returnOnEquity"))
                    gross_margin = _safe_float(info.get("grossMargins"))
                    profit_margin = _safe_float(info.get("profitMargins"))
                    trailing_pe = _safe_float(info.get("trailingPE"))
                    price_to_book = _safe_float(info.get("priceToBook"))
                    debt_to_equity = _safe_float(info.get("debtToEquity"))
                    current_ratio = _safe_float(info.get("currentRatio"))
                    quick_ratio = _safe_float(info.get("quickRatio"))

                    missing_flags: list[str] = []
                    if roe is None:
                        missing_flags.append("fundamentals.returnOnEquity")
                    if gross_margin is None:
                        missing_flags.append("fundamentals.grossMargins")
                    if profit_margin is None:
                        missing_flags.append("fundamentals.profitMargins")
                    if trailing_pe is None:
                        missing_flags.append("fundamentals.trailingPE")
                    if price_to_book is None:
                        missing_flags.append("fundamentals.priceToBook")
                    if debt_to_equity is None:
                        missing_flags.append("fundamentals.debtToEquity")
                    if current_ratio is None:
                        missing_flags.append("fundamentals.currentRatio")
                    if quick_ratio is None:
                        missing_flags.append("fundamentals.quickRatio")

                    quality_components = {
                        "quality.return_on_equity": _metric_score(roe, -0.10, 0.35, higher_is_better=True),
                        "quality.gross_margin": _metric_score(gross_margin, 0.10, 0.70, higher_is_better=True),
                        "quality.profit_margin": _metric_score(profit_margin, 0.00, 0.30, higher_is_better=True),
                    }
                    value_components = {
                        "value.trailing_pe": _metric_score(trailing_pe, 8.0, 45.0, higher_is_better=False),
                        "value.price_to_book": _metric_score(price_to_book, 1.0, 12.0, higher_is_better=False),
                    }
                    momentum_components = {
                        "momentum.daily_return": _metric_score(daily_pct, -5.0, 5.0, higher_is_better=True),
                        "momentum.weekly_return": _metric_score(weekly_pct, -12.0, 12.0, higher_is_better=True),
                        "momentum.monthly_return": _metric_score(monthly_pct, -20.0, 20.0, higher_is_better=True),
                        "momentum.volume_ratio": _metric_score(volume_ratio, 0.5, 2.0, higher_is_better=True),
                    }
                    health_components = {
                        "financial_health.debt_to_equity": _metric_score(debt_to_equity, 20.0, 300.0, higher_is_better=False),
                        "financial_health.current_ratio": _metric_score(current_ratio, 0.8, 3.0, higher_is_better=True),
                        "financial_health.quick_ratio": _metric_score(quick_ratio, 0.5, 2.0, higher_is_better=True),
                    }

                    def _category_score(components: dict[str, float | None], fallback: str) -> float:
                        available = [value for value in components.values() if value is not None]
                        if not available:
                            missing_flags.append(f"{fallback}.all_components_missing")
                            return 50.0
                        return round(mean(available), 2)

                    quality = _category_score(quality_components, "quality")
                    value = _category_score(value_components, "value")
                    momentum = _category_score(momentum_components, "momentum")
                    financial_health = _category_score(health_components, "financial_health")

                    composite = round(
                        (quality * 0.30) +
                        (value * 0.20) +
                        (momentum * 0.30) +
                        (financial_health * 0.20),
                        2,
                    )

                    contributors: list[dict] = []
                    weighted_sets = [
                        (quality_components, 0.30),
                        (value_components, 0.20),
                        (momentum_components, 0.30),
                        (health_components, 0.20),
                    ]
                    for component_set, group_weight in weighted_sets:
                        available_count = len([v for v in component_set.values() if v is not None])
                        divisor = max(1, available_count)
                        for factor, score in component_set.items():
                            if score is None:
                                continue
                            impact = round(((score - 50.0) / 50.0) * group_weight * (100.0 / divisor), 2)
                            contributors.append(
                                {
                                    "factor": factor,
                                    "impact": impact,
                                    "detail": f"Normalized factor score {score}",
                                }
                            )

                    contributors.sort(key=lambda item: item["impact"], reverse=True)
                    positives = [item for item in contributors if item["impact"] > 0][:5]
                    negatives = sorted(
                        [item for item in contributors if item["impact"] < 0],
                        key=lambda item: item["impact"],
                    )[:5]

                    top_positive_names = ", ".join(item["factor"] for item in positives[:2]) or "balanced factors"
                    top_negative_names = ", ".join(item["factor"] for item in negatives[:1]) or "no major detractors"
                    reason_for_ranking = (
                        f"Composite {composite} driven by {top_positive_names}; "
                        f"main drag: {top_negative_names}."
                    )

                    rows.append(
                        {
                            "ticker": ticker,
                            "sector": self.sector_for_ticker(ticker),
                            "quality": quality,
                            "value": value,
                            "momentum": momentum,
                            "financial_health": financial_health,
                            "composite": composite,
                            "recommended_action": _advisory_action(composite, daily_pct, weekly_pct, volume_ratio),
                            "reason_for_ranking": reason_for_ranking,
                            "top_positive_contributors": positives,
                            "top_negative_contributors": negatives,
                            "sector_percentile": 50.0,
                            "universe_percentile": 50.0,
                            "missing_data_flags": missing_flags,
                        }
                    )
                except Exception:
                    continue

        if not rows:
            rows = self._fallback_explainability_rows(TOP_RECOMMENDATION_UNIVERSE[:clamped_limit])

        universe_values = [row["composite"] for row in rows]
        sector_groups: dict[str, list[float]] = {}
        for row in rows:
            sector_groups.setdefault(row["sector"], []).append(row["composite"])

        for row in rows:
            row["universe_percentile"] = _percentile(row["composite"], universe_values)
            row["sector_percentile"] = _percentile(row["composite"], sector_groups.get(row["sector"], []))

        if sector:
            rows = [row for row in rows if row["sector"].lower() == sector.strip().lower()]

        rows.sort(key=lambda item: item["composite"], reverse=True)
        return {
            "as_of": _now_iso(),
            "universe_size": len(rows),
            "items": rows[:clamped_limit],
        }


live_feeds = LiveFeedService()
