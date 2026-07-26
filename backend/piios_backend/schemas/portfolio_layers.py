from pydantic import BaseModel


class FamilyPortfolioMember(BaseModel):
    member_id: str
    member_name: str
    relation: str
    base_currency: str


class FamilyPortfolioResponse(BaseModel):
    households: list[FamilyPortfolioMember]


class NetWorthItem(BaseModel):
    category: str
    value: float


class NetWorthResponse(BaseModel):
    owner: str
    total_assets: float
    total_liabilities: float
    net_worth: float
    breakdown: list[NetWorthItem]


class AllocationItem(BaseModel):
    dimension: str
    key: str
    market_value: float
    percentage: float


class AllocationResponse(BaseModel):
    total_value: float
    items: list[AllocationItem]


class CurrencyExposureItem(BaseModel):
    currency: str
    market_value: float
    percentage: float


class CurrencyExposureResponse(BaseModel):
    total_value: float
    items: list[CurrencyExposureItem]


class IPSConstraint(BaseModel):
    constraint_id: str
    name: str
    rule_type: str
    threshold_value: float
    severity: str
    enabled: bool


class IPSConstraintResponse(BaseModel):
    constraints: list[IPSConstraint]


class InstrumentMasterItem(BaseModel):
    instrument_id: str
    ticker: str
    name: str
    asset_class: str
    currency: str
    exchange: str
    data_source: str


class InstrumentMasterResponse(BaseModel):
    instruments: list[InstrumentMasterItem]


class DataTrustSourceItem(BaseModel):
    source_id: str
    source_name: str
    trust_tier: str
    score: float
    freshness_sla_hours: int


class DataTrustHierarchyResponse(BaseModel):
    hierarchy: list[DataTrustSourceItem]
