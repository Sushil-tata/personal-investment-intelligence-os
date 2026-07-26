from __future__ import annotations

import json
from datetime import date, datetime, timezone

from sqlmodel import Session, select

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
from piios.identity.domain.enums import (
    EntityScope,
    IdentifierType,
    ListingStatus,
    RelationshipType,
    ResolutionIssueStatus,
    SecurityType,
    VerificationStatus,
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
    IdentityResolutionQueryProtocol,
    LegacyIdentityMappingRepositoryProtocol,
    ListingRepositoryProtocol,
    SecurityRelationshipRepositoryProtocol,
    SecurityRepositoryProtocol,
    TickerHistoryRepositoryProtocol,
)
from piios_backend.models.entities import (
    IdentityCompanyEntity,
    IdentityLegacyMappingEntity,
    IdentityListingInstrumentEntity,
    IdentityResolutionIssueEntity,
    IdentitySecurityEntity,
    IdentitySecurityIdentifierEntity,
    IdentitySecurityRelationshipEntity,
    IdentityTickerHistoryEntity,
)


def _to_iso_date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLModelCompanyRepository(CompanyRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, company: Company) -> Company:
        row = IdentityCompanyEntity(
            company_id=company.company_id.value,
            legal_name=company.legal_name,
            common_name=company.common_name,
            company_type=company.company_type,
            jurisdiction_of_incorporation=company.jurisdiction_of_incorporation.value.upper(),
            primary_economic_country=company.primary_economic_country.value.upper(),
            sector=company.sector,
            industry=company.industry,
            active_from=company.active_range.active_from.isoformat(),
            active_to=_to_iso_date(company.active_range.active_to),
            status=company.status.value,
            created_at=company.created_at.isoformat(),
            updated_at=company.updated_at.isoformat(),
        )
        self._session.add(row)
        self._session.commit()
        return company

    def get_by_id(self, company_id: str) -> Company | None:
        row = self._session.exec(select(IdentityCompanyEntity).where(IdentityCompanyEntity.company_id == company_id)).first()
        if row is None:
            return None
        return _company_from_row(row)

    def search_by_name(self, name: str) -> list[Company]:
        token = name.strip().lower()
        rows = self._session.exec(select(IdentityCompanyEntity)).all()
        return [
            _company_from_row(row)
            for row in rows
            if token in row.legal_name.lower() or (row.common_name and token in row.common_name.lower())
        ]

    def list_active(self, as_of: date) -> list[Company]:
        rows = self._session.exec(select(IdentityCompanyEntity)).all()
        return [item for item in (_company_from_row(row) for row in rows) if item.active_range.contains(as_of)]

    def update_metadata(self, company_id: str, sector: str | None, industry: str | None, updated_at_iso: str) -> Company | None:
        row = self._session.exec(select(IdentityCompanyEntity).where(IdentityCompanyEntity.company_id == company_id)).first()
        if row is None:
            return None
        row.sector = sector
        row.industry = industry
        row.updated_at = updated_at_iso
        self._session.add(row)
        self._session.commit()
        return _company_from_row(row)

    def get_effective(self, company_id: str, as_of: date) -> Company | None:
        row = self.get_by_id(company_id)
        if row and row.active_range.contains(as_of):
            return row
        return None


class SQLModelSecurityRepository(SecurityRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, security: Security) -> Security:
        row = IdentitySecurityEntity(
            security_id=security.security_id.value,
            issuer_company_id=security.issuer_company_id.value if security.issuer_company_id else None,
            issuer_name=security.issuer_name,
            security_type=security.security_type.value,
            security_name=security.security_name,
            issue_currency=security.issue_currency.value.upper(),
            issue_date=_to_iso_date(security.issue_date),
            maturity_date=_to_iso_date(security.maturity_date),
            share_class_or_seniority=security.share_class_or_seniority,
            economic_exposure_type=security.economic_exposure_type,
            active_from=security.active_range.active_from.isoformat(),
            active_to=_to_iso_date(security.active_range.active_to),
            status=security.status.value,
            created_at=security.created_at.isoformat(),
            updated_at=security.updated_at.isoformat(),
        )
        self._session.add(row)
        self._session.commit()
        return security

    def get_by_id(self, security_id: str) -> Security | None:
        row = self._session.exec(select(IdentitySecurityEntity).where(IdentitySecurityEntity.security_id == security_id)).first()
        if row is None:
            return None
        return _security_from_row(row)

    def list_by_company(self, company_id: str) -> list[Security]:
        rows = self._session.exec(select(IdentitySecurityEntity).where(IdentitySecurityEntity.issuer_company_id == company_id)).all()
        return [_security_from_row(row) for row in rows]

    def list_active(self, as_of: date) -> list[Security]:
        rows = self._session.exec(select(IdentitySecurityEntity)).all()
        return [item for item in (_security_from_row(row) for row in rows) if item.active_range.contains(as_of)]


