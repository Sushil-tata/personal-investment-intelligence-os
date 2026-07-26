from pydantic import BaseModel, Field

from piios_backend.schemas.enums import Bucket, RecommendationStatus


class Recommendation(BaseModel):
    recommendation_id: str
    ticker: str
    thesis_id: str | None = None
    bucket: Bucket | None = None
    portfolio_bucket: Bucket
    bull_case: str
    bear_case: str
    why_now: str
    why_not_now: str
    thesis_invalidation_trigger: str
    position_size_suggestion: str
    time_horizon: str
    confidence_score: float = Field(ge=0, le=100)
    portfolio_fit_score: float = Field(ge=0, le=100)
    data_freshness_timestamp: str
    source_documents: list[str]
    source_links: list[str]
    rationale: str
    data_source: str
    model_version: str
    status: RecommendationStatus
    created_at: str
    updated_at: str
    approved_by: str | None = None
    advisory_only: bool = True


class TacticalSignal(BaseModel):
    signal_id: str
    ticker: str
    bucket: Bucket | None = Bucket.TACTICAL_OPPORTUNITIES
    status: str
    entry_zone: str
    invalidation: str
    target: str
    advisory_only: bool = True


class RecommendationStatusUpdateRequest(BaseModel):
    status: RecommendationStatus
    approved_by: str | None = None


class RecommendationQueueResponse(BaseModel):
    items: list[Recommendation]


class TopRecommendation(BaseModel):
    ticker: str
    sector: str
    score: float = Field(ge=0, le=100)
    daily_pct: float
    weekly_pct: float
    close: float
    volume_ratio: float
    recommended_action: str

