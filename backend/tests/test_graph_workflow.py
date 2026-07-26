from piios_backend.graph.workflow import graph_registry


def test_graph_blocks_without_human_approval() -> None:
    result = graph_registry.run("NVDA", approved=False)
    assert result["status"] == "rejected"


def test_graph_accepts_with_human_approval() -> None:
    result = graph_registry.run("NVDA", approved=True)
    assert result["status"] == "accepted"
