from pydantic import BaseModel


class GraphRunRequest(BaseModel):
    ticker: str
    requested_by: str
    approve: bool = False


class GraphRunResponse(BaseModel):
    run_id: str
    status: str
    recommendation_available: bool


class GraphStatusResponse(BaseModel):
    run_id: str
    status: str
    node_outputs: list[dict]
