def portfolio_context_node(state: dict) -> dict:
    output = {"bucket_alignment": "Strategic Alpha", "concentration_ok": True}
    return {"portfolio_context": output, "node_outputs": state.get("node_outputs", []) + [{"node": "portfolio_context_node", "output": output}]}
