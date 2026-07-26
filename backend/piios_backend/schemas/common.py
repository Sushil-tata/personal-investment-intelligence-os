from pydantic import BaseModel


class AdvisoryResponse(BaseModel):
    advisory_only: bool = True


class HealthResponse(BaseModel):
    status: str
    product: str
from enum import Enum

from pydantic import BaseModel, HttpUrl


class Bucket(str, Enum):
    EDUCATION = "Education"
    RETIREMENT = "Retirement"
    STRATEGIC_ALPHA = "Strategic Alpha"
    TACTICAL_OPPORTUNITIES = "Tactical Opportunities"


class SourceLink(BaseModel):
    label: str
    url: HttpUrl


ADVISORY_BOUNDARY = (
    "Advisory-only and research-only. No broker integration, no order placement, "
    "no auto-trading, no margin/leverage execution, and no broker credential storage."
)