class SQLModelListingRepository(ListingRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, listing: ListingInstrument) -> ListingInstrument:
        existing = self._session.exec(
            select(IdentityListingInstrumentEntity).where(IdentityListingInstrumentEntity.listing_id == listing.listing_id.value)
        ).first()
        row = existing or IdentityListingInstrumentEntity(listing_id=listing.listing_id.value)
        row.security_id = listing.security_id.value
        row.exchange_code = listing.exchange_code.value.upper()
        row.ticker_source = listing.ticker.source_value
        row.ticker_canonical = listing.ticker.canonical_value
        row.trading_currency = listing.trading_currency.value.upper()
        row.listing_country = listing.listing_country.value.upper()
        row.is_primary_listing = listing.is_primary_listing
        row.lot_size = float(listing.lot_size) if listing.lot_size is not None else None
        row.price_source_symbol = listing.price_source_symbol
        row.active_from = listing.active_range.active_from.isoformat()
        row.active_to = _to_iso_date(listing.active_range.active_to)
        row.status = listing.status.value
        now_iso = _utc_now_iso()
        row.created_at = existing.created_at if existing else listing.created_at.isoformat()
        row.updated_at = now_iso
        self._session.add(row)
        self._session.commit()
        return listing

    def get_by_id(self, listing_id: str) -> ListingInstrument | None:
        row = self._session.exec(select(IdentityListingInstrumentEntity).where(IdentityListingInstrumentEntity.listing_id == listing_id)).first()
        if row is None:
            return None
        return _listing_from_row(row)

    def list_by_security(self, security_id: str) -> list[ListingInstrument]:
        rows = self._session.exec(select(IdentityListingInstrumentEntity).where(IdentityListingInstrumentEntity.security_id == security_id)).all()
        return [_listing_from_row(row) for row in rows]

    def get_active_by_exchange_ticker(self, exchange: str, ticker: str, as_of: date) -> ListingInstrument | None:
        exchange_key = exchange.strip().upper()
        ticker_key = ticker.strip().upper().replace(" ", "")
        rows = self._session.exec(
            select(IdentityListingInstrumentEntity).where(
                IdentityListingInstrumentEntity.exchange_code == exchange_key,
                IdentityListingInstrumentEntity.ticker_canonical == ticker_key,
            )
        ).all()
        for row in rows:
            mapped = _listing_from_row(row)
            if mapped.active_range.contains(as_of) and mapped.status == ListingStatus.ACTIVE:
                return mapped
        return None

    def get_historical_by_exchange_ticker(self, exchange: str, ticker: str, target_date: date) -> ListingInstrument | None:
        exchange_key = exchange.strip().upper()
        ticker_key = ticker.strip().upper().replace(" ", "")
        rows = self._session.exec(
            select(IdentityTickerHistoryEntity).where(
                IdentityTickerHistoryEntity.exchange_code == exchange_key,
                IdentityTickerHistoryEntity.ticker_canonical == ticker_key,
            )
        ).all()
        for history in rows:
            start = _parse_date(history.active_from)
            end = _parse_date(history.active_to)
            if start and start <= target_date and (end is None or target_date <= end):
                listing = self.get_by_id(history.listing_id)
                if listing:
                    return listing
        return None


