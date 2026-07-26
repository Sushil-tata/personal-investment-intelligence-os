from fastapi import APIRouter

from piios_backend.core.config import settings
from piios_backend.schemas.operations import ResearchFeedResponse
from piios_backend.services.live_feeds import live_feeds


router = APIRouter(prefix="/research", tags=["research"])


@router.get("", response_model=ResearchFeedResponse)
def get_research() -> ResearchFeedResponse:
    return live_feeds.build_research_feed(settings.live_tickers_list)
