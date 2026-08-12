from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
from typing import Any


def canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ProspectiveDecisionRecord:
    decision_id: str
    strategy_id: str
    run_timestamp: str
    as_of_date: str
    ticker: str
    market: str
    ranking_position: int
    action: str
    proposed_allocation: float | None
    quality_score: float | None
    growth_score: float | None
    valuation_score: float | None
    momentum_score: float | None
    risk_score: float | None
    discovery_score: float | None
    attractiveness_score: float | None
    suitability_score: float | None
    combined_score: float | None
    evidence_coverage: float | None
    confidence: float | None
    reason_codes: list[str]
    factor_trace_reference: dict[str, Any] | None
    engine_version: str
    git_commit_sha: str
    config_version: str
    universe_version: str
    market_provider: str | None
    fundamental_provider: str | None
    market_source_retrieval_timestamp: str | None
    fundamental_source_retrieval_timestamp: str | None
    market_snapshot_reference: dict[str, Any] | None
    fundamental_snapshot_reference: dict[str, Any] | None
    market_snapshot_hash: str | None
    fundamental_snapshot_hash: str | None
    factor_payload_hash: str | None

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["reason_codes"] = json.dumps(self.reason_codes, ensure_ascii=True)
        row["factor_trace_reference"] = json.dumps(self.factor_trace_reference or {}, sort_keys=True, ensure_ascii=True)
        row["market_snapshot_reference"] = json.dumps(self.market_snapshot_reference or {}, sort_keys=True, ensure_ascii=True)
        row["fundamental_snapshot_reference"] = json.dumps(self.fundamental_snapshot_reference or {}, sort_keys=True, ensure_ascii=True)
        return row


def infer_market(ticker: str) -> str:
    if ticker.endswith(".NS"):
        return "India"
    if ticker.endswith(".SI"):
        return "Singapore"
    return "US"


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"
