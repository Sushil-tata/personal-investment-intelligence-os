def portfolio_fit_node(state: dict) -> dict:
    passed = bool(state.get("portfolio_context", {}).get("concentration_ok", False))
    return {"portfolio_fit_passed": passed, "node_outputs": state.get("node_outputs", []) + [{"node": "portfolio_fit_node", "output": {"passed": passed}}]}
