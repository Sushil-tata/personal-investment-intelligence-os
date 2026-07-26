from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from piios.identity.domain.enums import ResolutionStatus


@dataclass(frozen=True)
class CompanyReference:
    company_id: str
    display_name: str
    effective_date: date
    resolution_status: str
    legacy_source_reference: str | None = None


@dataclass(frozen=True)
class SecurityReference:
    security_id: str
    display_name: str
    effective_date: date
    resolution_status: str
    company_id: str | None = None
    legacy_source_reference: str | None = None


@dataclass(frozen=True)
class ListingReference:
    listing_id: str
    display_name: str
    ticker: str | None
    exchange: str | None
    effective_date: date
    resolution_status: str
    security_id: str | None = None
    legacy_source_reference: str | None = None


@dataclass(frozen=True)
class IdentitySubjectReference:
    company: CompanyReference | None = None
    security: SecurityReference | None = None
    listing: ListingReference | None = None


@dataclass(frozen=True)
class ResolutionCandidateDTO:
    company_id: str | None
    security_id: str | None
    listing_id: str | None
    match_basis: str
    rule_strength: str
    is_active: bool
    is_historical: bool


@dataclass(frozen=True)
class IdentityResolutionResultDTO:
    status: ResolutionStatus
    candidates: list[ResolutionCandidateDTO] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    effective_date: date | None = None
    requires_human_review: bool = False


@dataclass(frozen=True)
class IdentityResolutionIssueDTO:
    issue_id: str
    source_record_type: str
    source_record_id: str
    reason: str
    candidates: list[dict[str, str | None]]
    recommended_resolution: str | None
    owner_decision: str | None
    reviewer: str | None
    reviewed_at: datetime | None
    notes: str | None
    resulting_mapping_id: str | None
    status: str
    created_at: datetime
