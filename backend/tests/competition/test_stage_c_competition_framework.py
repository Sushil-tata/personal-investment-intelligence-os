from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from piios_backend.competition.ledger_bridge import decisions_to_events, load_core_decisions
from piios_backend.competition.models import APPLICATION_RETRIEVAL_TIMESTAMP, CoreDecision, StrategyDefinition
from piios_backend.competition.registry import StrategyRegistry, default_registry
from piios_backend.competition.runner import run_competition
from piios_backend.prospective_ledger.models import ProspectiveDecisionRecord
from piios_backend.prospective_ledger.store import ProspectiveLedgerStore


def _seed_record(*, decision_id: str, as_of_date: str, ticker: str, allocation: float, run_timestamp: str) -> ProspectiveDecisionRecord:
    return ProspectiveDecisionRecord(
        decision_id=decision_id,
        strategy_id="PIIOS_CORE",
        run_timestamp=run_timestamp,
        as_of_date=as_of_date,
        ticker=ticker,
        market="India",
        ranking_position=1,
        action="BUY",
        proposed_allocation=allocation,
        quality_score=70.0,
        growth_score=60.0,
        valuation_score=55.0,
        momentum_score=50.0,
        risk_score=45.0,
        discovery_score=58.0,
        attractiveness_score=62.0,
        suitability_score=57.0,
        combined_score=60.0,
        evidence_coverage=0.8,
        confidence=0.7,
        reason_codes=["EVIDENCE_COVERAGE"],
        factor_trace_reference={"trace_keys": ["a"]},
        engine_version="WAVE_3_1_RECOMMENDATION_MVP",
        git_commit_sha="abc123",
        config_version="cfg-v1",
        universe_version="u-v1",
        market_provider="yfinance",
        fundamental_provider="yfinance",
        market_source_retrieval_timestamp="2026-08-12T00:00:00+05:30",
        fundamental_source_retrieval_timestamp="2026-08-12T00:10:00+00:00",
        market_snapshot_reference={"as_of": "2026-08-12T00:00:00+05:30"},
        fundamental_snapshot_reference={
            "diagnostics": {
                "fundamental_source_retrieval_timestamp": "2026-08-12T00:10:00+00:00",
            }
        },
        market_snapshot_hash="mhash",
        fundamental_snapshot_hash="fhash",
        factor_payload_hash="phash",
    )


def _seed_db(path: Path) -> None:
    store = ProspectiveLedgerStore(path)
    store.init()
    store.append(
        [
            _seed_record(
                decision_id="d1",
                as_of_date="2026-01-15",
                ticker="AAA.NS",
                allocation=1000.0,
                run_timestamp="2026-01-15T10:00:00Z",
            ),
            _seed_record(
                decision_id="d2",
                as_of_date="2026-02-15",
                ticker="BBB.NS",
                allocation=1200.0,
                run_timestamp="2026-02-15T10:00:00Z",
            ),
        ]
    )


def test_registry_immutable_versioning() -> None:
    registry = StrategyRegistry()
    registry.register(StrategyDefinition("PIIOS_CORE", 1, "v1", "core", "CORE"))
    try:
        registry.register(StrategyDefinition("PIIOS_CORE", 1, "v1b", "core", "CORE"))
        assert False, "expected immutable version violation"
    except ValueError:
        pass


def test_ledger_bridge_preserves_application_timestamp_semantics(tmp_path: Path) -> None:
    db_path = tmp_path / "prospective.db"
    _seed_db(db_path)

    decisions = load_core_decisions(db_path)
    assert decisions
    assert all(d.fundamental_timestamp_semantics == APPLICATION_RETRIEVAL_TIMESTAMP for d in decisions)
    assert all(d.fundamental_source_retrieval_timestamp is not None for d in decisions)

    events = decisions_to_events(decisions)
    assert events
    first = events[0]
    assert first.payload["fundamental_timestamp_semantics"] == APPLICATION_RETRIEVAL_TIMESTAMP


def test_competition_replay_is_deterministic(tmp_path: Path) -> None:
    db_path = tmp_path / "prospective.db"
    _seed_db(db_path)

    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    first = run_competition(prospective_db_path=db_path, output_root=out1, monthly_contribution=5000.0)
    second = run_competition(prospective_db_path=db_path, output_root=out2, monthly_contribution=5000.0)

    assert [asdict(x) for x in first.leaderboard] == [asdict(x) for x in second.leaderboard]
    assert [asdict(x) for x in first.snapshots] == [asdict(x) for x in second.snapshots]


def test_fair_capital_rules_and_benchmark_contestants(tmp_path: Path) -> None:
    db_path = tmp_path / "prospective.db"
    _seed_db(db_path)

    result = run_competition(prospective_db_path=db_path, output_root=tmp_path / "out", monthly_contribution=5000.0)
    expected = {"PIIOS_CORE", "NIFTY50_V1", "SP500_V1", "STI_V1", "CASH_V1"}
    got = {row.strategy_id for row in result.leaderboard}
    assert got == expected

    months = len({s.as_of_date[:7] for s in result.snapshots})
    for row in result.leaderboard:
        assert row.cumulative_contributed == 5000.0 * months


def test_no_lookahead_for_earlier_months(tmp_path: Path) -> None:
    base_db = tmp_path / "base.db"
    _seed_db(base_db)
    base = run_competition(prospective_db_path=base_db, output_root=tmp_path / "out_base", monthly_contribution=5000.0)

    changed_db = tmp_path / "changed.db"
    _seed_db(changed_db)
    store = ProspectiveLedgerStore(changed_db)
    store.append(
        [
            _seed_record(
                decision_id="d3",
                as_of_date="2026-03-15",
                ticker="CCC.NS",
                allocation=1400.0,
                run_timestamp="2026-03-15T10:00:00Z",
            )
        ]
    )
    changed = run_competition(prospective_db_path=changed_db, output_root=tmp_path / "out_changed", monthly_contribution=5000.0)

    base_month = [s for s in base.snapshots if s.as_of_date.startswith("2026-01") and s.strategy_id == "PIIOS_CORE"][0]
    changed_month = [s for s in changed.snapshots if s.as_of_date.startswith("2026-01") and s.strategy_id == "PIIOS_CORE"][0]
    assert base_month.nav_after_return == changed_month.nav_after_return


def test_runtime_artifacts_written(tmp_path: Path) -> None:
    db_path = tmp_path / "prospective.db"
    _seed_db(db_path)
    out = tmp_path / "out"
    run_competition(prospective_db_path=db_path, output_root=out, monthly_contribution=5000.0)

    expected = {
        "competition_registry.json",
        "competition_event_ledger.json",
        "competition_leaderboard.json",
        "competition_monthly_snapshots.json",
        "competition_summary.json",
    }
    produced = {p.name for p in out.iterdir() if p.is_file()}
    assert expected.issubset(produced)

    summary = json.loads((out / "competition_summary.json").read_text(encoding="utf-8"))
    assert "current_rank_1" in summary
    assert "investment_conclusion" in summary


def test_default_registry_contains_required_contestants() -> None:
    registry = default_registry()
    ids = {item.strategy_id for item in registry.all_latest()}
    assert ids == {"PIIOS_CORE", "NIFTY50_V1", "SP500_V1", "STI_V1", "CASH_V1"}
