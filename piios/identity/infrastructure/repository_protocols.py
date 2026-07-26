from __future__ import annotations

from datetime import date
from typing import Protocol

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
from piios.identity.domain.enums import IdentifierType


class CompanyRepositoryProtocol(Protocol):
    def create(self, company: Company) -> Company:
        ...

    def get_by_id(self, company_id: str) -> Company | None:
        ...

    def search_by_name(self, name: str) -> list[Company]:
        ...

    def list_active(self, as_of: date) -> list[Company]:
        ...

    def update_metadata(self, company_id: str, sector: str | None, industry: str | None, updated_at_iso: str) -> Company | None:
        ...

    def get_effective(self, company_id: str, as_of: date) -> Company | None:
        ...


class SecurityRepositoryProtocol(Protocol):
    def create(self, security: Security) -> Security:
        ...

    def get_by_id(self, security_id: str) -> Security | None:
        ...

    def list_by_company(self, company_id: str) -> list[Security]:
        ...

    def list_active(self, as_of: date) -> list[Security]:
        ...


class ListingRepositoryProtocol(Protocol):
    def create(self, listing: ListingInstrument) -> ListingInstrument:
        ...

    def get_by_id(self, listing_id: str) -> ListingInstrument | None:
        ...

    def list_by_security(self, security_id: str) -> list[ListingInstrument]:
        ...

    def get_active_by_exchange_ticker(self, exchange: str, ticker: str, as_of: date) -> ListingInstrument | None:
        ...

    def get_historical_by_exchange_ticker(self, exchange: str, ticker: str, target_date: date) -> ListingInstrument | None:
        ...


class IdentifierRepositoryProtocol(Protocol):
    def create(self, identifier: SecurityIdentifier) -> SecurityIdentifier:
        ...

    def list_for_entity(self, scope: str, entity_id: str) -> list[SecurityIdentifier]:
        ...

    def find_active(
        self,
        identifier_type: IdentifierType,
        identifier_value: str,
        provider_or_authority: str | None,
        as_of: date,
    ) -> list[SecurityIdentifier]:
        ...

    def mark_verified(self, identifier_id: str, updated_at_iso: str) -> SecurityIdentifier | None:
        ...


class TickerHistoryRepositoryProtocol(Protocol):
    def create(self, ticker_record: TickerHistoryRecord) -> TickerHistoryRecord:
        ...

    def list_for_listing(self, listing_id: str) -> list[TickerHistoryRecord]:
        ...


class SecurityRelationshipRepositoryProtocol(Protocol):
    def create(self, relationship: SecurityRelationship) -> SecurityRelationship:
        ...

    def list_for_entity(self, scope: str, entity_id: str) -> list[SecurityRelationship]:
        ...


class LegacyIdentityMappingRepositoryProtocol(Protocol):
    def create(self, mapping: LegacyIdentityMapping) -> LegacyIdentityMapping:
        ...

    def get_by_legacy_keys(
        self,
        legacy_source: str,
        legacy_record_id: str | None,
        legacy_asset_id: str | None,
        legacy_ticker: str | None,
    ) -> LegacyIdentityMapping | None:
        ...


class IdentityResolutionIssueRepositoryProtocol(Protocol):
    def create(self, issue: IdentityResolutionIssue) -> IdentityResolutionIssue:
        ...

    def list_open(self, limit: int = 100) -> list[IdentityResolutionIssue]:
        ...


class IdentityResolutionQueryProtocol(Protocol):
    def candidates_by_identifier(
        self,
        identifier_type: IdentifierType,
        identifier_value: str,
        as_of: date,
        provider_or_authority: str | None = None,
    ) -> list[ResolutionCandidate]:
        ...

    def candidates_by_exchange_ticker(self, exchange: str, ticker: str, as_of: date) -> list[ResolutionCandidate]:
        ...

    def candidates_by_ticker_currency(self, ticker: str, trading_currency: str, as_of: date) -> list[ResolutionCandidate]:
        ...

    def candidates_by_company_name_jurisdiction(self, name: str, jurisdiction: str, as_of: date) -> list[ResolutionCandidate]:
        ...

    def candidate_by_internal_ids(
        self,
        company_id: str | None,
        security_id: str | None,
        listing_id: str | None,
        as_of: date,
    ) -> ResolutionCandidate | None:
        ...

    def legacy_mapping_candidate(
        self,
        legacy_asset_id: str | None,
        legacy_ticker: str | None,
        as_of: date,
    ) -> ResolutionCandidate | None:
        ...
