from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from piios.identity.application.commands import (
    AddIdentifierCommand,
    AddTickerHistoryCommand,
    CreateCompanyCommand,
    CreateListingCommand,
    CreateRelationshipCommand,
    CreateSecurityCommand,
)
from piios.identity.application.resolution import IdentityResolutionService
from piios.identity.application.services import IdentityApplicationService
from piios.identity.domain.enums import EntityScope, IdentifierType, RelationshipType, SecurityType
from piios.identity.domain.exceptions import (
    DuplicateActiveIdentifierError,
    EffectiveDateRangeError,
    HardDeleteProhibitedError,
    InvalidRelationshipError,
    OverlappingTickerHistoryError,
)
from piios.identity.infrastructure.in_memory_repositories import (
    InMemoryCompanyRepository,
    InMemoryIdentifierRepository,
    InMemoryIdentityResolutionIssueRepository,
    InMemoryIdentityResolutionQueryService,
    InMemoryLegacyIdentityMappingRepository,
    InMemoryListingRepository,
    InMemorySecurityRelationshipRepository,
    InMemorySecurityRepository,
    InMemoryTickerHistoryRepository,
)


def _service() -> IdentityApplicationService:
    company_repo = InMemoryCompanyRepository()
    security_repo = InMemorySecurityRepository()
    listing_repo = InMemoryListingRepository()
    identifier_repo = InMemoryIdentifierRepository()
    ticker_history_repo = InMemoryTickerHistoryRepository()
    relationship_repo = InMemorySecurityRelationshipRepository()
    legacy_repo = InMemoryLegacyIdentityMappingRepository()
    issue_repo = InMemoryIdentityResolutionIssueRepository()
    query_repo = InMemoryIdentityResolutionQueryService(company_repo, security_repo, listing_repo, identifier_repo, legacy_repo)
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


def _seed_company_security_listing(service: IdentityApplicationService) -> None:
    service.create_company(
        CreateCompanyCommand(
            company_id="co_india_1",
            legal_name="Infosys Limited",
            common_name="Infosys",
            company_type="CORPORATE",
            jurisdiction_of_incorporation="IN",
            primary_economic_country="IN",
            sector="Information Technology",
            industry="IT Services",
            active_from=date(1993, 1, 1),
            active_to=None,
        )
    )
    service.create_security(
        CreateSecurityCommand(
            security_id="sec_infy_eq",
            issuer_company_id="co_india_1",
            issuer_name=None,
            security_type=SecurityType.ORDINARY_EQUITY,
            security_name="Infosys Ordinary Share",
            issue_currency="INR",
            issue_date=None,
            maturity_date=None,
            share_class_or_seniority=None,
            economic_exposure_type="EQUITY",
            active_from=date(1993, 1, 1),
            active_to=None,
        )
    )
    service.create_listing(
        CreateListingCommand(
            listing_id="list_infy_nse",
            security_id="sec_infy_eq",
            exchange_code="NSE",
            ticker="INFY",
            trading_currency="INR",
            listing_country="IN",
            is_primary_listing=True,
            lot_size=Decimal("1"),
            price_source_symbol="INFY.NS",
            active_from=date(1999, 1, 1),
            active_to=None,
        )
    )


def test_valid_company_creation() -> None:
    service = _service()
    company = service.create_company(
        CreateCompanyCommand(
            company_id="co_us_1",
            legal_name="Acme Holdings Inc",
            common_name="Acme",
            company_type="CORPORATE",
            jurisdiction_of_incorporation="US",
            primary_economic_country="US",
            sector="Industrials",
            industry="Machinery",
            active_from=date(2000, 1, 1),
            active_to=None,
        )
    )
    assert company.company_id.value == "co_us_1"


def test_invalid_effective_date_ranges() -> None:
    service = _service()
    with pytest.raises(EffectiveDateRangeError):
        service.create_company(
            CreateCompanyCommand(
                company_id="co_invalid",
                legal_name="Invalid Corp",
                common_name=None,
                company_type="CORPORATE",
                jurisdiction_of_incorporation="US",
                primary_economic_country="US",
                sector=None,
                industry=None,
                active_from=date(2026, 7, 1),
                active_to=date(2026, 6, 1),
            )
        )