class SQLModelIdentifierRepository(IdentifierRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, identifier: SecurityIdentifier) -> SecurityIdentifier:
        row = IdentitySecurityIdentifierEntity(
            identifier_id=identifier.identifier_id,
            entity_scope=identifier.scope.value,
            entity_id=identifier.entity_id,
            identifier_type=identifier.identifier_type.value,
            identifier_value=identifier.identifier_value.value,
            provider_or_authority=identifier.provider_or_authority,
            active_from=identifier.active_range.active_from.isoformat(),
            active_to=_to_iso_date(identifier.active_range.active_to),
            verification_status=identifier.verification_status.value,
            source=identifier.source,
            created_at=identifier.created_at.isoformat(),
            updated_at=identifier.created_at.isoformat(),
        )
        self._session.add(row)
        self._session.commit()
        return identifier

    def list_for_entity(self, scope: str, entity_id: str) -> list[SecurityIdentifier]:
        rows = self._session.exec(
            select(IdentitySecurityIdentifierEntity).where(
                IdentitySecurityIdentifierEntity.entity_scope == scope,
                IdentitySecurityIdentifierEntity.entity_id == entity_id,
            )
        ).all()
        return [_identifier_from_row(row) for row in rows]

    def find_active(
        self,
        identifier_type: IdentifierType,
        identifier_value: str,
        provider_or_authority: str | None,
        as_of: date,
    ) -> list[SecurityIdentifier]:
        statement = select(IdentitySecurityIdentifierEntity).where(
            IdentitySecurityIdentifierEntity.identifier_type == identifier_type.value,
            IdentitySecurityIdentifierEntity.identifier_value == identifier_value,
        )
        if provider_or_authority:
            statement = statement.where(IdentitySecurityIdentifierEntity.provider_or_authority == provider_or_authority)
        rows = self._session.exec(statement).all()
        items = [_identifier_from_row(row) for row in rows]
        return [item for item in items if item.active_range.contains(as_of)]

    def mark_verified(self, identifier_id: str, updated_at_iso: str) -> SecurityIdentifier | None:
        row = self._session.exec(
            select(IdentitySecurityIdentifierEntity).where(IdentitySecurityIdentifierEntity.identifier_id == identifier_id)
        ).first()
        if row is None:
            return None
        row.verification_status = VerificationStatus.VERIFIED.value
        row.updated_at = updated_at_iso
        self._session.add(row)
        self._session.commit()
        return _identifier_from_row(row)


class SQLModelTickerHistoryRepository(TickerHistoryRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, ticker_record: TickerHistoryRecord) -> TickerHistoryRecord:
        row = IdentityTickerHistoryEntity(
            ticker_history_id=ticker_record.ticker_history_id,
            listing_id=ticker_record.listing_id.value,
            exchange_code=ticker_record.exchange_code.value.upper(),
            ticker_source=ticker_record.ticker.source_value,
            ticker_canonical=ticker_record.ticker.canonical_value,
            active_from=ticker_record.active_range.active_from.isoformat(),
            active_to=_to_iso_date(ticker_record.active_range.active_to),
            change_reason=ticker_record.change_reason,
            source=ticker_record.source,
            verification_status=ticker_record.verification_status.value,
            created_at=_utc_now_iso(),
            updated_at=_utc_now_iso(),
        )
        self._session.add(row)
        self._session.commit()
        return ticker_record

    def list_for_listing(self, listing_id: str) -> list[TickerHistoryRecord]:
        rows = self._session.exec(select(IdentityTickerHistoryEntity).where(IdentityTickerHistoryEntity.listing_id == listing_id)).all()
        return [_ticker_history_from_row(row) for row in rows]


class SQLModelSecurityRelationshipRepository(SecurityRelationshipRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, relationship: SecurityRelationship) -> SecurityRelationship:
        row = IdentitySecurityRelationshipEntity(
            relationship_id=relationship.relationship_id,
            source_scope=relationship.source_scope.value,
            source_entity_id=relationship.source_entity_id,
            target_scope=relationship.target_scope.value,
            target_entity_id=relationship.target_entity_id,
            relationship_type=relationship.relationship_type.value,
            conversion_ratio=float(relationship.conversion_ratio) if relationship.conversion_ratio is not None else None,
            active_from=relationship.active_range.active_from.isoformat(),
            active_to=_to_iso_date(relationship.active_range.active_to),
            source=relationship.source,
            verification_status=relationship.verification_status.value,
            created_at=_utc_now_iso(),
            updated_at=_utc_now_iso(),
        )
        self._session.add(row)
        self._session.commit()
        return relationship

    def list_for_entity(self, scope: str, entity_id: str) -> list[SecurityRelationship]:
        rows = self._session.exec(select(IdentitySecurityRelationshipEntity)).all()
        mapped = [_relationship_from_row(row) for row in rows]
        return [
            item
            for item in mapped
            if (item.source_scope.value == scope and item.source_entity_id == entity_id)
            or (item.target_scope.value == scope and item.target_entity_id == entity_id)
        ]


