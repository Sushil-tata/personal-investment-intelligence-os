from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from piios.identity.application.commands import CreateCompanyCommand, CreateListingCommand, CreateRelationshipCommand, CreateSecurityCommand
from piios.identity.application.resolution import IdentityResolutionService
from piios.identity.application.services import IdentityApplicationService
from piios.identity.domain.enums import EntityScope, RelationshipType, SecurityType
from piios.identity.domain.exceptions import InvalidRelationshipError
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


def _seed_dual_listing(service: IdentityApplicationService) -> None:
    service.create_company(
        CreateCompanyCommand(
            company_id="co_us_adr",
            legal_name="Example India Tech Ltd",
            common_name="EIT",
            company_type="CORPORATE",
            jurisdiction_of_incorporation="IN",
            primary_economic_country="IN",
            sector="Technology",
            industry="Software",
            active_from=date(2000, 1, 1),
            active_to=None,
        )
    )
    service.create_security(
        CreateSecurityCommand(
            security_id="sec_eit_ord",
            issuer_company_id="co_us_adr",
            issuer_name=None,
            security_type=SecurityType.ORDINARY_EQUITY,
            security_name="EIT Ordinary",
            issue_currency="INR",
            issue_date=None,
            maturity_date=None,
            share_class_or_seniority=None,
            economic_exposure_type="EQUITY",
            active_from=date(2000, 1, 1),
            active_to=None,
        )
    )
    service.create_security(
        CreateSecurityCommand(
            security_id="sec_eit_adr",
            issuer_company_id="co_us_adr",
            issuer_name=None,
            security_type=SecurityType.ADR,
            security_name="EIT ADR",
            issue_currency="USD",
            issue_date=None,
            maturity_date=None,
            share_class_or_seniority=None,
            economic_exposure_type="EQUITY",
            active_from=date(2005, 1, 1),
            active_to=None,
        )
    )
    service.create_listing(
        CreateListingCommand(
            listing_id="list_eit_nse",
            security_id="sec_eit_ord",
            exchange_code="NSE",
            ticker="EIT",
            trading_currency="INR",
            listing_country="IN",
            is_primary_listing=True,
            lot_size=Decimal("1"),
            price_source_symbol="EIT.NS",
            active_from=date(2000, 1, 1),
            active_to=None,
        )
    )
    service.create_listing(
        CreateListingCommand(
            listing_id="list_eit_nyse",
            security_id="sec_eit_adr",
            exchange_code="NYSE",
            ticker="EIT",
            trading_currency="USD",
            listing_country="US",
            is_primary_listing=True,
            lot_size=Decimal("1"),
            price_source_symbol="EIT",
            active_from=date(2005, 1, 1),
            active_to=None,
        )
    )


def test_adr_to_underlying_relationship() -> None:
    service = _service()
    _seed_dual_listing(service)
    rel = service.create_relationship(
        CreateRelationshipCommand(
            relationship_id="rel_adr_underlying",
            source_scope=EntityScope.SECURITY,
            source_entity_id="sec_eit_adr",
            target_scope=EntityScope.SECURITY,
            target_entity_id="sec_eit_ord",
            relationship_type=RelationshipType.ADR_REPRESENTS,
            conversion_ratio=Decimal("2"),
            active_from=date(2005, 1, 1),
            active_to=None,
            source="fixture",
        )
    )
    assert rel.relationship_type == RelationshipType.ADR_REPRESENTS


def test_dual_listing_relationship() -> None:
    service = _service()
    _seed_dual_listing(service)
    rel = service.create_relationship(
        CreateRelationshipCommand(
            relationship_id="rel_dual_list",
            source_scope=EntityScope.LISTING,
            source_entity_id="list_eit_nse",
            target_scope=EntityScope.LISTING,
            target_entity_id="list_eit_nyse",
            relationship_type=RelationshipType.DUAL_LISTING_OF,
            conversion_ratio=None,
            active_from=date(2005, 1, 1),
            active_to=None,
            source="fixture",
        )
    )
    assert rel.relationship_type == RelationshipType.DUAL_LISTING_OF


def test_successor_predecessor_contradiction_fails() -> None:
    service = _service()
    _seed_dual_listing(service)
    service.create_relationship(
        CreateRelationshipCommand(
            relationship_id="rel_successor",
            source_scope=EntityScope.SECURITY,
            source_entity_id="sec_eit_adr",
            target_scope=EntityScope.SECURITY,
            target_entity_id="sec_eit_ord",
            relationship_type=RelationshipType.SUCCESSOR_OF,
            conversion_ratio=None,
            active_from=date(2020, 1, 1),
            active_to=None,
            source="fixture",
        )
    )
    with pytest.raises(InvalidRelationshipError):
        service.create_relationship(
            CreateRelationshipCommand(
                relationship_id="rel_predecessor_conflict",
                source_scope=EntityScope.SECURITY,
                source_entity_id="sec_eit_adr",
                target_scope=EntityScope.SECURITY,
                target_entity_id="sec_eit_ord",
                relationship_type=RelationshipType.PREDECESSOR_OF,
                conversion_ratio=None,
                active_from=date(2020, 6, 1),
                active_to=None,
                source="fixture",
            )
        )
