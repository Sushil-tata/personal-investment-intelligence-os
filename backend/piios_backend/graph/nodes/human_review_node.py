def human_review_node(state: dict) -> dict:
    approved = bool(state.get("human_approved", False))
    status = "accepted" if approved else "rejected"
    return {
        "status": status,
        "node_outputs": state.get("node_outputs", []) + [{"node": "human_review_node", "output": {"approved": approved, "status": status}}],
    }
