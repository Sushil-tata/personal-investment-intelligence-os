def thesis_generation_node(state: dict) -> dict:
    thesis = "Quality growth with portfolio diversification benefit"
    return {"thesis": thesis, "node_outputs": state.get("node_outputs", []) + [{"node": "thesis_generation_node", "output": {"thesis": thesis}}]}
