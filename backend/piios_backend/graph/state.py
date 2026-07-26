from typing import Literal, TypedDict


class GraphState(TypedDict, total=False):
    run_id: str
    ticker: str
    status: Literal["running", "blocked", "review_pending", "accepted", "rejected"]
    portfolio_context: dict
    research_context: dict
    source_credibility: dict
    thesis: str
    bear_case: str
    portfolio_fit_passed: bool
    risk_check_passed: bool
    recommendation: dict
    human_approved: bool
    node_outputs: list[dict]
