from __future__ import annotations

from dataclasses import replace
from datetime import date

from piios.identity.domain.entities import (
    Company,
    IdentityResolutionIssue,
    LegacyIdentityMapping,
    ListingInstrument,
    ResolutionCandidate,
    Security,
    SecurityIdentifier,
    SecurityRelationship,
    TickerHistoryRecord,
)
from piios.identity.domain.enums import IdentifierType, VerificationStatus
from piios.identity.infrastructure.repository_protocols import (
    CompanyRepositoryProtocol,
    IdentifierRepositoryProtocol,
    IdentityResolutionIssueRepositoryProtocol,
    IdentityResolutionQueryProtocol,
    LegacyIdentityMappingRepositoryProtocol,
    ListingRepositoryProtocol,
    SecurityRelationshipRepositoryProtocol,
    SecurityRepositoryProtocol,
    TickerHistoryRepositoryProtocol,
)


class InMemoryCompanyRepository(CompanyRepositoryProtocol):
    def __init__(self) -> None:
        self._items: dict[str, Company] = {}

    def create(self, company: Company) -> Company:
        self._items[company.company_id.value] = company
        return company

    def get_by_id(self, company_id: str) -> Company | None:
        return self._items.get(company_id)

    def search_by_name(self, name: str) -> list[Company]:
        token = name.strip().lower()
        return [
            item
            for item in self._items.values()
            if token in item.legal_name.lower() or (item.common_name and token in item.common_name.lower())
        ]

    def list_active(self, as_of: date) -> list[Company]:
        return [item for item in self._items.values() if item.active_range.contains(as_of)]

    def update_metadata(self, company_id: str, sector: str | None, industry: str | None, updated_at_iso: str) -> Company | None:
        company = self._items.get(company_id)
        if company is None:
            return None
        updated = replace(company, sector=sector, industry=industry)
        self._items[company_id] = updated
        return updated

    def get_effective(self, company_id: str, as_of: date) -> Company | None:
        item = self._items.get(company_id)
        if item is None:
            return None
        if not item.active_range.contains(as_of):
            return None
        return item


class InMemorySecurityRepository(SecurityRepositoryProtocol):
    def __init__(self) -> None:
        self._items: dict[str, Security] = {}

    def create(self, security: Security) -> Security:
        self._items[security.security_id.value] = security
        return security

    def get_by_id(self, security_id: str) -> Security | None:
        return self._items.get(security_id)

    def list_by_company(self, company_id: str) -> list[Security]:
        return [item for item in self._items.values() if item.issuer_company_id and item.issuer_company_id.value == company_id]

    def list_active(self, as_of: date) -> list[Security]:
        return [item for item in self._items.values() if item.active_range.contains(as_of)]


class InMemoryListingRepository(ListingRepositoryProtocol):
    def __init__(self) -> None:
        self._items: dict[str, ListingInstrument] = {}

    def create(self, listing: ListingInstrument) -> ListingInstrument:
        self._items[listing.listing_id.value] = listing
        return listing

    def get_by_id(self, listing_id: str) -> ListingInstrument | None:
        return self._items.get(listing_id)

    def list_by_security(self, security_id: str) -> list[ListingInstrument]:
        return [item for item in self._items.values() if item.security_id.value == security_id]

    def get_active_by_exchange_ticker(self, exchange: str, ticker: str, as_of: date) -> ListingInstrument | None:
        exchange_key = exchange.strip().upper()
        ticker_key = ticker.strip().upper().replace(" ", "")
        for item in self._items.values():
            if (
                item.exchange_code.value.strip().upper() == exchange_key
                and item.ticker.canonical_value == ticker_key
                and item.active_range.contains(as_of)
            ):
                return item
        return None

    def get_historical_by_exchange_ticker(self, exchange: str, ticker: str, target_date: date) -> ListingInstrument | None:
        return self.get_active_by_exchange_ticker(exchange, ticker, target_date)


class InMemoryIdentifierRepository(IdentifierRepositoryProtocol):
    def __init__(self) -> None:
        self._items: dict[str, SecurityIdentifier] = {}

    def create(self, identifier: SecurityIdentifier) -> SecurityIdentifier:
        self._items[identifier.identifier_id] = identifier
        return identifier

    def list_for_entity(self, scope: str, entity_id: str) -> list[SecurityIdentifier]:
        return [item for item in self._items.values() if item.scope.value == scope and item.entity_id == entity_id]

    def find_active(
        self,
        identifier_type: IdentifierType,
        identifier_value: str,
        provider_or_authority: str | None,
        as_of: date,
    ) -> list[SecurityIdentifier]:
        value_key = identifier_value.strip().upper()
        provider_key = provider_or_authority.strip().lower() if provider_or_authority else None
        rows: list[SecurityIdentifier] = []
        for item in self._items.values():
            if item.identifier_type != identifier_type:
                continue
            if item.identifier_value.value.strip().upper() != value_key:
                continue
            if provider_key is not None and item.provider_or_authority.strip().lower() != provider_key:
                continue
            if item.active_range.contains(as_of):
                rows.append(item)
        return rows

    def mark_verified(self, identifier_id: str, updated_at_iso: str) -> SecurityIdentifier | None:
        item = self._items.get(identifier_id)
        if item is None:
            return None
        updated = replace(item, verification_status=VerificationStatus.VERIFIED)
        self._items[identifier_id] = updated
        return updated


