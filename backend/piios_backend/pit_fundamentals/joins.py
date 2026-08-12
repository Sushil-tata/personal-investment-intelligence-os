from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import median

from .models import AvailabilityMode, FundamentalObservation, VersionStatus


VERSION_PRIORITY = {
    VersionStatus.ORIGINAL.value: 1,
    VersionStatus.AMENDED.value: 2,
    VersionStatus.RESTATED.value: 3,
    VersionStatus.UNKNOWN_VERSION.value: 0,
}


def _is_strictly_eligible(observation: FundamentalObservation, strict: bool) -> bool:
    if observation.availability_date is None:
        return False
    if strict and observation.availability_mode == AvailabilityMode.UNKNOWN:
        return False
    return True


def latest_observation(
    observations: list[FundamentalObservation],
    ticker: str,
    metric_name: str,
    ranking_date: date,
    *,
    strict: bool = True,
) -> FundamentalObservation | None:
    candidates = [
        obs
        for obs in observations
        if obs.ticker_at_time == ticker
        and obs.metric_name == metric_name
        and _is_strictly_eligible(obs, strict)
        and obs.availability_date is not None
        and obs.availability_date <= ranking_date
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda obs: (
            obs.availability_date,
            obs.fiscal_period_end,
            VERSION_PRIORITY.get(obs.restatement_flag.value, 0),
            obs.version_id,
        ),
        reverse=True,
    )
    return candidates[0]


def get_fundamental_snapshot(
    observations: list[FundamentalObservation],
    ticker: str,
    ranking_date: date,
    *,
    strict: bool = True,
) -> dict[str, FundamentalObservation]:
    metric_names = sorted({obs.metric_name for obs in observations if obs.ticker_at_time == ticker})
    out: dict[str, FundamentalObservation] = {}
    for metric in metric_names:
        latest = latest_observation(observations, ticker, metric, ranking_date, strict=strict)
        if latest is not None:
            out[metric] = latest
    return out


def derive_metrics(
    observations: list[FundamentalObservation],
    ticker: str,
    ranking_date: date,
    *,
    strict: bool = True,
) -> dict[str, float]:
    snapshot = get_fundamental_snapshot(observations, ticker, ranking_date, strict=strict)

    out: dict[str, float] = {}
    revenue = snapshot.get("revenue")
    net_income = snapshot.get("net_income")
    operating_income = snapshot.get("operating_income")
    book_equity = snapshot.get("book_equity")
    total_assets = snapshot.get("total_assets")
    total_debt = snapshot.get("total_debt")
    ocf = snapshot.get("operating_cash_flow")
    fcf = snapshot.get("free_cash_flow")

    if revenue and operating_income and revenue.metric_value != 0:
        out["operating_margin"] = operating_income.metric_value / revenue.metric_value
    if revenue and net_income and revenue.metric_value != 0:
        out["profit_margin"] = net_income.metric_value / revenue.metric_value
    if net_income and book_equity and book_equity.metric_value != 0:
        out["roe"] = net_income.metric_value / book_equity.metric_value
    if net_income and total_assets and total_assets.metric_value != 0:
        out["roa"] = net_income.metric_value / total_assets.metric_value
    if total_debt and book_equity and book_equity.metric_value != 0:
        out["debt_equity"] = total_debt.metric_value / book_equity.metric_value
    if ocf:
        out["operating_cash_flow"] = ocf.metric_value
    if fcf:
        out["free_cash_flow"] = fcf.metric_value

    out.update(_derive_yoy_growth(observations, ticker, ranking_date, strict=strict))
    return out


def _derive_yoy_growth(
    observations: list[FundamentalObservation],
    ticker: str,
    ranking_date: date,
    *,
    strict: bool,
) -> dict[str, float]:
    out: dict[str, float] = {}
    for metric_name, out_name in [
        ("revenue", "revenue_growth_yoy"),
        ("net_income", "earnings_growth_yoy"),
        ("eps_diluted", "eps_growth_yoy"),
    ]:
        series = [
            obs
            for obs in observations
            if obs.ticker_at_time == ticker
            and obs.metric_name == metric_name
            and obs.fiscal_period_type == "FY"
            and _is_strictly_eligible(obs, strict)
            and obs.availability_date is not None
            and obs.availability_date <= ranking_date
        ]
        if len(series) < 2:
            continue
        series.sort(key=lambda obs: (obs.fiscal_period_end, obs.availability_date or date.min), reverse=True)
        current = series[0].metric_value
        previous = series[1].metric_value
        if previous != 0:
            out[out_name] = (current / previous) - 1.0
    return out


def valuation_snapshot(
    observations: list[FundamentalObservation],
    ticker: str,
    ranking_date: date,
    price_at_t: float | None,
    *,
    strict: bool = True,
) -> dict[str, float]:
    snapshot = get_fundamental_snapshot(observations, ticker, ranking_date, strict=strict)
    out: dict[str, float] = {}
    shares = snapshot.get("shares_outstanding")
    eps = snapshot.get("eps_diluted") or snapshot.get("eps_basic")
    book = snapshot.get("book_equity")
    debt = snapshot.get("total_debt")
    cash = snapshot.get("cash_and_equivalents")
    operating_income = snapshot.get("operating_income")
    fcf = snapshot.get("free_cash_flow")

    if price_at_t is not None and eps and eps.metric_value != 0:
        out["pe"] = price_at_t / eps.metric_value

    if price_at_t is not None and shares and book and shares.metric_value != 0 and book.metric_value != 0:
        market_cap = price_at_t * shares.metric_value
        out["pb"] = market_cap / book.metric_value

    if price_at_t is not None and shares and debt and cash and operating_income and operating_income.metric_value != 0:
        market_cap = price_at_t * shares.metric_value
        enterprise_value = market_cap + debt.metric_value - cash.metric_value
        out["ev_ebitda_proxy"] = enterprise_value / operating_income.metric_value

    if price_at_t is not None and shares and fcf and shares.metric_value != 0:
        market_cap = price_at_t * shares.metric_value
        if market_cap != 0:
            out["fcf_yield"] = fcf.metric_value / market_cap

    return out
