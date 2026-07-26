from __future__ import annotations

from dataclasses import dataclass

from piios.portfolio.domain.entities import ProposedAllocation
from piios.portfolio.domain.enums import CountryMode, ExposureBasis


@dataclass(frozen=True)
class ComputeExposureCommand:
    dimension: str
    basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE
    country_mode: CountryMode = CountryMode.LISTING


@dataclass(frozen=True)
class ProposedPurchaseImpactCommand:
    allocation: ProposedAllocation
