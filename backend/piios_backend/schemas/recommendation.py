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


class InvestorMandateOverride(BaseModel):
    india_exposure_inr: float | None = Field(default=None, ge=0)
    usd_diversification_priority: bool | None = None
    horizon_years_min: int | None = Field(default=None, ge=1)
    horizon_years_max: int | None = Field(default=None, ge=1)
    risk_profile: str | None = None
    quality_compounders_preference: bool | None = None
    strategic_upside_preference: bool | None = None
    target_position_count_min: int | None = Field(default=None, ge=1)
    target_position_count_max: int | None = Field(default=None, ge=1)
    monthly_contribution_usd: float | None = Field(default=None, ge=0)


class RecommendationGenerateRequest(BaseModel):
    portfolio_snapshot_id: str | None = None
    investable_amount: float = Field(default=5000.0, gt=0)
    as_of_date: str | None = None
    market_data_mode: str | None = Field(default=None, description="auto|live|cached|development_seed")
    use_demo_portfolio: bool = False
    mandate_override: InvestorMandateOverride | None = None


class RecommendationScoreComponent(BaseModel):
    name: str
    value: float | None
    weight: float = Field(ge=0, le=1)
    status: str
    explanation: str


class RecommendationEvidence(BaseModel):
    code: str
    detail: str
    source: str


class RecommendationLimitation(BaseModel):
    code: str
    detail: str
    severity: str = "INFO"


class PortfolioObservation(BaseModel):
    code: str
    severity: str
    detail: str


class AllocationRecommendation(BaseModel):
    action: str
    ticker: str
    instrument_name: str
    portfolio_role: str
    current_value: float = Field(ge=0)
    current_weight: float = Field(ge=0, le=1)
    proposed_allocation: float = Field(ge=0)
    proposed_total_value: float = Field(ge=0)
    post_weight: float = Field(ge=0, le=1)
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    market_data_provider: str
    market_data_mode: str
    market_data_as_of: str | None = None
    is_stale: bool = False
    fallback_reason: str | None = None
    seeded_input: bool = False
    rationale: str
    diversification_contribution: str
    risks: list[str]
    unavailable_inputs: list[str]
    conditions_to_change: list[str]
    components: list[RecommendationScoreComponent]
    evidence: list[RecommendationEvidence]


class PortfolioRecommendationResponse(BaseModel):
    recommendation_id: str
    status: str
    as_of_timestamp: str
    market_data_provider: str
    market_data_mode: str
    input_freshness: str
    investable_amount: float = Field(gt=0)
    allocation_total: float = Field(ge=0)
    allocation_difference: float
    overall_confidence: float = Field(ge=0, le=1)
    advisory_only: bool = True
    portfolio_observations: list[PortfolioObservation]
    recommendations: list[AllocationRecommendation]
    assumptions: list[str]
    limitations: list[RecommendationLimitation]