class InMemoryTickerHistoryRepository(TickerHistoryRepositoryProtocol):
    def __init__(self) -> None:
        self._items: dict[str, TickerHistoryRecord] = {}

    def create(self, ticker_record: TickerHistoryRecord) -> TickerHistoryRecord:
        self._items[ticker_record.ticker_history_id] = ticker_record
        return ticker_record

    def list_for_listing(self, listing_id: str) -> list[TickerHistoryRecord]:
        return [item for item in self._items.values() if item.listing_id.value == listing_id]


class InMemorySecurityRelationshipRepository(SecurityRelationshipRepositoryProtocol):
    def __init__(self) -> None:
        self._items: dict[str, SecurityRelationship] = {}

    def create(self, relationship: SecurityRelationship) -> SecurityRelationship:
        self._items[relationship.relationship_id] = relationship
        return relationship

    def list_for_entity(self, scope: str, entity_id: str) -> list[SecurityRelationship]:
        return [
            row
            for row in self._items.values()
            if (row.source_scope.value == scope and row.source_entity_id == entity_id)
            or (row.target_scope.value == scope and row.target_entity_id == entity_id)
        ]


class InMemoryLegacyIdentityMappingRepository(LegacyIdentityMappingRepositoryProtocol):
    def __init__(self) -> None:
        self._items: dict[str, LegacyIdentityMapping] = {}

    def create(self, mapping: LegacyIdentityMapping) -> LegacyIdentityMapping:
        self._items[mapping.mapping_id] = mapping
        return mapping

    def get_by_legacy_keys(
        self,
        legacy_source: str,
        legacy_record_id: str | None,
        legacy_asset_id: str | None,
        legacy_ticker: str | None,
    ) -> LegacyIdentityMapping | None:
        for item in self._items.values():
            if item.legacy_source != legacy_source:
                continue
            if legacy_record_id and item.legacy_record_id == legacy_record_id:
                return item
            if legacy_asset_id and item.legacy_asset_id == legacy_asset_id:
                return item
            if legacy_ticker and item.legacy_ticker and item.legacy_ticker.upper() == legacy_ticker.upper():
                return item
        return None


class InMemoryIdentityResolutionIssueRepository(IdentityResolutionIssueRepositoryProtocol):
    def __init__(self) -> None:
        self._items: dict[str, IdentityResolutionIssue] = {}

    def create(self, issue: IdentityResolutionIssue) -> IdentityResolutionIssue:
        self._items[issue.issue_id] = issue
        return issue

    def list_open(self, limit: int = 100) -> list[IdentityResolutionIssue]:
        rows = [item for item in self._items.values() if item.status.value == "OPEN"]
        return sorted(rows, key=lambda x: x.created_at, reverse=True)[:limit]


