def bear_case_node(state: dict) -> dict:
    bear = "Valuation compression in macro risk-off"
    return {"bear_case": bear, "node_outputs": state.get("node_outputs", []) + [{"node": "bear_case_node", "output": {"bear_case": bear}}]}
