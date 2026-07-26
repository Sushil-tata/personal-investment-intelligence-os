from pydantic import BaseModel

from piios_backend.schemas.enums import Bucket


class Holding(BaseModel):
    holding_id: str
    ticker: str
    name: str
    quantity: float
    market_value: float
    bucket: Bucket | None = None
    geography: str = "Global"
    currency: str = "USD"
    asset_class: str = "Equity"
    sector: str = "Multi-Sector"
    theme: str = "Core"


class WatchlistIdea(BaseModel):
    watchlist_id: str
    ticker: str
    note: str
    bucket: Bucket | None = None


class PortfolioSnapshot(BaseModel):
    snapshot_id: str
    owner: str
    total_value: float
    holdings: list[Holding]


class DriftItem(BaseModel):
    dimension: str
    key: str
    target_percentage: float
    actual_percentage: float
    drift_amount: float
    drift_percentage: float
    severity: str
    recommended_action: str
    advisory_only: bool = True


class PortfolioDriftResponse(BaseModel):
    generated_at: str
    items: list[DriftItem]


class PortfolioTargetsResponse(BaseModel):
    targets: dict
    thresholds: dict