class SQLModelLegacyIdentityMappingRepository(LegacyIdentityMappingRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, mapping: LegacyIdentityMapping) -> LegacyIdentityMapping:
        row = IdentityLegacyMappingEntity(
            mapping_id=mapping.mapping_id,
            legacy_source=mapping.legacy_source,
            legacy_record_id=mapping.legacy_record_id,
            legacy_asset_id=mapping.legacy_asset_id,
            legacy_instrument_id=mapping.legacy_instrument_id,
            legacy_ticker=mapping.legacy_ticker,
            company_id=mapping.company_id,
            security_id=mapping.security_id,
            listing_id=mapping.listing_id,
            resolution_status=mapping.resolution_status,
            provenance=mapping.provenance,
            created_at=mapping.created_at.isoformat(),
        )
        self._session.add(row)
        self._session.commit()
        return mapping

    def get_by_legacy_keys(
        self,
        legacy_source: str,
        legacy_record_id: str | None,
        legacy_asset_id: str | None,
        legacy_ticker: str | None,
    ) -> LegacyIdentityMapping | None:
        rows = self._session.exec(
            select(IdentityLegacyMappingEntity).where(IdentityLegacyMappingEntity.legacy_source == legacy_source)
        ).all()
        for row in rows:
            if legacy_record_id and row.legacy_record_id == legacy_record_id:
                return _legacy_mapping_from_row(row)
            if legacy_asset_id and row.legacy_asset_id == legacy_asset_id:
                return _legacy_mapping_from_row(row)
            if legacy_ticker and row.legacy_ticker and row.legacy_ticker.upper() == legacy_ticker.upper():
                return _legacy_mapping_from_row(row)
        return None


class SQLModelIdentityResolutionIssueRepository(IdentityResolutionIssueRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, issue: IdentityResolutionIssue) -> IdentityResolutionIssue:
        row = IdentityResolutionIssueEntity(
            issue_id=issue.issue_id,
            source_record_type=issue.source_record_type,
            source_record_id=issue.source_record_id,
            reason=issue.reason,
            candidate_payload=json.dumps(issue.candidate_payload, sort_keys=True),
            recommended_resolution=issue.recommended_resolution,
            owner_decision=issue.owner_decision,
            reviewer=issue.reviewer,
            reviewed_at=issue.reviewed_at.isoformat() if issue.reviewed_at else None,
            notes=issue.notes,
            resulting_mapping_id=issue.resulting_mapping_id,
            status=issue.status.value,
            created_at=issue.created_at.isoformat(),
            updated_at=_utc_now_iso(),
        )
        self._session.add(row)
        self._session.commit()
        return issue

    def list_open(self, limit: int = 100) -> list[IdentityResolutionIssue]:
        rows = self._session.exec(
            select(IdentityResolutionIssueEntity)
            .where(IdentityResolutionIssueEntity.status == ResolutionIssueStatus.OPEN.value)
            .order_by(IdentityResolutionIssueEntity.created_at.desc())
        ).all()
        return [_issue_from_row(row) for row in rows[:limit]]


