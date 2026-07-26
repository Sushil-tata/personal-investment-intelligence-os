from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine

from piios.identity.application.commands import AddTickerHistoryCommand, CreateCompanyCommand, CreateListingCommand, CreateSecurityCommand
from piios.identity.application.resolution import IdentityResolutionService
from piios.identity.application.services import IdentityApplicationService
from piios.identity.domain.enums import SecurityType
from piios.identity.infrastructure.sqlmodel_repositories import (
    SQLModelCompanyRepository,
    SQLModelIdentifierRepository,
    SQLModelIdentityResolutionIssueRepository,
    SQLModelIdentityResolutionQueryService,
    SQLModelLegacyIdentityMappingRepository,
    SQLModelListingRepository,
    SQLModelSecurityRelationshipRepository,
    SQLModelSecurityRepository,
    SQLModelTickerHistoryRepository,
)
from piios_backend.models import entities  # noqa: F401


def _service(session: Session) -> IdentityApplicationService:
    company_repo = SQLModelCompanyRepository(session)
    security_repo = SQLModelSecurityRepository(session)
    listing_repo = SQLModelListingRepository(session)
    identifier_repo = SQLModelIdentifierRepository(session)
    ticker_history_repo = SQLModelTickerHistoryRepository(session)
    relationship_repo = SQLModelSecurityRelationshipRepository(session)
    legacy_repo = SQLModelLegacyIdentityMappingRepository(session)
    issue_repo = SQLModelIdentityResolutionIssueRepository(session)
    query_repo = SQLModelIdentityResolutionQueryService(company_repo, security_repo, listing_repo, identifier_repo, legacy_repo)
    return IdentityApplicationService(
        company_repo=company_repo,
        security_repo=security_repo,
        listing_repo=listing_repo,
        identifier_repo=identifier_repo,
        ticker_history_repo=ticker_history_repo,
        relationship_repo=relationship_repo,
        legacy_mapping_repo=legacy_repo,
        issue_repo=issue_repo,
        resolution_service=IdentityResolutionService(query_repo),
    )


def test_sqlmodel_repository_create_and_retrieve() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        service = _service(session)
        service.create_company(
            CreateCompanyCommand(
                company_id="co_us_msft",
                legal_name="Microsoft Corporation",
                common_name="Microsoft",
                company_type="CORPORATE",
                jurisdiction_of_incorporation="US",
                primary_economic_country="US",
                sector="Technology",
                industry="Software",
                active_from=date(1975, 1, 1),
                active_to=None,
            )
        )
        service.create_security(
            CreateSecurityCommand(
                security_id="sec_msft_common",
                issuer_company_id="co_us_msft",
                issuer_name=None,
                security_type=SecurityType.ORDINARY_EQUITY,
                security_name="Microsoft Common Stock",
                issue_currency="USD",
                issue_date=None,
                maturity_date=None,
                share_class_or_seniority=None,
                economic_exposure_type="EQUITY",
                active_from=date(1986, 3, 13),
                active_to=None,
            )
        )
        service.create_listing(
            CreateListingCommand(
                listing_id="list_msft_nasdaq",
                security_id="sec_msft_common",
                exchange_code="NASDAQ",
                ticker="MSFT",
                trading_currency="USD",
                listing_country="US",
                is_primary_listing=True,
                lot_size=Decimal("1"),
                price_source_symbol="MSFT",
                active_from=date(1986, 3, 13),
                active_to=None,
            )
        )

        listing = service._listing_repo.get_active_by_exchange_ticker("NASDAQ", "MSFT", date(2026, 7, 26))
        assert listing is not None
        assert listing.listing_id.value == "list_msft_nasdaq"


def test_effective_date_and_historical_retrieval() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        service = _service(session)
        service.create_company(
            CreateCompanyCommand(
                company_id="co_sg_dbs",
                legal_name="DBS Group Holdings Ltd",
                common_name="DBS",
                company_type="CORPORATE",
                jurisdiction_of_incorporation="SG",
                primary_economic_country="SG",
                sector="Financials",
                industry="Banks",
                active_from=date(1990, 1, 1),
                active_to=None,
            )
        )
        service.create_security(
            CreateSecurityCommand(
                security_id="sec_dbs_common",
                issuer_company_id="co_sg_dbs",
                issuer_name=None,
                security_type=SecurityType.ORDINARY_EQUITY,
                security_name="DBS Common",
                issue_currency="SGD",
                issue_date=None,
                maturity_date=None,
                share_class_or_seniority=None,
                economic_exposure_type="EQUITY",
                active_from=date(1990, 1, 1),
                active_to=None,
            )
        )
        service.create_listing(
            CreateListingCommand(
                listing_id="list_dbs_sgx",
                security_id="sec_dbs_common",
                exchange_code="SGX",
                ticker="D05",
                trading_currency="SGD",
                listing_country="SG",
                is_primary_listing=True,
                lot_size=Decimal("1"),
                price_source_symbol="D05.SI",
                active_from=date(2000, 1, 1),
                active_to=date(2025, 12, 31),
            )
        )
        service.add_ticker_history(
            AddTickerHistoryCommand(
                ticker_history_id="th_dbs_1",
                listing_id="list_dbs_sgx",
                exchange_code="SGX",
                ticker="D05",
                active_from=date(2000, 1, 1),
                active_to=date(2025, 12, 31),
                change_reason="legacy",
                source="fixture",
            )
        )
        active_listing = service._listing_repo.get_active_by_exchange_ticker("SGX", "D05", date(2026, 1, 1))
        assert active_listing is None
        historical_listing = service._listing_repo.get_historical_by_exchange_ticker("SGX", "D05", date(2024, 1, 1))
        assert historical_listing is not None


def test_uniqueness_and_transaction_rollback() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        service = _service(session)
        service.create_company(
            CreateCompanyCommand(
                company_id="co_hk_700",
                legal_name="Tencent Holdings Limited",
                common_name="Tencent",
                company_type="CORPORATE",
                jurisdiction_of_incorporation="HK",
                primary_economic_country="CN",
                sector="Communication Services",
                industry="Internet",
                active_from=date(1998, 1, 1),
                active_to=None,
            )
        )
        with pytest.raises(IntegrityError):
            service._company_repo.create(
                service._company_repo.get_by_id("co_hk_700")  # duplicate company_id through raw repo create
            )
        session.rollback()
        assert service._company_repo.get_by_id("co_hk_700") is not None
