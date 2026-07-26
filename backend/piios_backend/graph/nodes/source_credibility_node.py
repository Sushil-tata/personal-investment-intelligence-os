def source_credibility_node(state: dict) -> dict:
    output = {"credibility_score": 78}
    return {"source_credibility": output, "node_outputs": state.get("node_outputs", []) + [{"node": "source_credibility_node", "output": output}]}
