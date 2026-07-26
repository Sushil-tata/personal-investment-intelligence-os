import uuid

from langgraph.graph import END, StateGraph

from piios_backend.graph.nodes.bear_case_node import bear_case_node
from piios_backend.graph.nodes.human_review_node import human_review_node
from piios_backend.graph.nodes.portfolio_context_node import portfolio_context_node
from piios_backend.graph.nodes.portfolio_fit_node import portfolio_fit_node
from piios_backend.graph.nodes.recommendation_node import recommendation_node
from piios_backend.graph.nodes.research_ingestion_node import research_ingestion_node
from piios_backend.graph.nodes.risk_check_node import risk_check_node
from piios_backend.graph.nodes.source_credibility_node import source_credibility_node
from piios_backend.graph.nodes.thesis_generation_node import thesis_generation_node
from piios_backend.graph.state import GraphState
from piios_backend.services.graph_persistence import GraphPersistence


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("portfolio_context_node", portfolio_context_node)
    graph.add_node("research_ingestion_node", research_ingestion_node)
    graph.add_node("source_credibility_node", source_credibility_node)
    graph.add_node("thesis_generation_node", thesis_generation_node)
    graph.add_node("bear_case_node", bear_case_node)
    graph.add_node("portfolio_fit_node", portfolio_fit_node)
    graph.add_node("risk_check_node", risk_check_node)
    graph.add_node("recommendation_node", recommendation_node)
    graph.add_node("human_review_node", human_review_node)

    graph.set_entry_point("portfolio_context_node")
    graph.add_edge("portfolio_context_node", "research_ingestion_node")
    graph.add_edge("research_ingestion_node", "source_credibility_node")
    graph.add_edge("source_credibility_node", "thesis_generation_node")
    graph.add_edge("thesis_generation_node", "bear_case_node")
    graph.add_edge("bear_case_node", "portfolio_fit_node")
    graph.add_edge("portfolio_fit_node", "risk_check_node")
    graph.add_edge("risk_check_node", "recommendation_node")
    graph.add_edge("recommendation_node", "human_review_node")
    graph.add_edge("human_review_node", END)
    return graph.compile()


graph_app = build_graph()


class GraphRunRegistry:
    def __init__(self) -> None:
        self.persistence = GraphPersistence()

    def run(self, ticker: str, approved: bool, requested_by: str = "system") -> dict:
        run_id = str(uuid.uuid4())
        initial = {"run_id": run_id, "ticker": ticker, "status": "running", "human_approved": approved, "node_outputs": []}
        result = graph_app.invoke(initial)
        self.persistence.persist_run(result, requested_by)
        return result

    def status(self, run_id: str) -> dict | None:
        return self.persistence.fetch_run(run_id)


graph_registry = GraphRunRegistry()