class SQLModelIdentityResolutionQueryService(IdentityResolutionQueryProtocol):
    def __init__(
        self,
        company_repo: SQLModelCompanyRepository,
        security_repo: SQLModelSecurityRepository,
        listing_repo: SQLModelListingRepository,
        identifier_repo: SQLModelIdentifierRepository,
        legacy_repo: SQLModelLegacyIdentityMappingRepository,
    ) -> None:
        self._companies = company_repo
        self._securities = security_repo
        self._listings = listing_repo
        self._identifiers = identifier_repo
        self._legacy = legacy_repo

    def candidates_by_identifier(
        self,
        identifier_type: IdentifierType,
        identifier_value: str,
        as_of: date,
        provider_or_authority: str | None = None,
    ) -> list[ResolutionCandidate]:
        rows = self._identifiers.find_active(identifier_type, identifier_value, provider_or_authority, as_of)
        result: list[ResolutionCandidate] = []
        for row in rows:
            company_id: str | None = None
            security_id: str | None = None
            listing_id: str | None = None
            if row.scope == EntityScope.COMPANY:
                company_id = row.entity_id
            elif row.scope == EntityScope.SECURITY:
                security_id = row.entity_id
                sec = self._securities.get_by_id(row.entity_id)
                if sec and sec.issuer_company_id:
                    company_id = sec.issuer_company_id.value
            else:
                listing_id = row.entity_id
                listing = self._listings.get_by_id(row.entity_id)
                if listing is not None:
                    security_id = listing.security_id.value
                    sec = self._securities.get_by_id(security_id)
                    if sec and sec.issuer_company_id:
                        company_id = sec.issuer_company_id.value
            result.append(
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
        return result

    def candidates_by_exchange_ticker(self, exchange: str, ticker: str, as_of: date) -> list[ResolutionCandidate]:
        listing = self._listings.get_active_by_exchange_ticker(exchange, ticker, as_of)
        if listing is None:
            return []
        sec = self._securities.get_by_id(listing.security_id.value)
        comp_id = sec.issuer_company_id.value if sec and sec.issuer_company_id else None
        return [
            ResolutionCandidate(
                company_id=comp_id,
                security_id=listing.security_id.value,
                listing_id=listing.listing_id.value,
                match_basis="exchange+ticker",
                rule_strength="STRONG",
                is_active=True,
                is_historical=False,
            )
        ]

    def candidates_by_ticker_currency(self, ticker: str, trading_currency: str, as_of: date) -> list[ResolutionCandidate]:
        candidates: list[ResolutionCandidate] = []
        ticker_key = ticker.strip().upper().replace(" ", "")
        for security in self._securities.list_active(as_of):
            listings = self._listings.list_by_security(security.security_id.value)
            for listing in listings:
                if listing.ticker.canonical_value != ticker_key:
                    continue
                if listing.trading_currency.value.upper() != trading_currency.strip().upper():
                    continue
                if not listing.active_range.contains(as_of):
                    continue
                comp_id = security.issuer_company_id.value if security.issuer_company_id else None
                candidates.append(
                    ResolutionCandidate(
                        company_id=comp_id,
                        security_id=security.security_id.value,
                        listing_id=listing.listing_id.value,
                        match_basis="ticker+currency",
                        rule_strength="MEDIUM",
                        is_active=True,
                        is_historical=False,
                    )
                )
        return candidates

    def candidates_by_company_name_jurisdiction(self, name: str, jurisdiction: str, as_of: date) -> list[ResolutionCandidate]:
        rows = self._companies.search_by_name(name)
        key = jurisdiction.strip().upper()
        return [
            ResolutionCandidate(
                company_id=row.company_id.value,
                security_id=None,
                listing_id=None,
                match_basis="company_name+jurisdiction",
                rule_strength="WEAK",
                is_active=True,
                is_historical=False,
            )
            for row in rows
            if row.jurisdiction_of_incorporation.value.upper() == key and row.active_range.contains(as_of)
        ]

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
                    listing_id=listing.listing_id.value,
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
                    security_id=sec.security_id.value,
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
                    company_id=comp.company_id.value,
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
        mapping = self._legacy.get_by_legacy_keys("legacy", None, legacy_asset_id, legacy_ticker)
        if mapping is None:
            return None
        return ResolutionCandidate(
            company_id=mapping.company_id,
            security_id=mapping.security_id,
            listing_id=mapping.listing_id,
            match_basis="legacy_mapping",
            rule_strength="MEDIUM",
            is_active=True,
            is_historical=False,
        )


def _company_from_row(row: IdentityCompanyEntity) -> Company:
    return Company(
        company_id=CompanyId(row.company_id),
        legal_name=row.legal_name,
        common_name=row.common_name,
        company_type=row.company_type,
        jurisdiction_of_incorporation=CountryCode(row.jurisdiction_of_incorporation),
        primary_economic_country=CountryCode(row.primary_economic_country),
        sector=row.sector,
        industry=row.industry,
        active_range=EffectiveDateRange(date.fromisoformat(row.active_from), _parse_date(row.active_to)),
        status=_enum_or_default(row.status),
        created_at=_parse_dt(row.created_at),
        updated_at=_parse_dt(row.updated_at),
    )


def _security_from_row(row: IdentitySecurityEntity) -> Security:
    return Security(
        security_id=SecurityId(row.security_id),
        issuer_company_id=CompanyId(row.issuer_company_id) if row.issuer_company_id else None,
        issuer_name=row.issuer_name,
        security_type=SecurityType(row.security_type),
        security_name=row.security_name,
        issue_currency=CurrencyCode(row.issue_currency),
        issue_date=_parse_date(row.issue_date),
        maturity_date=_parse_date(row.maturity_date),
        share_class_or_seniority=row.share_class_or_seniority,
        economic_exposure_type=row.economic_exposure_type,
        active_range=EffectiveDateRange(date.fromisoformat(row.active_from), _parse_date(row.active_to)),
        status=_enum_or_default(row.status),
        created_at=_parse_dt(row.created_at),
        updated_at=_parse_dt(row.updated_at),
    )


def _listing_from_row(row: IdentityListingInstrumentEntity) -> ListingInstrument:
    return ListingInstrument(
        listing_id=ListingId(row.listing_id),
        security_id=SecurityId(row.security_id),
        exchange_code=ExchangeCode(row.exchange_code),
        ticker=Ticker(source_value=row.ticker_source, canonical_value=row.ticker_canonical),
        trading_currency=CurrencyCode(row.trading_currency),
        listing_country=CountryCode(row.listing_country),
        is_primary_listing=row.is_primary_listing,
        lot_size=row.lot_size,
        price_source_symbol=row.price_source_symbol,
        active_range=EffectiveDateRange(date.fromisoformat(row.active_from), _parse_date(row.active_to)),
        status=ListingStatus(row.status),
        created_at=_parse_dt(row.created_at),
        updated_at=_parse_dt(row.updated_at),
    )


def _identifier_from_row(row: IdentitySecurityIdentifierEntity) -> SecurityIdentifier:
    return SecurityIdentifier(
        identifier_id=row.identifier_id,
        scope=EntityScope(row.entity_scope),
        entity_id=row.entity_id,
        identifier_type=IdentifierType(row.identifier_type),
        identifier_value=IdentifierValue(row.identifier_value),
        provider_or_authority=row.provider_or_authority,
        active_range=EffectiveDateRange(date.fromisoformat(row.active_from), _parse_date(row.active_to)),
        verification_status=VerificationStatus(row.verification_status),
        source=row.source,
        created_at=_parse_dt(row.created_at),
    )


def _ticker_history_from_row(row: IdentityTickerHistoryEntity) -> TickerHistoryRecord:
    return TickerHistoryRecord(
        ticker_history_id=row.ticker_history_id,
        listing_id=ListingId(row.listing_id),
        exchange_code=ExchangeCode(row.exchange_code),
        ticker=Ticker(source_value=row.ticker_source, canonical_value=row.ticker_canonical),
        active_range=EffectiveDateRange(date.fromisoformat(row.active_from), _parse_date(row.active_to)),
        change_reason=row.change_reason,
        source=row.source,
        verification_status=VerificationStatus(row.verification_status),
    )


def _relationship_from_row(row: IdentitySecurityRelationshipEntity) -> SecurityRelationship:
    return SecurityRelationship(
        relationship_id=row.relationship_id,
        source_scope=EntityScope(row.source_scope),
        source_entity_id=row.source_entity_id,
        target_scope=EntityScope(row.target_scope),
        target_entity_id=row.target_entity_id,
        relationship_type=RelationshipType(row.relationship_type),
        conversion_ratio=row.conversion_ratio,
        active_range=EffectiveDateRange(date.fromisoformat(row.active_from), _parse_date(row.active_to)),
        source=row.source,
        verification_status=VerificationStatus(row.verification_status),
    )


def _legacy_mapping_from_row(row: IdentityLegacyMappingEntity) -> LegacyIdentityMapping:
    return LegacyIdentityMapping(
        mapping_id=row.mapping_id,
        legacy_source=row.legacy_source,
        legacy_record_id=row.legacy_record_id,
        legacy_asset_id=row.legacy_asset_id,
        legacy_instrument_id=row.legacy_instrument_id,
        legacy_ticker=row.legacy_ticker,
        company_id=row.company_id,
        security_id=row.security_id,
        listing_id=row.listing_id,
        resolution_status=row.resolution_status,
        provenance=row.provenance,
        created_at=_parse_dt(row.created_at),
    )


def _issue_from_row(row: IdentityResolutionIssueEntity) -> IdentityResolutionIssue:
    return IdentityResolutionIssue(
        issue_id=row.issue_id,
        source_record_type=row.source_record_type,
        source_record_id=row.source_record_id,
        reason=row.reason,
        candidate_payload=json.loads(row.candidate_payload),
        recommended_resolution=row.recommended_resolution,
        owner_decision=row.owner_decision,
        reviewer=row.reviewer,
        reviewed_at=_parse_dt(row.reviewed_at) if row.reviewed_at else None,
        notes=row.notes,
        resulting_mapping_id=row.resulting_mapping_id,
        status=ResolutionIssueStatus(row.status),
        created_at=_parse_dt(row.created_at),
    )


def _enum_or_default(value: str):
    from piios.identity.domain.enums import IdentityStatus

    try:
        return IdentityStatus(value)
    except ValueError:
        return IdentityStatus.ACTIVE