def test_security_without_company_is_allowed() -> None:
    service = _service()
    security = service.create_security(
        CreateSecurityCommand(
            security_id="sec_sg_fund",
            issuer_company_id=None,
            issuer_name="Sovereign Fund Authority",
            security_type=SecurityType.FUND_UNIT,
            security_name="Sovereign Growth Fund Unit",
            issue_currency="SGD",
            issue_date=None,
            maturity_date=None,
            share_class_or_seniority=None,
            economic_exposure_type="FUND",
            active_from=date(2010, 1, 1),
            active_to=None,
        )
    )
    assert security.issuer_company_id is None


def test_listing_with_invalid_currency_fails() -> None:
    service = _service()
    _seed_company_security_listing(service)
    with pytest.raises(ValueError):
        service.create_listing(
            CreateListingCommand(
                listing_id="list_bad_ccy",
                security_id="sec_infy_eq",
                exchange_code="BSE",
                ticker="INFY",
                trading_currency="IN",  # invalid
                listing_country="IN",
                is_primary_listing=False,
                lot_size=Decimal("1"),
                price_source_symbol=None,
                active_from=date(2000, 1, 1),
                active_to=None,
            )
        )


def test_duplicate_active_listing_primary_fails() -> None:
    service = _service()
    _seed_company_security_listing(service)
    with pytest.raises(InvalidRelationshipError):
        service.create_listing(
            CreateListingCommand(
                listing_id="list_infy_bse",
                security_id="sec_infy_eq",
                exchange_code="BSE",
                ticker="INFY",
                trading_currency="INR",
                listing_country="IN",
                is_primary_listing=True,
                lot_size=Decimal("1"),
                price_source_symbol="INFY.BO",
                active_from=date(2001, 1, 1),
                active_to=None,
            )
        )


def test_overlapping_ticker_history_fails() -> None:
    service = _service()
    _seed_company_security_listing(service)
    service.add_ticker_history(
        AddTickerHistoryCommand(
            ticker_history_id="th1",
            listing_id="list_infy_nse",
            exchange_code="NSE",
            ticker="INFY",
            active_from=date(2000, 1, 1),
            active_to=date(2010, 1, 1),
            change_reason="initial",
            source="fixture",
        )
    )
    with pytest.raises(OverlappingTickerHistoryError):
        service.add_ticker_history(
            AddTickerHistoryCommand(
                ticker_history_id="th2",
                listing_id="list_infy_nse",
                exchange_code="NSE",
                ticker="INFY",
                active_from=date(2005, 1, 1),
                active_to=date(2015, 1, 1),
                change_reason="overlap",
                source="fixture",
            )
        )


def test_duplicate_active_identifier_fails() -> None:
    service = _service()
    _seed_company_security_listing(service)
    service.add_identifier(
        AddIdentifierCommand(
            identifier_id="id1",
            scope=EntityScope.SECURITY,
            entity_id="sec_infy_eq",
            identifier_type=IdentifierType.ISIN,
            identifier_value="INE009A01021",
            provider_or_authority="NSDL",
            active_from=date(2000, 1, 1),
            active_to=None,
            source="fixture",
        )
    )
    with pytest.raises(DuplicateActiveIdentifierError):
        service.add_identifier(
            AddIdentifierCommand(
                identifier_id="id2",
                scope=EntityScope.SECURITY,
                entity_id="sec_infy_eq",
                identifier_type=IdentifierType.ISIN,
                identifier_value="INE009A01021",
                provider_or_authority="NSDL",
                active_from=date(2001, 1, 1),
                active_to=None,
                source="fixture",
            )
        )


def test_invalid_relationship_self_fails() -> None:
    service = _service()
    _seed_company_security_listing(service)
    with pytest.raises(InvalidRelationshipError):
        service.create_relationship(
            CreateRelationshipCommand(
                relationship_id="rel_self",
                source_scope=EntityScope.SECURITY,
                source_entity_id="sec_infy_eq",
                target_scope=EntityScope.SECURITY,
                target_entity_id="sec_infy_eq",
                relationship_type=RelationshipType.SHARE_CLASS_SIBLING,
                conversion_ratio=None,
                active_from=date(2020, 1, 1),
                active_to=None,
                source="fixture",
            )
        )


def test_prohibited_hard_delete_path() -> None:
    service = _service()
    with pytest.raises(HardDeleteProhibitedError):
        service.hard_delete_identity("company", "co_us_1")
