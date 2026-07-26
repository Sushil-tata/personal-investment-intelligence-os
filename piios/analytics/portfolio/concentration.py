from __future__ import annotations

from decimal import Decimal

from piios.portfolio.application.dto import ConcentrationMetricsDTO, ExposureItemDTO
from piios.portfolio.application.services import PortfolioAnalyticsService
from piios.portfolio.domain.entities import DataQualityIssue, PortfolioSnapshot
from piios.portfolio.domain.enums import ExposureBasis


def top_holdings(
    snapshot: PortfolioSnapshot,
    fx_rates: dict[str, Decimal],
    limit: int = 10,
    basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE,
) -> tuple[list[ExposureItemDTO], list[DataQualityIssue]]:
    return PortfolioAnalyticsService().top_holdings(snapshot, fx_rates, limit, basis)


def position_weights(
    snapshot: PortfolioSnapshot,
    fx_rates: dict[str, Decimal],
    basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE,
) -> tuple[dict[str, Decimal], list[DataQualityIssue]]:
    return PortfolioAnalyticsService().position_weights(snapshot, fx_rates, basis)


def hhi_metrics(
    snapshot: PortfolioSnapshot,
    fx_rates: dict[str, Decimal],
    basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE,
) -> tuple[ConcentrationMetricsDTO, list[DataQualityIssue]]:
    return PortfolioAnalyticsService().concentration_metrics(snapshot, fx_rates, basis)
