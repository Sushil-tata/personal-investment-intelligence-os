from fastapi import APIRouter

from piios_backend.core.config import settings
from piios_backend.schemas.common import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", product="PIIOS", version=settings.app_version)
