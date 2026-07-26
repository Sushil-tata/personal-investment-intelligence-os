from __future__ import annotations

from decimal import Decimal

from piios.portfolio.application.services import PortfolioAnalyticsService
from piios.portfolio.domain.entities import PortfolioSnapshot, ProposedTradeImpact
from piios.portfolio.domain.value_objects import Money


def proposed_purchase_impact(
    snapshot: PortfolioSnapshot,
    fx_rates: dict[str, Decimal],
    amount: Money,
    proposed_country: str,
    proposed_sector: str | None,
    proposed_theme: str | None,
    proposed_ticker: str,
) -> ProposedTradeImpact:
    return PortfolioAnalyticsService().proposed_purchase_impact(
        snapshot=snapshot,
        fx_rates=fx_rates,
        command_amount=amount,
        proposed_country=proposed_country,
        proposed_sector=proposed_sector,
        proposed_theme=proposed_theme,
        proposed_ticker=proposed_ticker,
    )
