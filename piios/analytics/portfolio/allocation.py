from __future__ import annotations

from decimal import Decimal

from piios.portfolio.application.services import PortfolioAnalyticsService
from piios.portfolio.domain.entities import DataQualityIssue, PortfolioSnapshot
from piios.portfolio.domain.enums import ExposureBasis


def value_by_account(
    snapshot: PortfolioSnapshot,
    fx_rates: dict[str, Decimal],
    basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE,
) -> tuple[dict[str, Decimal], list[DataQualityIssue]]:
    return PortfolioAnalyticsService().value_by_account(snapshot, fx_rates, basis)


def value_by_bucket(
    snapshot: PortfolioSnapshot,
    fx_rates: dict[str, Decimal],
    basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE,
) -> tuple[dict[str, Decimal], list[DataQualityIssue]]:
    return PortfolioAnalyticsService().value_by_bucket(snapshot, fx_rates, basis)


def asset_class_exposure(
    snapshot: PortfolioSnapshot,
    fx_rates: dict[str, Decimal],
    basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE,
):
    return PortfolioAnalyticsService().asset_class_exposure(snapshot, fx_rates, basis)
