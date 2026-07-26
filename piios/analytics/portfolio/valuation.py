from __future__ import annotations

from decimal import Decimal

from piios.portfolio.application.services import PortfolioAnalyticsService
from piios.portfolio.domain.entities import DataQualityIssue, PortfolioSnapshot
from piios.portfolio.domain.enums import ExposureBasis


def total_value(
    snapshot: PortfolioSnapshot,
    fx_rates: dict[str, Decimal],
    basis: ExposureBasis = ExposureBasis.TOTAL_NET_WORTH,
) -> tuple[Decimal, list[DataQualityIssue]]:
    return PortfolioAnalyticsService().total_portfolio_value(snapshot, fx_rates, basis)


def cash_percentage(snapshot: PortfolioSnapshot, fx_rates: dict[str, Decimal]) -> tuple[Decimal, list[DataQualityIssue]]:
    return PortfolioAnalyticsService().cash_percentage(snapshot, fx_rates)


def listed_equity_percentage(snapshot: PortfolioSnapshot, fx_rates: dict[str, Decimal]) -> tuple[Decimal, list[DataQualityIssue]]:
    return PortfolioAnalyticsService().listed_equity_percentage(snapshot, fx_rates)
