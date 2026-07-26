from __future__ import annotations

from datetime import date
from decimal import Decimal

from piios.identity.application.commands import AddIdentifierCommand, CreateCompanyCommand, CreateListingCommand, CreateSecurityCommand, LinkLegacyIdentityCommand
from piios.identity.application.queries import ResolveIdentityQuery
from piios.identity.application.resolution import IdentityResolutionService
from piios.identity.application.services import IdentityApplicationService
from piios.identity.domain.enums import EntityScope, IdentifierType, ResolutionStatus, SecurityType
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


def _seed(service: IdentityApplicationService) -> None:
    service.create_company(
        CreateCompanyCommand(
            company_id="co_hk_1",
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
    service.create_security(
        CreateSecurityCommand(
            security_id="sec_tencent_ord",
            issuer_company_id="co_hk_1",
            issuer_name=None,
            security_type=SecurityType.ORDINARY_EQUITY,
            security_name="Tencent Ordinary Shares",
            issue_currency="HKD",
            issue_date=None,
            maturity_date=None,
            share_class_or_seniority=None,
            economic_exposure_type="EQUITY",
            active_from=date(2004, 1, 1),
            active_to=None,
        )
    )
    service.create_listing(
        CreateListingCommand(
            listing_id="list_0700_hkex",
            security_id="sec_tencent_ord",
            exchange_code="HKEX",
            ticker="0700",
            trading_currency="HKD",
            listing_country="HK",
            is_primary_listing=True,
            lot_size=Decimal("100"),
            price_source_symbol="0700.HK",
            active_from=date(2004, 1, 1),
            active_to=None,
        )
    )
    service.add_identifier(
        AddIdentifierCommand(
            identifier_id="id_tencent_isin",
            scope=EntityScope.SECURITY,
            entity_id="sec_tencent_ord",
            identifier_type=IdentifierType.ISIN,
            identifier_value="KYG875721634",
            provider_or_authority="HKEX",
            active_from=date(2004, 1, 1),
            active_to=None,
            source="fixture",
        )
    )
    service.add_identifier(
        AddIdentifierCommand(
            identifier_id="id_tencent_provider",
            scope=EntityScope.LISTING,
            entity_id="list_0700_hkex",
            identifier_type=IdentifierType.PROVIDER_INTERNAL,
            identifier_value="bbg:HK.0700",
            provider_or_authority="BLOOMBERG",
            active_from=date(2004, 1, 1),
            active_to=None,
            source="fixture",
        )
    )
    service.link_legacy_identity(
        LinkLegacyIdentityCommand(
            mapping_id="map_legacy_tencent",
            legacy_source="legacy",
            legacy_record_id="h_tencent",
            legacy_asset_id="h_tencent",
            legacy_instrument_id=None,
            legacy_ticker="0700",
            company_id="co_hk_1",
            security_id="sec_tencent_ord",
            listing_id="list_0700_hkex",
            resolution_status="RESOLVED",
            provenance="fixture",
        )
    )


def test_internal_id_exact_match() -> None:
    service = _service()
    _seed(service)
    result = service.resolve_identity(ResolveIdentityQuery(listing_id="list_0700_hkex"))
    assert result.status == ResolutionStatus.RESOLVED


def test_isin_exact_match() -> None:
    service = _service()
    _seed(service)
    result = service.resolve_identity(ResolveIdentityQuery(isin="KYG875721634"))
    assert result.status == ResolutionStatus.RESOLVED
    assert result.candidates[0].security_id == "sec_tencent_ord"


def test_exchange_plus_ticker_match() -> None:
    service = _service()
    _seed(service)
    result = service.resolve_identity(ResolveIdentityQuery(exchange="HKEX", ticker="0700"))
    assert result.status == ResolutionStatus.RESOLVED


def test_historical_ticker_match_by_date() -> None:
    service = _service()
    _seed(service)
    result = service.resolve_identity(
        ResolveIdentityQuery(exchange="HKEX", ticker="0700", effective_date=date(2020, 1, 1))
    )
    assert result.status == ResolutionStatus.HISTORICAL_MATCH


def test_ticker_only_ambiguous_candidate() -> None:
    service = _service()
    _seed(service)
    service.create_company(
        CreateCompanyCommand(
            company_id="co_sg_1",
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
            security_id="sec_dbs_ord",
            issuer_company_id="co_sg_1",
            issuer_name=None,
            security_type=SecurityType.ORDINARY_EQUITY,
            security_name="DBS Ordinary Shares",
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
            listing_id="list_0700_sgx",
            security_id="sec_dbs_ord",
            exchange_code="SGX",
            ticker="0700",
            trading_currency="SGD",
            listing_country="SG",
            is_primary_listing=True,
            lot_size=Decimal("1"),
            price_source_symbol=None,
            active_from=date(2000, 1, 1),
            active_to=None,
        )
    )
    result = service.resolve_identity(ResolveIdentityQuery(ticker="0700"))
    assert result.status == ResolutionStatus.AMBIGUOUS
    assert result.requires_human_review is True


def test_provider_identifier_resolution() -> None:
    service = _service()
    _seed(service)
    result = service.resolve_identity(
        ResolveIdentityQuery(provider="BLOOMBERG", provider_identifier="bbg:HK.0700")
    )
    assert result.status == ResolutionStatus.RESOLVED


def test_legacy_mapping_resolution() -> None:
    service = _service()
    _seed(service)
    result = service.resolve_identity(ResolveIdentityQuery(legacy_asset_id="h_tencent", legacy_ticker="0700"))
    assert result.status == ResolutionStatus.RESOLVED


def test_unresolved_identity() -> None:
    service = _service()
    _seed(service)
    result = service.resolve_identity(ResolveIdentityQuery(exchange="NSE", ticker="ZZZZ"))
    assert result.status == ResolutionStatus.UNRESOLVED


def test_conflicting_identifiers_require_review() -> None:
    service = _service()
    _seed(service)
    service.create_company(
        CreateCompanyCommand(
            company_id="co_us_2",
            legal_name="Acme Corp",
            common_name="Acme",
            company_type="CORPORATE",
            jurisdiction_of_incorporation="US",
            primary_economic_country="US",
            sector="Technology",
            industry="Software",
            active_from=date(2001, 1, 1),
            active_to=None,
        )
    )
    service.create_security(
        CreateSecurityCommand(
            security_id="sec_acme_eq",
            issuer_company_id="co_us_2",
            issuer_name=None,
            security_type=SecurityType.ORDINARY_EQUITY,
            security_name="Acme Common",
            issue_currency="USD",
            issue_date=None,
            maturity_date=None,
            share_class_or_seniority=None,
            economic_exposure_type="EQUITY",
            active_from=date(2001, 1, 1),
            active_to=None,
        )
    )
    service.create_listing(
        CreateListingCommand(
            listing_id="list_acme_nyse",
            security_id="sec_acme_eq",
            exchange_code="NYSE",
            ticker="ACME",
            trading_currency="USD",
            listing_country="US",
            is_primary_listing=True,
            lot_size=None,
            price_source_symbol=None,
            active_from=date(2001, 1, 1),
            active_to=None,
        )
    )
    service.add_identifier(
        AddIdentifierCommand(
            identifier_id="id_provider_conflict",
            scope=EntityScope.LISTING,
            entity_id="list_acme_nyse",
            identifier_type=IdentifierType.PROVIDER_INTERNAL,
            identifier_value="bbg:HK.0700",
            provider_or_authority="BLOOMBERG",
            active_from=date(2001, 1, 1),
            active_to=None,
            source="fixture",
        )
    )

    result = service.resolve_identity(
        ResolveIdentityQuery(isin="KYG875721634", provider="BLOOMBERG", provider_identifier="bbg:HK.0700")
    )
    assert result.status == ResolutionStatus.CONFLICTING
    assert result.requires_human_review is True
