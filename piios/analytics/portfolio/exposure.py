from __future__ import annotations

from decimal import Decimal

from piios.portfolio.application.dto import ExposureItemDTO
from piios.portfolio.application.services import PortfolioAnalyticsService
from piios.portfolio.domain.entities import DataQualityIssue, PortfolioSnapshot
from piios.portfolio.domain.enums import CountryMode, ExposureBasis


def by_country(
    snapshot: PortfolioSnapshot,
    fx_rates: dict[str, Decimal],
    mode: CountryMode = CountryMode.LISTING,
    basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE,
) -> tuple[list[ExposureItemDTO], list[DataQualityIssue]]:
    return PortfolioAnalyticsService().country_exposure(snapshot, fx_rates, mode, basis)


def by_currency(
    snapshot: PortfolioSnapshot,
    fx_rates: dict[str, Decimal],
    basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE,
) -> tuple[list[ExposureItemDTO], list[DataQualityIssue]]:
    return PortfolioAnalyticsService().currency_exposure(snapshot, fx_rates, basis)


def by_sector(
    snapshot: PortfolioSnapshot,
    fx_rates: dict[str, Decimal],
    basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE,
) -> tuple[list[ExposureItemDTO], list[DataQualityIssue]]:
    return PortfolioAnalyticsService().sector_exposure(snapshot, fx_rates, basis)


def by_industry(
    snapshot: PortfolioSnapshot,
    fx_rates: dict[str, Decimal],
    basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE,
) -> tuple[list[ExposureItemDTO], list[DataQualityIssue]]:
    return PortfolioAnalyticsService().industry_exposure(snapshot, fx_rates, basis)


def by_theme(
    snapshot: PortfolioSnapshot,
    fx_rates: dict[str, Decimal],
    basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE,
) -> tuple[list[ExposureItemDTO], list[DataQualityIssue]]:
    return PortfolioAnalyticsService().theme_exposure(snapshot, fx_rates, basis)
