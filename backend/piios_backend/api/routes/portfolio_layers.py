from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from piios_backend.core.config import settings
from piios_backend.core.database import get_session
from piios_backend.schemas.portfolio_layers import (
    AllocationResponse,
    CurrencyExposureResponse,
    DataTrustHierarchyResponse,
    FamilyPortfolioResponse,
    IPSConstraintResponse,
    InstrumentMasterResponse,
    NetWorthResponse,
)
from piios_backend.services.portfolio_dual_run import get_last_dual_run_report, maybe_run_dual_run, run_dual_run_verification
from piios_backend.services.portfolio_layers import PortfolioLayersService


router = APIRouter(tags=["portfolio-layers"])


def get_layers_service(session: Session = Depends(get_session)) -> PortfolioLayersService:
    return PortfolioLayersService(session)


@router.get("/family/portfolios", response_model=FamilyPortfolioResponse)
def get_family_registry(service: PortfolioLayersService = Depends(get_layers_service)) -> FamilyPortfolioResponse:
    return service.family_registry()


@router.get("/portfolio/net-worth", response_model=NetWorthResponse)
def get_net_worth(service: PortfolioLayersService = Depends(get_layers_service)) -> NetWorthResponse:
    maybe_run_dual_run("GET /portfolio/net-worth")
    return service.net_worth()


@router.get("/portfolio/allocation", response_model=AllocationResponse)
def get_asset_allocation(
    dimension: str = Query(default="asset_class"),
    service: PortfolioLayersService = Depends(get_layers_service),
) -> AllocationResponse:
    maybe_run_dual_run(f"GET /portfolio/allocation?dimension={dimension}")
    return service.allocation(dimension)


@router.get("/portfolio/currency-exposure", response_model=CurrencyExposureResponse)
def get_currency_exposure(service: PortfolioLayersService = Depends(get_layers_service)) -> CurrencyExposureResponse:
    maybe_run_dual_run("GET /portfolio/currency-exposure")
    return service.currency_exposure()


@router.post("/portfolio/dual-run/verify")
def run_portfolio_dual_run_verification() -> dict:
    if settings.env.lower() not in {"dev", "test"}:
        return {"enabled": False, "reason": "dual-run verification is restricted to dev/test"}
    return {"enabled": settings.portfolio_dual_run_enabled, "report": run_dual_run_verification()}


@router.get("/portfolio/dual-run/last")
def get_portfolio_dual_run_report() -> dict:
    if settings.env.lower() not in {"dev", "test"}:
        return {"enabled": False, "reason": "dual-run verification is restricted to dev/test"}
    return {"enabled": settings.portfolio_dual_run_enabled, "report": get_last_dual_run_report()}


@router.get("/ips/constraints", response_model=IPSConstraintResponse)
def get_ips_constraints(service: PortfolioLayersService = Depends(get_layers_service)) -> IPSConstraintResponse:
    return service.ips_constraints()


@router.get("/instruments", response_model=InstrumentMasterResponse)
def get_instrument_master(service: PortfolioLayersService = Depends(get_layers_service)) -> InstrumentMasterResponse:
    return service.instrument_master()


@router.get("/data-trust/hierarchy", response_model=DataTrustHierarchyResponse)
def get_data_trust_hierarchy(service: PortfolioLayersService = Depends(get_layers_service)) -> DataTrustHierarchyResponse:
    return service.data_trust_hierarchy()
