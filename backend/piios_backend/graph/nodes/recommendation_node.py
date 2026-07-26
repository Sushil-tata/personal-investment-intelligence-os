from datetime import datetime, timezone


def recommendation_node(state: dict) -> dict:
    fit = state.get("portfolio_fit_passed", False)
    risk = state.get("risk_check_passed", False)
    if not (fit and risk):
        return {
            "status": "blocked",
            "node_outputs": state.get("node_outputs", [])
            + [{"node": "recommendation_node", "output": {"blocked": True, "reason": "fit_or_risk_failed"}}],
        }
    recommendation = {
        "ticker": state.get("ticker", "UNKNOWN"),
        "bull_case": state.get("thesis", ""),
        "bear_case": state.get("bear_case", ""),
        "why_now": "Setup quality and evidence score pass threshold",
        "why_not_now": "Macro volatility can invalidate timing",
        "thesis_invalidation_trigger": "Loss of earnings momentum",
        "position_size_suggestion": "1-2% starter",
        "time_horizon": "2-5 years",
        "confidence_score": 72,
        "data_freshness_timestamp": datetime.now(timezone.utc).isoformat(),
        "source_links": ["https://example.com"],
        "advisory_only": True,
    }
    return {
        "recommendation": recommendation,
        "status": "review_pending",
        "node_outputs": state.get("node_outputs", []) + [{"node": "recommendation_node", "output": recommendation}],
    }
