import json
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session, select

from piios_backend.core.database import engine
from piios_backend.models.entities import GraphNodeOutput, GraphRun


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GraphPersistence:
    def __init__(self) -> None:
        self.file_path = Path(__file__).resolve().parents[2] / "data" / "mock" / "graph_runs_fallback.json"
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def persist_run(self, result: dict, requested_by: str) -> None:
        run_id = result["run_id"]
        try:
            with Session(engine) as session:
                run = GraphRun(
                    run_id=run_id,
                    ticker=result.get("ticker", "UNKNOWN"),
                    status=result.get("status", "unknown"),
                    requested_by=requested_by,
                    created_at=_now(),
                    updated_at=_now(),
                )
                session.add(run)
                for node in result.get("node_outputs", []):
                    session.add(
                        GraphNodeOutput(
                            run_id=run_id,
                            node_name=node.get("node", "unknown"),
                            output_json=json.dumps(node.get("output", {})),
                            timestamp=_now(),
                        )
                    )
                session.commit()
                return
        except Exception:
            self._persist_file(result, requested_by)

    def fetch_run(self, run_id: str) -> dict | None:
        try:
            with Session(engine) as session:
                run = session.exec(select(GraphRun).where(GraphRun.run_id == run_id)).first()
                if run:
                    outputs = session.exec(select(GraphNodeOutput).where(GraphNodeOutput.run_id == run_id)).all()
                    return {
                        "run_id": run.run_id,
                        "ticker": run.ticker,
                        "status": run.status,
                        "requested_by": run.requested_by,
                        "node_outputs": [
                            {"node": row.node_name, "output": json.loads(row.output_json)} for row in outputs
                        ],
                    }
        except Exception:
            pass
        return self._fetch_file(run_id)

    def _persist_file(self, result: dict, requested_by: str) -> None:
        existing = []
        if self.file_path.exists():
            existing = json.loads(self.file_path.read_text(encoding="utf-8"))
        payload = {
            "run_id": result["run_id"],
            "ticker": result.get("ticker"),
            "status": result.get("status"),
            "requested_by": requested_by,
            "node_outputs": result.get("node_outputs", []),
        }
        existing.append(payload)
        self.file_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    def _fetch_file(self, run_id: str) -> dict | None:
        if not self.file_path.exists():
            return None
        existing = json.loads(self.file_path.read_text(encoding="utf-8"))
        for row in existing:
            if row.get("run_id") == run_id:
                return row
        return None
