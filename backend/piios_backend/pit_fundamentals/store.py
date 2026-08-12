from __future__ import annotations

from pathlib import Path
import json
import sqlite3

import pandas as pd

from .models import FundamentalObservation, JoinAuditRow, SourceQualityRecord


class PitProofStore:
    def __init__(self, output_root: str | Path) -> None:
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.output_root / "pit_fundamentals_proof.db"

    def init(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    ingest_hash TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS failures (
                    ticker TEXT,
                    failure TEXT,
                    detail TEXT
                )
                """
            )

    def write_observations(self, observations: list[FundamentalObservation]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            for obs in observations:
                row = obs.to_row()
                conn.execute(
                    "INSERT OR REPLACE INTO observations (ingest_hash, payload_json) VALUES (?, ?)",
                    (obs.ingest_hash, json.dumps(row)),
                )

    def write_failures(self, failures: list[dict[str, str]]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM failures")
            for row in failures:
                conn.execute(
                    "INSERT INTO failures (ticker, failure, detail) VALUES (?, ?, ?)",
                    (row.get("ticker"), row.get("failure"), row.get("detail")),
                )

    def write_csv_outputs(
        self,
        *,
        company_coverage: pd.DataFrame,
        metric_coverage: pd.DataFrame,
        join_audit: list[JoinAuditRow],
        source_quality: list[SourceQualityRecord],
        summary: dict,
    ) -> None:
        company_coverage.to_csv(self.output_root / "company_coverage.csv", index=False)
        metric_coverage.to_csv(self.output_root / "metric_coverage.csv", index=False)
        pd.DataFrame([row.to_row() for row in join_audit]).to_csv(self.output_root / "manual_join_audit.csv", index=False)
        pd.DataFrame([row.__dict__ for row in source_quality]).to_csv(self.output_root / "source_quality.csv", index=False)
        summary_path = self.output_root / "pit_data_proof_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2))
        with sqlite3.connect(self.db_path) as conn:
            failures_df = pd.read_sql_query("SELECT ticker, failure, detail FROM failures", conn)
        failures_df.to_csv(self.output_root / "failure_log.csv", index=False)

    def load_observations_dataframe(self) -> pd.DataFrame:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT payload_json FROM observations").fetchall()
        decoded = [json.loads(row[0]) for row in rows]
        return pd.DataFrame(decoded)