class InMemoryIdentityResolutionQueryService(IdentityResolutionQueryProtocol):
    def __init__(
        self,
        companies: InMemoryCompanyRepository,
        securities: InMemorySecurityRepository,
        listings: InMemoryListingRepository,
        identifiers: InMemoryIdentifierRepository,
        legacy_mappings: InMemoryLegacyIdentityMappingRepository,
    ) -> None:
        self._companies = companies
        self._securities = securities
        self._listings = listings
        self._identifiers = identifiers
        self._legacy = legacy_mappings

    def candidates_by_identifier(
        self,
        identifier_type: IdentifierType,
        identifier_value: str,
        as_of: date,
        provider_or_authority: str | None = None,
    ) -> list[ResolutionCandidate]:
        rows = self._identifiers.find_active(identifier_type, identifier_value, provider_or_authority, as_of)
        candidates: list[ResolutionCandidate] = []
        for row in rows:
            company_id: str | None = None
            security_id: str | None = None
            listing_id: str | None = None
            if row.scope.value == "COMPANY":
                company_id = row.entity_id
            elif row.scope.value == "SECURITY":
                security_id = row.entity_id
                sec = self._securities.get_by_id(security_id)
                if sec and sec.issuer_company_id:
                    company_id = sec.issuer_company_id.value
            elif row.scope.value == "LISTING":
                listing_id = row.entity_id
                listing = self._listings.get_by_id(listing_id)
                if listing is not None:
                    security_id = listing.security_id.value
                    sec = self._securities.get_by_id(security_id)
                    if sec and sec.issuer_company_id:
                        company_id = sec.issuer_company_id.value
            candidates.append(
                ResolutionCandidate(
                    company_id=company_id,
                    security_id=security_id,
                    listing_id=listing_id,
                    match_basis=f"{identifier_type.value}:{identifier_value}",
                    rule_strength="AUTHORITATIVE" if identifier_type == IdentifierType.ISIN else "STRONG",
                    is_active=True,
                    is_historical=False,
                )
            )
        return candidates

    def candidates_by_exchange_ticker(self, exchange: str, ticker: str, as_of: date) -> list[ResolutionCandidate]:
        listing = self._listings.get_active_by_exchange_ticker(exchange, ticker, as_of)
        if listing is None:
            return []
        security = self._securities.get_by_id(listing.security_id.value)
        company_id = security.issuer_company_id.value if security and security.issuer_company_id else None
        return [
            ResolutionCandidate(
                company_id=company_id,
                security_id=listing.security_id.value,
                listing_id=listing.listing_id.value,
                match_basis="exchange+ticker",
                rule_strength="STRONG",
                is_active=True,
                is_historical=False,
            )
        ]

    def candidates_by_ticker_currency(self, ticker: str, trading_currency: str, as_of: date) -> list[ResolutionCandidate]:
        ticker_key = ticker.strip().upper().replace(" ", "")
        cur_key = trading_currency.strip().upper()
        rows: list[ResolutionCandidate] = []
        for listing in self._listings._items.values():
            if listing.ticker.canonical_value != ticker_key:
                continue
            if listing.trading_currency.value.strip().upper() != cur_key:
                continue
            if not listing.active_range.contains(as_of):
                continue
            security = self._securities.get_by_id(listing.security_id.value)
            company_id = security.issuer_company_id.value if security and security.issuer_company_id else None
            rows.append(
                ResolutionCandidate(
                    company_id=company_id,
                    security_id=listing.security_id.value,
                    listing_id=listing.listing_id.value,
                    match_basis="ticker+currency",
                    rule_strength="MEDIUM",
                    is_active=True,
                    is_historical=False,
                )
            )
        return rows

    def candidates_by_company_name_jurisdiction(self, name: str, jurisdiction: str, as_of: date) -> list[ResolutionCandidate]:
        name_key = name.strip().lower()
        jurisdiction_key = jurisdiction.strip().upper()
        rows: list[ResolutionCandidate] = []
        for company in self._companies.list_active(as_of):
            if jurisdiction_key != company.jurisdiction_of_incorporation.value.strip().upper():
                continue
            if name_key not in company.legal_name.lower() and (not company.common_name or name_key not in company.common_name.lower()):
                continue
            rows.append(
                ResolutionCandidate(
                    company_id=company.company_id.value,
                    security_id=None,
                    listing_id=None,
                    match_basis="company_name+jurisdiction",
                    rule_strength="WEAK",
                    is_active=True,
                    is_historical=False,
                )
            )
        return rows

    def candidate_by_internal_ids(
        self,
        company_id: str | None,
        security_id: str | None,
        listing_id: str | None,
        as_of: date,
    ) -> ResolutionCandidate | None:
        if listing_id:
            listing = self._listings.get_by_id(listing_id)
            if listing and listing.active_range.contains(as_of):
                sec = self._securities.get_by_id(listing.security_id.value)
                comp_id = sec.issuer_company_id.value if sec and sec.issuer_company_id else None
                return ResolutionCandidate(
                    company_id=comp_id,
                    security_id=listing.security_id.value,
                    listing_id=listing_id,
                    match_basis="internal_listing_id",
                    rule_strength="AUTHORITATIVE",
                    is_active=True,
                    is_historical=False,
                )
        if security_id:
            sec = self._securities.get_by_id(security_id)
            if sec and sec.active_range.contains(as_of):
                comp_id = sec.issuer_company_id.value if sec.issuer_company_id else None
                return ResolutionCandidate(
                    company_id=comp_id,
                    security_id=security_id,
                    listing_id=None,
                    match_basis="internal_security_id",
                    rule_strength="AUTHORITATIVE",
                    is_active=True,
                    is_historical=False,
                )
        if company_id:
            comp = self._companies.get_effective(company_id, as_of)
            if comp:
                return ResolutionCandidate(
                    company_id=company_id,
                    security_id=None,
                    listing_id=None,
                    match_basis="internal_company_id",
                    rule_strength="AUTHORITATIVE",
                    is_active=True,
                    is_historical=False,
                )
        return None

    def legacy_mapping_candidate(
        self,
        legacy_asset_id: str | None,
        legacy_ticker: str | None,
        as_of: date,
    ) -> ResolutionCandidate | None:
        row = self._legacy.get_by_legacy_keys("legacy", None, legacy_asset_id, legacy_ticker)
        if row is None:
            return None
        return ResolutionCandidate(
            company_id=row.company_id,
            security_id=row.security_id,
            listing_id=row.listing_id,
            match_basis="legacy_mapping",
            rule_strength="MEDIUM",
            is_active=True,
            is_historical=False,
        )
