from fastapi import APIRouter, HTTPException

from piios_backend.graph.workflow import graph_registry
from piios_backend.schemas.graph import GraphRunRequest, GraphRunResponse, GraphStatusResponse


router = APIRouter(prefix="/graph", tags=["graph"])


@router.post("/run", response_model=GraphRunResponse)
def run_graph(request: GraphRunRequest) -> GraphRunResponse:
    result = graph_registry.run(ticker=request.ticker, approved=request.approve, requested_by=request.requested_by)
    return GraphRunResponse(
        run_id=result["run_id"],
        status=result["status"],
        recommendation_available=bool(result.get("recommendation")) and result.get("status") in {"review_pending", "accepted"},
    )


@router.get("/status", response_model=GraphStatusResponse)
def graph_status(run_id: str) -> GraphStatusResponse:
    run = graph_registry.status(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run_id not found")
    return GraphStatusResponse(run_id=run_id, status=run.get("status", "unknown"), node_outputs=run.get("node_outputs", []))
