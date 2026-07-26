from __future__ import annotations

from sqlmodel import Session, select

from piios_backend.models.entities import (
    DataTrustSourceEntity,
    FamilyPortfolioMemberEntity,
    IPSConstraintEntity,
    InstrumentMasterEntity,
)


class PortfolioLayersRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_family_members(self) -> list[FamilyPortfolioMemberEntity]:
        return list(self.session.exec(select(FamilyPortfolioMemberEntity).order_by(FamilyPortfolioMemberEntity.member_id)).all())

    def list_ips_constraints(self) -> list[IPSConstraintEntity]:
        return list(self.session.exec(select(IPSConstraintEntity).order_by(IPSConstraintEntity.constraint_id)).all())

    def list_instruments(self) -> list[InstrumentMasterEntity]:
        return list(self.session.exec(select(InstrumentMasterEntity).order_by(InstrumentMasterEntity.ticker)).all())

    def list_data_trust_sources(self) -> list[DataTrustSourceEntity]:
        return list(self.session.exec(select(DataTrustSourceEntity).order_by(DataTrustSourceEntity.score.desc())).all())

    def seed_defaults(self) -> None:
        if not self.list_family_members():
            self.session.add(
                FamilyPortfolioMemberEntity(
                    member_id="fm1",
                    member_name="Primary Investor",
                    relation="Self",
                    base_currency="INR",
                )
            )

        if not self.list_ips_constraints():
            self.session.add(
                IPSConstraintEntity(
                    constraint_id="ips1",
                    name="Single Ticker Cap",
                    rule_type="max_position_pct",
                    threshold_value=10.0,
                    severity="HIGH",
                    enabled=True,
                )
            )

        if not self.list_instruments():
            self.session.add(
                InstrumentMasterEntity(
                    instrument_id="ins1",
                    ticker="VTI",
                    name="Vanguard Total Stock Market ETF",
                    asset_class="ETF",
                    currency="USD",
                    exchange="NYSE Arca",
                    data_source="yfinance",
                )
            )

        if not self.list_data_trust_sources():
            self.session.add(
                DataTrustSourceEntity(
                    source_id="src1",
                    source_name="Exchange Feed",
                    trust_tier="Tier-1",
                    score=95.0,
                    freshness_sla_hours=1,
                )
            )

        self.session.commit()
