import json

from piios_backend.graph.workflow import graph_registry


def _force_fallback(monkeypatch):
    # Force fallback writer path deterministically for test coverage.
    monkeypatch.setattr(
        "piios_backend.services.graph_persistence.Session",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("forced-db-failure")),
    )


def test_graph_blocks_without_human_approval(tmp_path, monkeypatch) -> None:
    fallback_file = tmp_path / "graph_runs_fallback_workflow.json"
    monkeypatch.setattr(graph_registry.persistence, "file_path", fallback_file)
    _force_fallback(monkeypatch)

    result = graph_registry.run("NVDA", approved=False)
    assert result["status"] == "rejected"

    payload = json.loads(fallback_file.read_text(encoding="utf-8"))
    assert len(payload) >= 1
    assert payload[-1]["run_id"] == result["run_id"]
    assert payload[-1]["status"] == "rejected"


def test_graph_accepts_with_human_approval(tmp_path, monkeypatch) -> None:
    fallback_file = tmp_path / "graph_runs_fallback_workflow.json"
    monkeypatch.setattr(graph_registry.persistence, "file_path", fallback_file)
    _force_fallback(monkeypatch)

    result = graph_registry.run("NVDA", approved=True)
    assert result["status"] == "accepted"

    payload = json.loads(fallback_file.read_text(encoding="utf-8"))
    assert len(payload) >= 1
    assert payload[-1]["run_id"] == result["run_id"]
    assert payload[-1]["status"] == "accepted"
