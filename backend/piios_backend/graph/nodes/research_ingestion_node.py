def research_ingestion_node(state: dict) -> dict:
    output = {"docs": 3, "freshness": "recent"}
    return {"research_context": output, "node_outputs": state.get("node_outputs", []) + [{"node": "research_ingestion_node", "output": output}]}
