from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
import sqlite3

from .models import APPLICATION_RETRIEVAL_TIMESTAMP, CoreDecision, StrategyEvent, canonical_hash


def load_core_decisions(db_path: Path, strategy_id: str = "PIIOS_CORE") -> list[CoreDecision]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT decision_id, strategy_id, as_of_date, run_timestamp, ticker, action,
                   COALESCE(proposed_allocation, 0.0),
                   market_source_retrieval_timestamp,
                   fundamental_source_retrieval_timestamp
            FROM prospective_decisions
            WHERE strategy_id = ?
            ORDER BY as_of_date ASC, ranking_position ASC
            """,
            (strategy_id,),
        ).fetchall()

    out: list[CoreDecision] = []
    for row in rows:
        out.append(
            CoreDecision(
                decision_id=str(row[0]),
                strategy_id=str(row[1]),
                as_of_date=str(row[2]),
                run_timestamp=str(row[3]),
                ticker=str(row[4]),
                action=str(row[5]),
                proposed_allocation=float(row[6] or 0.0),
                market_source_retrieval_timestamp=(None if row[7] is None else str(row[7])),
                fundamental_source_retrieval_timestamp=(None if row[8] is None else str(row[8])),
                fundamental_timestamp_semantics=APPLICATION_RETRIEVAL_TIMESTAMP,
            )
        )
    return out


def decisions_to_events(decisions: list[CoreDecision]) -> list[StrategyEvent]:
    grouped: dict[str, list[CoreDecision]] = defaultdict(list)
    for decision in decisions:
        grouped[decision.as_of_date].append(decision)

    events: list[StrategyEvent] = []
    for as_of_date in sorted(grouped.keys()):
        batch = grouped[as_of_date]
        allocations = {
            d.ticker: d.proposed_allocation
            for d in batch
            if d.action in {"BUY", "ADD", "RESEARCH"} and d.proposed_allocation > 0.0
        }
        payload = {
            "as_of_date": as_of_date,
            "allocations": allocations,
            "decision_ids": [d.decision_id for d in batch],
            "fundamental_timestamp_semantics": APPLICATION_RETRIEVAL_TIMESTAMP,
            "market_source_retrieval_timestamps": sorted(
                {d.market_source_retrieval_timestamp for d in batch if d.market_source_retrieval_timestamp}
            ),
            "fundamental_source_retrieval_timestamps": sorted(
                {d.fundamental_source_retrieval_timestamp for d in batch if d.fundamental_source_retrieval_timestamp}
            ),
        }
        event_hash = canonical_hash(payload)
        events.append(
            StrategyEvent(
                event_id=f"{as_of_date}-PIIOS_CORE",
                strategy_id="PIIOS_CORE",
                as_of_date=as_of_date,
                event_type="MONTHLY_REBALANCE",
                payload=payload,
                event_hash=event_hash,
            )
        )
    return events


def event_ledger_hash(events: list[StrategyEvent]) -> str:
    payload = {"events": [asdict(event) for event in events]}
    return canonical_hash(payload)
