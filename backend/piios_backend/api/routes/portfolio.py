from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from piios_backend.schemas.portfolio import PortfolioDriftResponse, PortfolioSnapshot, PortfolioTargetsResponse
from piios_backend.services.csv_io import to_csv
from piios_backend.services.in_memory_store import store


router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=list[PortfolioSnapshot])
def get_portfolio() -> list[PortfolioSnapshot]:
    return store.snapshots


@router.get("/export", response_class=PlainTextResponse)
def export_portfolio() -> str:
    return to_csv([row.model_dump() for row in store.snapshots])


@router.get("/targets", response_model=PortfolioTargetsResponse)
def portfolio_targets() -> PortfolioTargetsResponse:
    return PortfolioTargetsResponse(targets=store.target_allocation.get("targets", {}), thresholds=store.drift_thresholds)


@router.get("/drift", response_model=PortfolioDriftResponse)
def portfolio_drift() -> PortfolioDriftResponse:
    return store.calculate_drift()
