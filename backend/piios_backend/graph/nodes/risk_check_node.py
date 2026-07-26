def risk_check_node(state: dict) -> dict:
    passed = True
    return {"risk_check_passed": passed, "node_outputs": state.get("node_outputs", []) + [{"node": "risk_check_node", "output": {"passed": passed}}]}
