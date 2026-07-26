from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timezone
from uuid import uuid4

from piios.identity.application.commands import (
    AddIdentifierCommand,
    AddTickerHistoryCommand,
    CreateCompanyCommand,
    CreateListingCommand,
    CreateRelationshipCommand,
    CreateSecurityCommand,
    LinkLegacyIdentityCommand,
    MarkIdentityVerifiedCommand,
    RetireListingCommand,
)
from piios.identity.application.dto import IdentityResolutionIssueDTO, IdentityResolutionResultDTO
from piios.identity.application.queries import ResolveIdentityQuery, UnresolvedIssuesQuery
from piios.identity.application.resolution import IdentityResolutionService
from piios.identity.domain.entities import (
    Company,
    IdentityResolutionIssue,
    LegacyIdentityMapping,
    ListingInstrument,
    Security,
    SecurityIdentifier,
    SecurityRelationship,
    TickerHistoryRecord,
)
from piios.identity.domain.enums import (
    IdentityStatus,
    ListingStatus,
    ResolutionIssueStatus,
    VerificationStatus,
)
from piios.identity.domain.exceptions import HardDeleteProhibitedError, InvalidTransitionError
from piios.identity.domain.policies import (
    ensure_one_primary_listing,
    validate_identifier_uniqueness,
    validate_relationship,
    validate_ticker_history_overlap,
)
from piios.identity.domain.value_objects import (
    CompanyId,
    CountryCode,
    CurrencyCode,
    EffectiveDateRange,
    ExchangeCode,
    IdentifierValue,
    ListingId,
    SecurityId,
    Ticker,
)
from piios.identity.infrastructure.repository_protocols import (
    CompanyRepositoryProtocol,
    IdentifierRepositoryProtocol,
    IdentityResolutionIssueRepositoryProtocol,
    LegacyIdentityMappingRepositoryProtocol,
    ListingRepositoryProtocol,
    SecurityRelationshipRepositoryProtocol,
    SecurityRepositoryProtocol,
    TickerHistoryRepositoryProtocol,
)


