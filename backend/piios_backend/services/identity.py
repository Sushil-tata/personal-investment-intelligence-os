from __future__ import annotations

import sys
from datetime import timezone
from pathlib import Path

from sqlmodel import Session

# Ensure repo-root level piios package is importable from backend runtime.
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from piios.identity.application.commands import (  # noqa: E402
    AddIdentifierCommand,
    CreateCompanyCommand,
    CreateListingCommand,
    CreateRelationshipCommand,
    CreateSecurityCommand,
    LinkLegacyIdentityCommand,
)
from piios.identity.application.queries import ResolveIdentityQuery, UnresolvedIssuesQuery  # noqa: E402
from piios.identity.application.resolution import IdentityResolutionService  # noqa: E402
from piios.identity.application.services import IdentityApplicationService  # noqa: E402
from piios.identity.domain.enums import EntityScope, IdentifierType, RelationshipType, SecurityType  # noqa: E402
from piios.identity.infrastructure.sqlmodel_repositories import (  # noqa: E402
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


class BackendIdentityService:
    def __init__(self, session: Session) -> None:
        company_repo = SQLModelCompanyRepository(session)
        security_repo = SQLModelSecurityRepository(session)
        listing_repo = SQLModelListingRepository(session)
        identifier_repo = SQLModelIdentifierRepository(session)
        ticker_history_repo = SQLModelTickerHistoryRepository(session)
        relationship_repo = SQLModelSecurityRelationshipRepository(session)
        legacy_mapping_repo = SQLModelLegacyIdentityMappingRepository(session)
        issue_repo = SQLModelIdentityResolutionIssueRepository(session)
        query_service = SQLModelIdentityResolutionQueryService(
            company_repo,
            security_repo,
            listing_repo,
            identifier_repo,
            legacy_mapping_repo,
        )
        resolver = IdentityResolutionService(query_service)
        self._service = IdentityApplicationService(
            company_repo=company_repo,
            security_repo=security_repo,
            listing_repo=listing_repo,
            identifier_repo=identifier_repo,
            ticker_history_repo=ticker_history_repo,
            relationship_repo=relationship_repo,
            legacy_mapping_repo=legacy_mapping_repo,
            issue_repo=issue_repo,
            resolution_service=resolver,
        )

    def create_company(self, payload) -> dict:
        company = self._service.create_company(
            CreateCompanyCommand(
                company_id=payload.company_id,
                legal_name=payload.legal_name,
                common_name=payload.common_name,
                company_type=payload.company_type,
                jurisdiction_of_incorporation=payload.jurisdiction_of_incorporation,
                primary_economic_country=payload.primary_economic_country,
                sector=payload.sector,
                industry=payload.industry,
                active_from=payload.active_from,
                active_to=payload.active_to,
            )
        )
        return {
            "company_id": company.company_id.value,
            "legal_name": company.legal_name,
            "common_name": company.common_name,
            "company_type": company.company_type,
            "jurisdiction_of_incorporation": company.jurisdiction_of_incorporation.value,
            "primary_economic_country": company.primary_economic_country.value,
            "sector": company.sector,
            "industry": company.industry,
            "active_from": company.active_range.active_from,
            "active_to": company.active_range.active_to,
            "status": company.status.value,
        }

    def get_company(self, company_id: str, as_of):
        company = self._service._company_repo.get_effective(company_id, as_of)
        if company is None:
            return None
        return {
            "company_id": company.company_id.value,
            "legal_name": company.legal_name,
            "common_name": company.common_name,
            "company_type": company.company_type,
            "jurisdiction_of_incorporation": company.jurisdiction_of_incorporation.value,
            "primary_economic_country": company.primary_economic_country.value,
            "sector": company.sector,
            "industry": company.industry,
            "active_from": company.active_range.active_from,
            "active_to": company.active_range.active_to,
            "status": company.status.value,
        }

    def search_companies(self, token: str) -> list[dict]:
        rows = self._service._company_repo.search_by_name(token)
        return [
            {
                "company_id": row.company_id.value,
                "legal_name": row.legal_name,
                "common_name": row.common_name,
                "company_type": row.company_type,
                "jurisdiction_of_incorporation": row.jurisdiction_of_incorporation.value,
                "primary_economic_country": row.primary_economic_country.value,
                "sector": row.sector,
                "industry": row.industry,
                "active_from": row.active_range.active_from,
                "active_to": row.active_range.active_to,
                "status": row.status.value,
            }
            for row in rows
        ]

    def create_security(self, payload) -> dict:
        security = self._service.create_security(
            CreateSecurityCommand(
                security_id=payload.security_id,
                issuer_company_id=payload.issuer_company_id,
                issuer_name=payload.issuer_name,
                security_type=SecurityType(payload.security_type),
                security_name=payload.security_name,
                issue_currency=payload.issue_currency,
                issue_date=payload.issue_date,
                maturity_date=payload.maturity_date,
                share_class_or_seniority=payload.share_class_or_seniority,
                economic_exposure_type=payload.economic_exposure_type,
                active_from=payload.active_from,
                active_to=payload.active_to,
            )
        )
        return {
            "security_id": security.security_id.value,
            "issuer_company_id": security.issuer_company_id.value if security.issuer_company_id else None,
            "issuer_name": security.issuer_name,
            "security_type": security.security_type.value,
            "security_name": security.security_name,
            "issue_currency": security.issue_currency.value,
            "issue_date": security.issue_date,
            "maturity_date": security.maturity_date,
            "share_class_or_seniority": security.share_class_or_seniority,
            "economic_exposure_type": security.economic_exposure_type,
            "active_from": security.active_range.active_from,
            "active_to": security.active_range.active_to,
            "status": security.status.value,
        }

    def get_security(self, security_id: str):
        security = self._service._security_repo.get_by_id(security_id)
        if security is None:
            return None
        return {
            "security_id": security.security_id.value,
            "issuer_company_id": security.issuer_company_id.value if security.issuer_company_id else None,
            "issuer_name": security.issuer_name,
            "security_type": security.security_type.value,
            "security_name": security.security_name,
            "issue_currency": security.issue_currency.value,
            "issue_date": security.issue_date,
            "maturity_date": security.maturity_date,
            "share_class_or_seniority": security.share_class_or_seniority,
            "economic_exposure_type": security.economic_exposure_type,
            "active_from": security.active_range.active_from,
            "active_to": security.active_range.active_to,
            "status": security.status.value,
        }

    def list_company_securities(self, company_id: str) -> list[dict]:
        rows = self._service._security_repo.list_by_company(company_id)
        return [self.get_security(row.security_id.value) for row in rows if self.get_security(row.security_id.value)]

    def create_listing(self, payload) -> dict:
        listing = self._service.create_listing(
            CreateListingCommand(
                listing_id=payload.listing_id,
                security_id=payload.security_id,
                exchange_code=payload.exchange_code,
                ticker=payload.ticker,
                trading_currency=payload.trading_currency,
                listing_country=payload.listing_country,
                is_primary_listing=payload.is_primary_listing,
                lot_size=payload.lot_size,
                price_source_symbol=payload.price_source_symbol,
                active_from=payload.active_from,
                active_to=payload.active_to,
            )
        )
        return {
            "listing_id": listing.listing_id.value,
            "security_id": listing.security_id.value,
            "exchange_code": listing.exchange_code.value,
            "ticker": listing.ticker.source_value,
            "trading_currency": listing.trading_currency.value,
            "listing_country": listing.listing_country.value,
            "is_primary_listing": listing.is_primary_listing,
            "lot_size": listing.lot_size,
            "price_source_symbol": listing.price_source_symbol,
            "active_from": listing.active_range.active_from,
            "active_to": listing.active_range.active_to,
            "status": listing.status.value,
        }

    def get_listing(self, listing_id: str):
        listing = self._service._listing_repo.get_by_id(listing_id)
        if listing is None:
            return None
        return {
            "listing_id": listing.listing_id.value,
            "security_id": listing.security_id.value,
            "exchange_code": listing.exchange_code.value,
            "ticker": listing.ticker.source_value,
            "trading_currency": listing.trading_currency.value,
            "listing_country": listing.listing_country.value,
            "is_primary_listing": listing.is_primary_listing,
            "lot_size": listing.lot_size,
            "price_source_symbol": listing.price_source_symbol,
            "active_from": listing.active_range.active_from,
            "active_to": listing.active_range.active_to,
            "status": listing.status.value,
        }

    def list_security_listings(self, security_id: str) -> list[dict]:
        rows = self._service._listing_repo.list_by_security(security_id)
        return [self.get_listing(row.listing_id.value) for row in rows if self.get_listing(row.listing_id.value)]

    def add_identifier(self, payload) -> None:
        self._service.add_identifier(
            AddIdentifierCommand(
                identifier_id=payload.identifier_id,
                scope=EntityScope(payload.entity_scope),
                entity_id=payload.entity_id,
                identifier_type=IdentifierType(payload.identifier_type),
                identifier_value=payload.identifier_value,
                provider_or_authority=payload.provider_or_authority,
                active_from=payload.active_from,
                active_to=payload.active_to,
                source=payload.source,
            )
        )

    def add_relationship(self, payload) -> None:
        self._service.create_relationship(
            CreateRelationshipCommand(
                relationship_id=payload.relationship_id,
                source_scope=EntityScope(payload.source_scope),
                source_entity_id=payload.source_entity_id,
                target_scope=EntityScope(payload.target_scope),
                target_entity_id=payload.target_entity_id,
                relationship_type=RelationshipType(payload.relationship_type),
                conversion_ratio=payload.conversion_ratio,
                active_from=payload.active_from,
                active_to=payload.active_to,
                source=payload.source,
            )
        )

    def resolve(self, payload) -> dict:
        result = self._service.resolve_identity(
            ResolveIdentityQuery(
                company_id=payload.company_id,
                security_id=payload.security_id,
                listing_id=payload.listing_id,
                isin=payload.isin,
                exchange=payload.exchange,
                ticker=payload.ticker,
                provider=payload.provider,
                provider_identifier=payload.provider_identifier,
                legacy_asset_id=payload.legacy_asset_id,
                legacy_ticker=payload.legacy_ticker,
                company_name=payload.company_name,
                jurisdiction=payload.jurisdiction,
                trading_currency=payload.trading_currency,
                effective_date=payload.effective_date,
            )
        )
        return {
            "status": result.status.value,
            "candidates": [
                {
                    "company_id": c.company_id,
                    "security_id": c.security_id,
                    "listing_id": c.listing_id,
                    "match_basis": c.match_basis,
                    "rule_strength": c.rule_strength,
                    "is_active": c.is_active,
                    "is_historical": c.is_historical,
                }
                for c in result.candidates
            ],
            "warnings": result.warnings,
            "conflicts": result.conflicts,
            "effective_date": result.effective_date,
            "requires_human_review": result.requires_human_review,
        }

    def unresolved_issues(self, limit: int = 100) -> list[dict]:
        rows = self._service.inspect_unresolved_identities(UnresolvedIssuesQuery(limit=limit))
        return [
            {
                "issue_id": row.issue_id,
                "source_record_type": row.source_record_type,
                "source_record_id": row.source_record_id,
                "reason": row.reason,
                "candidates": row.candidates,
                "recommended_resolution": row.recommended_resolution,
                "owner_decision": row.owner_decision,
                "reviewer": row.reviewer,
                "reviewed_at": row.reviewed_at.astimezone(timezone.utc).isoformat() if row.reviewed_at else None,
                "notes": row.notes,
                "resulting_mapping_id": row.resulting_mapping_id,
                "status": row.status,
                "created_at": row.created_at.astimezone(timezone.utc).isoformat(),
            }
            for row in rows
        ]

    def link_legacy_mapping(
        self,
        *,
        mapping_id: str,
        legacy_source: str,
        legacy_record_id: str,
        legacy_asset_id: str | None,
        legacy_ticker: str | None,
        company_id: str | None,
        security_id: str | None,
        listing_id: str | None,
        resolution_status: str,
        provenance: str,
    ) -> None:
        self._service.link_legacy_identity(
            LinkLegacyIdentityCommand(
                mapping_id=mapping_id,
                legacy_source=legacy_source,
                legacy_record_id=legacy_record_id,
                legacy_asset_id=legacy_asset_id,
                legacy_instrument_id=None,
                legacy_ticker=legacy_ticker,
                company_id=company_id,
                security_id=security_id,
                listing_id=listing_id,
                resolution_status=resolution_status,
                provenance=provenance,
            )
        )
