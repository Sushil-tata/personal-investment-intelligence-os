from pydantic import BaseModel, Field

from piios_backend.schemas.common import Bucket, SourceLink


class Holding(BaseModel):
    ticker: str
    name: str
    quantity: float
    value: float
    bucket: Bucket | None = None


class WatchlistItem(BaseModel):
    ticker: str
    thesis: str
    bucket: Bucket | None = None


class Recommendation(BaseModel):
    ticker: str
    bucket: Bucket | None = None
    bull_case: str
    bear_case: str
    why_now: str
    why_not_now: str
    thesis_invalidation_trigger: str
    position_size_suggestion: str
    time_horizon: str
    confidence_score: float = Field(ge=0, le=100)
    data_freshness_timestamp: str
    source_links: list[SourceLink] = []
    rationale: str
    model_version: str
    data_source: str
    advisory_only: bool = True


class TacticalSignal(BaseModel):
    ticker: str
    bucket: Bucket | None = Bucket.TACTICAL_OPPORTUNITIES
    signal: str
    risk_reward: float
    advisory_only: bool = True


class JournalEntry(BaseModel):
    ticker: str
    note: str
    outcome: str
    bucket: Bucket | None = None


class PortfolioSnapshot(BaseModel):
    as_of: str
    total_value: float
    holdings: list[Holding]