class IdentityApplicationService:
    def __init__(
        self,
        company_repo: CompanyRepositoryProtocol,
        security_repo: SecurityRepositoryProtocol,
        listing_repo: ListingRepositoryProtocol,
        identifier_repo: IdentifierRepositoryProtocol,
        ticker_history_repo: TickerHistoryRepositoryProtocol,
        relationship_repo: SecurityRelationshipRepositoryProtocol,
        legacy_mapping_repo: LegacyIdentityMappingRepositoryProtocol,
        issue_repo: IdentityResolutionIssueRepositoryProtocol,
        resolution_service: IdentityResolutionService,
    ) -> None:
        self._company_repo = company_repo
        self._security_repo = security_repo
        self._listing_repo = listing_repo
        self._identifier_repo = identifier_repo
        self._ticker_history_repo = ticker_history_repo
        self._relationship_repo = relationship_repo
        self._legacy_mapping_repo = legacy_mapping_repo
        self._issue_repo = issue_repo
        self._resolver = resolution_service

    def create_company(self, command: CreateCompanyCommand) -> Company:
        now = _utc_now()
        company = Company(
            company_id=CompanyId(command.company_id),
            legal_name=command.legal_name,
            common_name=command.common_name,
            company_type=command.company_type,
            jurisdiction_of_incorporation=CountryCode(command.jurisdiction_of_incorporation),
            primary_economic_country=CountryCode(command.primary_economic_country),
            sector=command.sector,
            industry=command.industry,
            active_range=EffectiveDateRange(command.active_from, command.active_to),
            status=IdentityStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        return self._company_repo.create(company)

    def create_security(self, command: CreateSecurityCommand) -> Security:
        now = _utc_now()
        security = Security(
            security_id=SecurityId(command.security_id),
            issuer_company_id=CompanyId(command.issuer_company_id) if command.issuer_company_id else None,
            issuer_name=command.issuer_name,
            security_type=command.security_type,
            security_name=command.security_name,
            issue_currency=CurrencyCode(command.issue_currency),
            issue_date=command.issue_date,
            maturity_date=command.maturity_date,
            share_class_or_seniority=command.share_class_or_seniority,
            economic_exposure_type=command.economic_exposure_type,
            active_range=EffectiveDateRange(command.active_from, command.active_to),
            status=IdentityStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        return self._security_repo.create(security)

    def create_listing(self, command: CreateListingCommand) -> ListingInstrument:
        now = _utc_now()
        listing = ListingInstrument(
            listing_id=ListingId(command.listing_id),
            security_id=SecurityId(command.security_id),
            exchange_code=ExchangeCode(command.exchange_code),
            ticker=Ticker.from_source(command.ticker),
            trading_currency=CurrencyCode(command.trading_currency),
            listing_country=CountryCode(command.listing_country),
            is_primary_listing=command.is_primary_listing,
            lot_size=command.lot_size,
            price_source_symbol=command.price_source_symbol,
            active_range=EffectiveDateRange(command.active_from, command.active_to),
            status=ListingStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        existing = self._listing_repo.list_by_security(command.security_id)
        ensure_one_primary_listing(existing + [listing], command.active_from)
        return self._listing_repo.create(listing)

    def add_identifier(self, command: AddIdentifierCommand) -> SecurityIdentifier:
        now = _utc_now()
        record = SecurityIdentifier(
            identifier_id=command.identifier_id,
            scope=command.scope,
            entity_id=command.entity_id,
            identifier_type=command.identifier_type,
            identifier_value=IdentifierValue(command.identifier_value),
            provider_or_authority=command.provider_or_authority,
            active_range=EffectiveDateRange(command.active_from, command.active_to),
            verification_status=VerificationStatus.UNVERIFIED,
            source=command.source,
            created_at=now,
        )
        existing = self._identifier_repo.list_for_entity(command.scope.value, command.entity_id)
        validate_identifier_uniqueness(existing, record)
        return self._identifier_repo.create(record)

    def add_ticker_history(self, command: AddTickerHistoryCommand) -> TickerHistoryRecord:
        record = TickerHistoryRecord(
            ticker_history_id=command.ticker_history_id,
            listing_id=ListingId(command.listing_id),
            exchange_code=ExchangeCode(command.exchange_code),
            ticker=Ticker.from_source(command.ticker),
            active_range=EffectiveDateRange(command.active_from, command.active_to),
            change_reason=command.change_reason,
            source=command.source,
            verification_status=VerificationStatus.UNVERIFIED,
        )
        existing = self._ticker_history_repo.list_for_listing(command.listing_id)
        validate_ticker_history_overlap(existing, record)
        return self._ticker_history_repo.create(record)

    def create_relationship(self, command: CreateRelationshipCommand) -> SecurityRelationship:
        record = SecurityRelationship(
            relationship_id=command.relationship_id,
            source_scope=command.source_scope,
            source_entity_id=command.source_entity_id,
            target_scope=command.target_scope,
            target_entity_id=command.target_entity_id,
            relationship_type=command.relationship_type,
            conversion_ratio=command.conversion_ratio,
            active_range=EffectiveDateRange(command.active_from, command.active_to),
            source=command.source,
            verification_status=VerificationStatus.UNVERIFIED,
        )
        existing = self._relationship_repo.list_for_entity(command.source_scope.value, command.source_entity_id)
        validate_relationship(existing, record)
        return self._relationship_repo.create(record)

    def resolve_identity(self, query: ResolveIdentityQuery) -> IdentityResolutionResultDTO:
        result = self._resolver.resolve(query)
        if result.requires_human_review:
            self._issue_repo.create(
                IdentityResolutionIssue(
                    issue_id=f"iri-{uuid4().hex}",
                    source_record_type="resolution_request",
                    source_record_id=_build_request_fingerprint(query),
                    reason=result.status.value,
                    candidate_payload=[asdict(item) for item in result.candidates],
                    recommended_resolution=None,
                    owner_decision=None,
                    reviewer=None,
                    reviewed_at=None,
                    notes="auto-captured unresolved/ambiguous identity",
                    resulting_mapping_id=None,
                    status=ResolutionIssueStatus.OPEN,
                    created_at=_utc_now(),
                )
            )
        return result

    def mark_identity_verified(self, command: MarkIdentityVerifiedCommand) -> SecurityIdentifier | None:
        return self._identifier_repo.mark_verified(command.identifier_id, _utc_now().isoformat())

    def retire_listing(self, command: RetireListingCommand) -> ListingInstrument:
        listing = self._listing_repo.get_by_id(command.listing_id)
        if listing is None:
            raise InvalidTransitionError("listing not found")
        if listing.status == ListingStatus.DELISTED:
            raise InvalidTransitionError("listing already retired")
        retired = ListingInstrument(
            listing_id=listing.listing_id,
            security_id=listing.security_id,
            exchange_code=listing.exchange_code,
            ticker=listing.ticker,
            trading_currency=listing.trading_currency,
            listing_country=listing.listing_country,
            is_primary_listing=listing.is_primary_listing,
            lot_size=listing.lot_size,
            price_source_symbol=listing.price_source_symbol,
            active_range=EffectiveDateRange(listing.active_range.active_from, command.retired_on),
            status=ListingStatus.DELISTED,
            created_at=listing.created_at,
            updated_at=_utc_now(),
        )
        return self._listing_repo.create(retired)

    def amend_company_classification(self, company_id: str, sector: str | None, industry: str | None) -> Company | None:
        # Classification is treated as mutable metadata and not immutable identity.
        return self._company_repo.update_metadata(company_id, sector, industry, _utc_now().isoformat())

    def link_legacy_identity(self, command: LinkLegacyIdentityCommand) -> LegacyIdentityMapping:
        mapping = LegacyIdentityMapping(
            mapping_id=command.mapping_id,
            legacy_source=command.legacy_source,
            legacy_record_id=command.legacy_record_id,
            legacy_asset_id=command.legacy_asset_id,
            legacy_instrument_id=command.legacy_instrument_id,
            legacy_ticker=command.legacy_ticker,
            company_id=command.company_id,
            security_id=command.security_id,
            listing_id=command.listing_id,
            resolution_status=command.resolution_status,
            provenance=command.provenance,
            created_at=_utc_now(),
        )
        return self._legacy_mapping_repo.create(mapping)

    def inspect_unresolved_identities(self, query: UnresolvedIssuesQuery) -> list[IdentityResolutionIssueDTO]:
        rows = self._issue_repo.list_open(query.limit)
        return [
            IdentityResolutionIssueDTO(
                issue_id=row.issue_id,
                source_record_type=row.source_record_type,
                source_record_id=row.source_record_id,
                reason=row.reason,
                candidates=row.candidate_payload,
                recommended_resolution=row.recommended_resolution,
                owner_decision=row.owner_decision,
                reviewer=row.reviewer,
                reviewed_at=row.reviewed_at,
                notes=row.notes,
                resulting_mapping_id=row.resulting_mapping_id,
                status=row.status.value,
                created_at=row.created_at,
            )
            for row in rows
        ]

    def hard_delete_identity(self, *_args, **_kwargs) -> None:
        raise HardDeleteProhibitedError("hard delete is prohibited for identity records")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _build_request_fingerprint(query: ResolveIdentityQuery) -> str:
    parts = [
        query.company_id or "",
        query.security_id or "",
        query.listing_id or "",
        query.isin or "",
        query.exchange or "",
        query.ticker or "",
        query.provider or "",
        query.provider_identifier or "",
        query.legacy_asset_id or "",
        query.legacy_ticker or "",
        query.company_name or "",
        query.jurisdiction or "",
        query.trading_currency or "",
    ]
    return "|".join(parts)
