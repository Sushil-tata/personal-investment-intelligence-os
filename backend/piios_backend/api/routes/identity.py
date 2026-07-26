from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from piios_backend.core.config import settings
from piios_backend.core.database import get_session
from piios_backend.schemas.identity import (
    CompanyCreateRequest,
    CompanyResponse,
    IdentifierCreateRequest,
    ListingCreateRequest,
    ListingResponse,
    RelationshipCreateRequest,
    ResolutionIssueResponse,
    ResolutionRequest,
    ResolutionResponse,
    SecurityCreateRequest,
    SecurityResponse,
    ShadowIdentityDiagnosticsResponse,
)
from piios_backend.services.identity import BackendIdentityService
from piios_backend.services.identity_shadow import build_shadow_identity_diagnostics


router = APIRouter(prefix="/identity", tags=["identity"])


def get_identity_service(session: Session = Depends(get_session)) -> BackendIdentityService:
    return BackendIdentityService(session)


def _ensure_internal_mutation_allowed() -> None:
    if settings.env.lower() not in {"dev", "test"}:
        raise HTTPException(status_code=403, detail="identity mutation endpoints are restricted to dev/test")


@router.post("/companies", response_model=CompanyResponse)
def create_company(request: CompanyCreateRequest, service: BackendIdentityService = Depends(get_identity_service)) -> CompanyResponse:
    _ensure_internal_mutation_allowed()
    return CompanyResponse(**service.create_company(request))


@router.get("/companies/search", response_model=list[CompanyResponse])
def search_companies(token: str, service: BackendIdentityService = Depends(get_identity_service)) -> list[CompanyResponse]:
    return [CompanyResponse(**row) for row in service.search_companies(token)]


@router.get("/companies/{company_id}", response_model=CompanyResponse)
def get_company(
    company_id: str,
    as_of: date = Query(default_factory=date.today),
    service: BackendIdentityService = Depends(get_identity_service),
) -> CompanyResponse:
    row = service.get_company(company_id, as_of)
    if row is None:
        raise HTTPException(status_code=404, detail="company_id not found")
    return CompanyResponse(**row)


@router.post("/securities", response_model=SecurityResponse)
def create_security(request: SecurityCreateRequest, service: BackendIdentityService = Depends(get_identity_service)) -> SecurityResponse:
    _ensure_internal_mutation_allowed()
    return SecurityResponse(**service.create_security(request))


@router.get("/securities/{security_id}", response_model=SecurityResponse)
def get_security(security_id: str, service: BackendIdentityService = Depends(get_identity_service)) -> SecurityResponse:
    row = service.get_security(security_id)
    if row is None:
        raise HTTPException(status_code=404, detail="security_id not found")
    return SecurityResponse(**row)


@router.get("/companies/{company_id}/securities", response_model=list[SecurityResponse])
def list_company_securities(company_id: str, service: BackendIdentityService = Depends(get_identity_service)) -> list[SecurityResponse]:
    return [SecurityResponse(**row) for row in service.list_company_securities(company_id)]


@router.post("/listings", response_model=ListingResponse)
def create_listing(request: ListingCreateRequest, service: BackendIdentityService = Depends(get_identity_service)) -> ListingResponse:
    _ensure_internal_mutation_allowed()
    return ListingResponse(**service.create_listing(request))


@router.get("/listings/{listing_id}", response_model=ListingResponse)
def get_listing(listing_id: str, service: BackendIdentityService = Depends(get_identity_service)) -> ListingResponse:
    row = service.get_listing(listing_id)
    if row is None:
        raise HTTPException(status_code=404, detail="listing_id not found")
    return ListingResponse(**row)


@router.get("/securities/{security_id}/listings", response_model=list[ListingResponse])
def list_security_listings(security_id: str, service: BackendIdentityService = Depends(get_identity_service)) -> list[ListingResponse]:
    return [ListingResponse(**row) for row in service.list_security_listings(security_id)]


@router.post("/identifiers")
def add_identifier(request: IdentifierCreateRequest, service: BackendIdentityService = Depends(get_identity_service)) -> dict:
    _ensure_internal_mutation_allowed()
    service.add_identifier(request)
    return {"ok": True}


@router.post("/relationships")
def add_relationship(request: RelationshipCreateRequest, service: BackendIdentityService = Depends(get_identity_service)) -> dict:
    _ensure_internal_mutation_allowed()
    service.add_relationship(request)
    return {"ok": True}


@router.post("/resolve", response_model=ResolutionResponse)
def resolve_identity(request: ResolutionRequest, service: BackendIdentityService = Depends(get_identity_service)) -> ResolutionResponse:
    return ResolutionResponse(**service.resolve(request))


@router.get("/resolution-issues", response_model=list[ResolutionIssueResponse])
def list_resolution_issues(
    limit: int = Query(default=100, ge=1, le=1000),
    service: BackendIdentityService = Depends(get_identity_service),
) -> list[ResolutionIssueResponse]:
    return [ResolutionIssueResponse(**row) for row in service.unresolved_issues(limit)]


@router.get("/shadow/diagnostics", response_model=ShadowIdentityDiagnosticsResponse)
def shadow_diagnostics(service: BackendIdentityService = Depends(get_identity_service)) -> ShadowIdentityDiagnosticsResponse:
    if settings.env.lower() not in {"dev", "test"}:
        return ShadowIdentityDiagnosticsResponse(enabled=False, checked_records=0, unresolved_records=0, items=[])
    return ShadowIdentityDiagnosticsResponse(**build_shadow_identity_diagnostics(service))
