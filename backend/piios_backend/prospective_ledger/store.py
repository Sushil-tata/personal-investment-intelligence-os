from __future__ import annotations

from pathlib import Path
import sqlite3

from .models import ProspectiveDecisionRecord


class ProspectiveLedgerStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def init(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS prospective_decisions (
                    decision_id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    run_timestamp TEXT NOT NULL,
                    as_of_date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    market TEXT NOT NULL,
                    ranking_position INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    proposed_allocation REAL,
                    quality_score REAL,
                    growth_score REAL,
                    valuation_score REAL,
                    momentum_score REAL,
                    risk_score REAL,
                    discovery_score REAL,
                    attractiveness_score REAL,
                    suitability_score REAL,
                    combined_score REAL,
                    evidence_coverage REAL,
                    confidence REAL,
                    reason_codes TEXT NOT NULL,
                    factor_trace_reference TEXT NOT NULL,
                    engine_version TEXT NOT NULL,
                    git_commit_sha TEXT NOT NULL,
                    config_version TEXT NOT NULL,
                    universe_version TEXT NOT NULL,
                    market_provider TEXT,
                    fundamental_provider TEXT,
                    market_source_retrieval_timestamp TEXT,
                    fundamental_source_retrieval_timestamp TEXT,
                    market_snapshot_reference TEXT NOT NULL,
                    fundamental_snapshot_reference TEXT NOT NULL,
                    market_snapshot_hash TEXT,
                    fundamental_snapshot_hash TEXT,
                    factor_payload_hash TEXT
                )
                """
            )

    def append(self, records: list[ProspectiveDecisionRecord]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            for record in records:
                row = record.to_row()
                conn.execute(
                    """
                    INSERT INTO prospective_decisions (
                        decision_id,
                        strategy_id,
                        run_timestamp,
                        as_of_date,
                        ticker,
                        market,
                        ranking_position,
                        action,
                        proposed_allocation,
                        quality_score,
                        growth_score,
                        valuation_score,
                        momentum_score,
                        risk_score,
                        discovery_score,
                        attractiveness_score,
                        suitability_score,
                        combined_score,
                        evidence_coverage,
                        confidence,
                        reason_codes,
                        factor_trace_reference,
                        engine_version,
                        git_commit_sha,
                        config_version,
                        universe_version,
                        market_provider,
                        fundamental_provider,
                        market_source_retrieval_timestamp,
                        fundamental_source_retrieval_timestamp,
                        market_snapshot_reference,
                        fundamental_snapshot_reference,
                        market_snapshot_hash,
                        fundamental_snapshot_hash,
                        factor_payload_hash
                    ) VALUES (
                        :decision_id,
                        :strategy_id,
                        :run_timestamp,
                        :as_of_date,
                        :ticker,
                        :market,
                        :ranking_position,
                        :action,
                        :proposed_allocation,
                        :quality_score,
                        :growth_score,
                        :valuation_score,
                        :momentum_score,
                        :risk_score,
                        :discovery_score,
                        :attractiveness_score,
                        :suitability_score,
                        :combined_score,
                        :evidence_coverage,
                        :confidence,
                        :reason_codes,
                        :factor_trace_reference,
                        :engine_version,
                        :git_commit_sha,
                        :config_version,
                        :universe_version,
                        :market_provider,
                        :fundamental_provider,
                        :market_source_retrieval_timestamp,
                        :fundamental_source_retrieval_timestamp,
                        :market_snapshot_reference,
                        :fundamental_snapshot_reference,
                        :market_snapshot_hash,
                        :fundamental_snapshot_hash,
                        :factor_payload_hash
                    )
                    """,
                    row,
                )

    def count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            value = conn.execute("SELECT COUNT(*) FROM prospective_decisions").fetchone()
        return int(value[0] if value else 0)
