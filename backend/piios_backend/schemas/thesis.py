from pydantic import BaseModel, Field

from piios_backend.schemas.enums import Bucket, RecommendationStatus


class InvestmentThesis(BaseModel):
    thesis_id: str
    ticker: str
    asset_name: str
    theme: str
    bucket: Bucket
    thesis: str
    bull_case: str
    bear_case: str
    why_now: str
    why_not_now: str
    invalidation_trigger: str
    valuation_notes: str
    expected_holding_period: str
    source_documents: list[str]
    confidence_score: float = Field(ge=0, le=100)
    status: RecommendationStatus
    created_at: str
    updated_at: str


class ThesisCreateRequest(BaseModel):
    ticker: str
    asset_name: str
    theme: str
    bucket: Bucket
    thesis: str
    bull_case: str
    bear_case: str
    why_now: str
    why_not_now: str
    invalidation_trigger: str
    valuation_notes: str
    expected_holding_period: str
    source_documents: list[str]
    confidence_score: float = Field(ge=0, le=100)


class ThesisStatusUpdateRequest(BaseModel):
    status: RecommendationStatus
