from fastapi import APIRouter, Query

from piios_backend.core.config import settings
from piios_backend.services.live_feeds import live_feeds


router = APIRouter(prefix="/scores", tags=["scores"])


@router.get("")
def get_scores() -> dict:
    return live_feeds.build_scores(settings.live_tickers_list)


@router.get("/explainability")
def get_score_explainability(
    limit: int = Query(default=25, ge=1, le=100),
    sector: str | None = Query(default=None),
) -> dict:
    return live_feeds.build_score_explainability(limit=limit, sector=sector)
