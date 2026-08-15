from fastapi import APIRouter, Query, UploadFile
from fastapi import HTTPException
from fastapi.responses import PlainTextResponse

from piios_backend.schemas.operations import CSVImportResponse
from piios_backend.schemas.recommendation import (
    PortfolioRecommendationResponse,
    Recommendation,
    RecommendationGenerateRequest,
    RecommendationQueueResponse,
    RecommendationStatusUpdateRequest,
    TopRecommendation,
)
from piios_backend.services.csv_io import from_csv, to_csv
from piios_backend.services.in_memory_store import store
from piios_backend.services.live_feeds import live_feeds
from piios_backend.services.recommendation_mvp import assert_live_market_data_mode, recommendation_mvp_service


router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=list[Recommendation])
def get_recommendations() -> list[Recommendation]:
    live_feeds.refresh_recommendations(store.recommendations)
    return store.visible_recommendations()


@router.post("/import", response_model=CSVImportResponse)
async def import_recommendations(file: UploadFile) -> CSVImportResponse:
    parsed = from_csv((await file.read()).decode("utf-8"))
    return CSVImportResponse(imported_rows=len(parsed))


@router.get("/export", response_class=PlainTextResponse)
def export_recommendations() -> str:
    live_feeds.refresh_recommendations(store.recommendations)
    return to_csv([row.model_dump() for row in store.recommendations])


@router.get("/queue", response_model=RecommendationQueueResponse)
def recommendation_queue() -> RecommendationQueueResponse:
    live_feeds.refresh_recommendations(store.recommendations)
    return RecommendationQueueResponse(items=store.recommendation_queue())


@router.get("/top", response_model=list[TopRecommendation])
def top_recommendations(
    limit: int = Query(default=50, ge=1, le=100),
    sector: str | None = Query(default=None),
    market: str | None = Query(default=None),
) -> list[TopRecommendation]:
    return live_feeds.top_recommendations(limit=limit, sector=sector, market=market)


@router.post("/generate", response_model=PortfolioRecommendationResponse)
def generate_recommendation(request: RecommendationGenerateRequest) -> PortfolioRecommendationResponse:
    if request.use_demo_portfolio:
        raise HTTPException(status_code=422, detail="use_demo_portfolio is only supported via /recommendations/demo")
    if (request.market_data_mode or "").strip().lower() == "development_seed":
        raise HTTPException(status_code=422, detail="development_seed mode is only supported via /recommendations/demo")
    try:
        assert_live_market_data_mode(request.market_data_mode, caller="POST /recommendations/generate")
        return recommendation_mvp_service.generate(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/demo", response_model=PortfolioRecommendationResponse)
def generate_recommendation_demo() -> PortfolioRecommendationResponse:
    return recommendation_mvp_service.generate(
        RecommendationGenerateRequest(
            investable_amount=5000.0,
            market_data_mode="development_seed",
            use_demo_portfolio=True,
        )
    )


@router.patch("/{recommendation_id}/status", response_model=Recommendation)
def update_recommendation_status(recommendation_id: str, request: RecommendationStatusUpdateRequest) -> Recommendation:
    updated = store.update_recommendation_status(recommendation_id, request.status, request.approved_by)
    if not updated:
        raise HTTPException(status_code=404, detail="recommendation_id not found")
    return updated
