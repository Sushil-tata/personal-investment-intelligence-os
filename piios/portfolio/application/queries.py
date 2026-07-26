from __future__ import annotations

from dataclasses import dataclass

from piios.portfolio.domain.enums import ExposureBasis


@dataclass(frozen=True)
class TopHoldingsQuery:
    limit: int = 10
    basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE


@dataclass(frozen=True)
class PositionWeightsQuery:
    basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE
