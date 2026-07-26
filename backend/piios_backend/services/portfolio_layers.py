from __future__ import annotations

from collections import defaultdict

from sqlmodel import Session

from piios_backend.repositories.portfolio_layers import PortfolioLayersRepository
from piios_backend.schemas.portfolio_layers import (
    AllocationItem,
    AllocationResponse,
    CurrencyExposureItem,
    CurrencyExposureResponse,
    DataTrustHierarchyResponse,
    DataTrustSourceItem,
    FamilyPortfolioMember,
    FamilyPortfolioResponse,
    IPSConstraint,
    IPSConstraintResponse,
    InstrumentMasterItem,
    InstrumentMasterResponse,
    NetWorthItem,
    NetWorthResponse,
)
from piios_backend.services.in_memory_store import store


class PortfolioLayersService:
    def __init__(self, session: Session) -> None:
        self.repo = PortfolioLayersRepository(session)

    def seed_defaults(self) -> None:
        self.repo.seed_defaults()

    def family_registry(self) -> FamilyPortfolioResponse:
        members = [
            FamilyPortfolioMember(
                member_id=row.member_id,
                member_name=row.member_name,
                relation=row.relation,
                base_currency=row.base_currency,
            )
            for row in self.repo.list_family_members()
        ]
        return FamilyPortfolioResponse(households=members)

    def ips_constraints(self) -> IPSConstraintResponse:
        constraints = [
            IPSConstraint(
                constraint_id=row.constraint_id,
                name=row.name,
                rule_type=row.rule_type,
                threshold_value=row.threshold_value,
                severity=row.severity,
                enabled=row.enabled,
            )
            for row in self.repo.list_ips_constraints()
        ]
        return IPSConstraintResponse(constraints=constraints)

    def instrument_master(self) -> InstrumentMasterResponse:
        instruments = [
            InstrumentMasterItem(
                instrument_id=row.instrument_id,
                ticker=row.ticker,
                name=row.name,
                asset_class=row.asset_class,
                currency=row.currency,
                exchange=row.exchange,
                data_source=row.data_source,
            )
            for row in self.repo.list_instruments()
        ]
        return InstrumentMasterResponse(instruments=instruments)

    def data_trust_hierarchy(self) -> DataTrustHierarchyResponse:
        hierarchy = [
            DataTrustSourceItem(
                source_id=row.source_id,
                source_name=row.source_name,
                trust_tier=row.trust_tier,
                score=row.score,
                freshness_sla_hours=row.freshness_sla_hours,
            )
            for row in self.repo.list_data_trust_sources()
        ]
        return DataTrustHierarchyResponse(hierarchy=hierarchy)

    def net_worth(self) -> NetWorthResponse:
        total_assets = sum(h.market_value for h in store.holdings)
        total_liabilities = 0.0
        breakdown = [
            NetWorthItem(category="Investments", value=total_assets),
            NetWorthItem(category="Liabilities", value=total_liabilities),
        ]
        return NetWorthResponse(
            owner="Family Portfolio",
            total_assets=round(total_assets, 2),
            total_liabilities=round(total_liabilities, 2),
            net_worth=round(total_assets - total_liabilities, 2),
            breakdown=breakdown,
        )

    def allocation(self, dimension: str = "asset_class") -> AllocationResponse:
        total_value = sum(h.market_value for h in store.holdings) or 1.0
        valid_dimensions = {"asset_class", "sector", "theme", "bucket", "geography"}
        dim = dimension if dimension in valid_dimensions else "asset_class"

        grouped: dict[str, float] = defaultdict(float)
        for holding in store.holdings:
            if dim == "bucket":
                key = holding.bucket.value if holding.bucket else "Unknown"
            else:
                key = getattr(holding, dim)
            grouped[key] += holding.market_value

        items = [
            AllocationItem(
                dimension=dim,
                key=key,
                market_value=round(value, 2),
                percentage=round((value / total_value) * 100, 2),
            )
            for key, value in grouped.items()
        ]
        items.sort(key=lambda item: item.market_value, reverse=True)
        return AllocationResponse(total_value=round(total_value, 2), items=items)

    def currency_exposure(self) -> CurrencyExposureResponse:
        total_value = sum(h.market_value for h in store.holdings) or 1.0
        grouped: dict[str, float] = defaultdict(float)
        for holding in store.holdings:
            grouped[holding.currency] += holding.market_value

        items = [
            CurrencyExposureItem(
                currency=currency,
                market_value=round(value, 2),
                percentage=round((value / total_value) * 100, 2),
            )
            for currency, value in grouped.items()
        ]
        items.sort(key=lambda item: item.market_value, reverse=True)
        return CurrencyExposureResponse(total_value=round(total_value, 2), items=items)
