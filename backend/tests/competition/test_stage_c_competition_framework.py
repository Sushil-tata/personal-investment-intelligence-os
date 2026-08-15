from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

import pandas as pd

from piios_backend.competition.ledger_bridge import decisions_to_events, load_core_decisions
from piios_backend.competition.models import APPLICATION_RETRIEVAL_TIMESTAMP, CoreDecision, StrategyDefinition
from piios_backend.competition.registry import StrategyRegistry, default_registry
from piios_backend.competition.runner import run_competition
from piios_backend.prospective_ledger.models import ProspectiveDecisionRecord
from piios_backend.prospective_ledger.store import ProspectiveLedgerStore


class FakePriceProvider:
    def __init__(
        self,
        series_by_ticker: dict[str, list[tuple[str, float]]],
        volume_by_ticker: dict[str, list[tuple[str, float]]] | None = None,
    ) -> None:
        self._series_by_ticker = series_by_ticker
        self._volume_by_ticker = volume_by_ticker or {}

    def close_series(self, ticker: str) -> pd.Series:
        rows = self._series_by_ticker.get(ticker, [])
        if not rows:
            return pd.Series(dtype=float)
        idx = pd.to_datetime([d for d, _ in rows]).normalize()
        values = [float(v) for _, v in rows]
        return pd.Series(values, index=idx).sort_index()

    def volume_series(self, ticker: str) -> pd.Series:
        rows = self._volume_by_ticker.get(ticker, [])
        if not rows:
            return pd.Series(dtype=float)
        idx = pd.to_datetime([d for d, _ in rows]).normalize()
        values = [float(v) for _, v in rows]
        return pd.Series(values, index=idx).sort_index()


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
    registry.register(StrategyDefinition("PIIOS_CORE_V1", 1, "v1", "core", "CORE"))
    try:
        registry.register(StrategyDefinition("PIIOS_CORE_V1", 1, "v1b", "core", "CORE"))
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
    provider = FakePriceProvider(
        {
            "AAA.NS": [("2026-01-15", 100.0), ("2026-01-31", 110.0)],
            "BBB.NS": [("2026-02-15", 100.0), ("2026-02-28", 90.0)],
            "NIFTYBEES.NS": [("2026-01-15", 200.0), ("2026-01-31", 202.0), ("2026-02-15", 202.0), ("2026-02-28", 204.0)],
            "SPY": [("2026-01-15", 300.0), ("2026-01-31", 303.0), ("2026-02-15", 303.0), ("2026-02-28", 306.0)],
            "ES3.SI": [("2026-01-15", 3.0), ("2026-01-31", 3.03), ("2026-02-15", 3.03), ("2026-02-28", 3.06)],
        }
    )
    first = run_competition(
        prospective_db_path=db_path,
        output_root=out1,
        monthly_contribution=5000.0,
        price_provider=provider,
        today=pd.Timestamp("2026-03-05").date(),
    )
    second = run_competition(
        prospective_db_path=db_path,
        output_root=out2,
        monthly_contribution=5000.0,
        price_provider=provider,
        today=pd.Timestamp("2026-03-05").date(),
    )

    assert [asdict(x) for x in first.leaderboard] == [asdict(x) for x in second.leaderboard]
    assert [asdict(x) for x in first.snapshots] == [asdict(x) for x in second.snapshots]


def test_fair_capital_rules_and_benchmark_contestants(tmp_path: Path) -> None:
    db_path = tmp_path / "prospective.db"
    _seed_db(db_path)

    provider = FakePriceProvider(
        {
            "AAA.NS": [("2026-01-15", 100.0), ("2026-01-31", 110.0)],
            "BBB.NS": [("2026-02-15", 100.0), ("2026-02-28", 90.0)],
            "NIFTYBEES.NS": [("2026-01-15", 200.0), ("2026-01-31", 202.0), ("2026-02-15", 202.0), ("2026-02-28", 204.0)],
            "SPY": [("2026-01-15", 300.0), ("2026-01-31", 303.0), ("2026-02-15", 303.0), ("2026-02-28", 306.0)],
            "ES3.SI": [("2026-01-15", 3.0), ("2026-01-31", 3.03), ("2026-02-15", 3.03), ("2026-02-28", 3.06)],
        }
    )
    result = run_competition(
        prospective_db_path=db_path,
        output_root=tmp_path / "out",
        monthly_contribution=5000.0,
        price_provider=provider,
        today=pd.Timestamp("2026-03-05").date(),
    )
    expected = {"PIIOS_CORE_V1", "52W_HIGH_V1", "NIFTY50_V1", "NIFTY500_V1", "SP500_V1", "STI_V1", "CASH_V1"}
    got = {row.strategy_id for row in result.leaderboard}
    assert got == expected

    months = len({s.as_of_date[:7] for s in result.snapshots})
    for row in result.leaderboard:
        assert row.cumulative_contributed == 5000.0 * months


def test_no_lookahead_for_earlier_months(tmp_path: Path) -> None:
    base_db = tmp_path / "base.db"
    _seed_db(base_db)
    provider_base = FakePriceProvider(
        {
            "AAA.NS": [("2026-01-15", 100.0), ("2026-01-31", 110.0), ("2026-03-31", 300.0)],
            "BBB.NS": [("2026-02-15", 100.0), ("2026-02-28", 90.0), ("2026-03-31", 10.0)],
            "CCC.NS": [("2026-03-15", 100.0), ("2026-03-31", 120.0)],
            "NIFTYBEES.NS": [("2026-01-15", 200.0), ("2026-01-31", 202.0), ("2026-02-15", 202.0), ("2026-02-28", 204.0), ("2026-03-31", 190.0)],
            "SPY": [("2026-01-15", 300.0), ("2026-01-31", 303.0), ("2026-02-15", 303.0), ("2026-02-28", 306.0), ("2026-03-31", 330.0)],
            "ES3.SI": [("2026-01-15", 3.0), ("2026-01-31", 3.03), ("2026-02-15", 3.03), ("2026-02-28", 3.06), ("2026-03-31", 2.8)],
        }
    )
    base = run_competition(
        prospective_db_path=base_db,
        output_root=tmp_path / "out_base",
        monthly_contribution=5000.0,
        price_provider=provider_base,
        today=pd.Timestamp("2026-03-31").date(),
    )

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
    changed = run_competition(
        prospective_db_path=changed_db,
        output_root=tmp_path / "out_changed",
        monthly_contribution=5000.0,
        price_provider=provider_base,
        today=pd.Timestamp("2026-03-31").date(),
    )

    base_month = [s for s in base.snapshots if s.as_of_date.startswith("2026-01") and s.strategy_id == "PIIOS_CORE_V1"][0]
    changed_month = [s for s in changed.snapshots if s.as_of_date.startswith("2026-01") and s.strategy_id == "PIIOS_CORE_V1"][0]
    assert base_month.nav_after_return == changed_month.nav_after_return


def test_runtime_artifacts_written(tmp_path: Path) -> None:
    db_path = tmp_path / "prospective.db"
    _seed_db(db_path)
    out = tmp_path / "out"
    provider = FakePriceProvider(
        {
            "AAA.NS": [("2026-01-15", 100.0), ("2026-01-31", 110.0)],
            "BBB.NS": [("2026-02-15", 100.0), ("2026-02-28", 90.0)],
            "NIFTYBEES.NS": [("2026-01-15", 200.0), ("2026-01-31", 202.0), ("2026-02-15", 202.0), ("2026-02-28", 204.0)],
            "SPY": [("2026-01-15", 300.0), ("2026-01-31", 303.0), ("2026-02-15", 303.0), ("2026-02-28", 306.0)],
            "ES3.SI": [("2026-01-15", 3.0), ("2026-01-31", 3.03), ("2026-02-15", 3.03), ("2026-02-28", 3.06)],
        }
    )
    run_competition(
        prospective_db_path=db_path,
        output_root=out,
        monthly_contribution=5000.0,
        price_provider=provider,
        today=pd.Timestamp("2026-03-05").date(),
    )

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


def test_piios_core_weighted_real_return_matches_expected(tmp_path: Path) -> None:
    db_path = tmp_path / "prospective.db"
    store = ProspectiveLedgerStore(db_path)
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
                as_of_date="2026-01-15",
                ticker="BBB.NS",
                allocation=3000.0,
                run_timestamp="2026-01-15T10:00:00Z",
            ),
        ]
    )

    provider = FakePriceProvider(
        {
            "AAA.NS": [("2026-01-15", 100.0), ("2026-01-31", 110.0)],
            "BBB.NS": [("2026-01-15", 100.0), ("2026-01-31", 90.0)],
            "NIFTYBEES.NS": [("2026-01-15", 200.0), ("2026-01-31", 202.0)],
            "SPY": [("2026-01-15", 300.0), ("2026-01-31", 303.0)],
            "ES3.SI": [("2026-01-15", 3.0), ("2026-01-31", 3.03)],
        }
    )

    run_competition(
        prospective_db_path=db_path,
        output_root=tmp_path / "out",
        monthly_contribution=5000.0,
        price_provider=provider,
        today=pd.Timestamp("2026-01-31").date(),
    )

    summary = json.loads((tmp_path / "out" / "competition_summary.json").read_text(encoding="utf-8"))
    details = summary["piios_core_monthly_components"]["2026-01"]
    by_ticker = {row["ticker"]: row for row in details}
    assert by_ticker["AAA.NS"]["price_return"] == 0.1
    assert by_ticker["BBB.NS"]["price_return"] == -0.1

    snapshots = json.loads((tmp_path / "out" / "competition_monthly_snapshots.json").read_text(encoding="utf-8"))
    core = [x for x in snapshots if x["strategy_id"] == "PIIOS_CORE_V1" and x["as_of_date"].startswith("2026-01")][0]
    expected_return = ((1000.0 / 4000.0) * 0.1) + ((3000.0 / 4000.0) * -0.1)
    assert core["monthly_return"] == round(expected_return, 8)


def test_default_registry_contains_required_contestants() -> None:
    registry = default_registry()
    ids = {item.strategy_id for item in registry.all_latest()}
    assert ids == {"PIIOS_CORE_V1", "52W_HIGH_V1", "NIFTY50_V1", "NIFTY500_V1", "SP500_V1", "STI_V1", "CASH_V1"}


def test_summary_marks_ph_ph_mh_rs_as_data_pending(tmp_path: Path) -> None:
    db_path = tmp_path / "prospective.db"
    _seed_db(db_path)
    out = tmp_path / "out"
    provider = FakePriceProvider(
        {
            "AAA.NS": [("2026-01-15", 100.0), ("2026-01-31", 110.0)],
            "BBB.NS": [("2026-02-15", 100.0), ("2026-02-28", 90.0)],
            "ABB.NS": [("2025-01-01", 90.0), ("2026-01-15", 100.0), ("2026-01-31", 110.0)],
            "NIFTYBEES.NS": [("2026-01-15", 200.0), ("2026-01-31", 202.0), ("2026-02-15", 202.0), ("2026-02-28", 204.0)],
            "SPY": [("2026-01-15", 300.0), ("2026-01-31", 303.0), ("2026-02-15", 303.0), ("2026-02-28", 306.0)],
            "ES3.SI": [("2026-01-15", 3.0), ("2026-01-31", 3.03), ("2026-02-15", 3.03), ("2026-02-28", 3.06)],
        }
    )
    run_competition(
        prospective_db_path=db_path,
        output_root=out,
        monthly_contribution=5000.0,
        price_provider=provider,
        today=pd.Timestamp("2026-03-05").date(),
    )

    summary = json.loads((out / "competition_summary.json").read_text(encoding="utf-8"))
    assert summary["data_pending_strategies"] == {
        "PH_PH_MH_RS_V1": (
            "REAL_YFINANCE_STATEMENT_PROFIT_EXISTS_BUT_COMPLETE_PIT_PUBLICATION_DATES_"
            "UNIVERSE_COVERAGE_AND_RESTATEMENT_VERSIONS_ARE_UNAVAILABLE;CURRENT_INFO_"
            "FIELDS_WOULD_INTRODUCE_LOOKAHEAD"
        )
    }
    assert summary["sizing_note"] == (
        "52W_HIGH_V1 uses equal-weight sizing because liquidity/volatility inputs are not available in the current "
        "MarketPriceProvider interface; liquidity proxy in this version is minimum recent trading-day observations only."
    )


def test_52w_high_challenger_selects_near_high_name_without_lookahead(tmp_path: Path) -> None:
    db_path = tmp_path / "prospective.db"
    store = ProspectiveLedgerStore(db_path)
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
        ]
    )

    trading_days = pd.bdate_range("2025-01-01", "2026-01-31")
    abb_rows: list[tuple[str, float]] = []
    acc_rows: list[tuple[str, float]] = []
    for idx, ts in enumerate(trading_days):
        date_text = ts.date().isoformat()
        abb_price = 100.0 + (idx * 0.15)
        acc_price = 120.0 - (idx * 0.02)
        if date_text == "2026-01-31":
            abb_price = 150.0
            acc_price = 110.0
        abb_rows.append((date_text, round(abb_price, 6)))
        acc_rows.append((date_text, round(acc_price, 6)))

    provider = FakePriceProvider(
        {
            "AAA.NS": [("2026-01-15", 100.0), ("2026-01-31", 110.0)],
            "ABB.NS": abb_rows,
            "ACC.NS": acc_rows,
            "NIFTYBEES.NS": [("2026-01-15", 200.0), ("2026-01-31", 202.0)],
            "SPY": [("2026-01-15", 300.0), ("2026-01-31", 303.0)],
            "ES3.SI": [("2026-01-15", 3.0), ("2026-01-31", 3.03)],
        }
    )

    run_competition(
        prospective_db_path=db_path,
        output_root=tmp_path / "out",
        monthly_contribution=5000.0,
        price_provider=provider,
        today=pd.Timestamp("2026-01-31").date(),
    )

    summary = json.loads((tmp_path / "out" / "competition_summary.json").read_text(encoding="utf-8"))
    picks = summary["challenger_monthly_components"]["2026-01"]["52W_HIGH_V1"]
    assert picks
    assert picks[0]["ticker"] == "ABB.NS"

    snapshots = json.loads((tmp_path / "out" / "competition_monthly_snapshots.json").read_text(encoding="utf-8"))
    challenger = [x for x in snapshots if x["strategy_id"] == "52W_HIGH_V1" and x["as_of_date"].startswith("2026-01")][0]
    assert challenger["monthly_return"] > 0.0


def test_nifty500_index_contestant_and_execution_proxy_are_reported_separately(tmp_path: Path) -> None:
    db_path = tmp_path / "prospective.db"
    _seed_db(db_path)
    dates = ["2026-01-15", "2026-01-31", "2026-02-15", "2026-02-28"]
    provider = FakePriceProvider(
        {
            "AAA.NS": [(dates[0], 100.0), (dates[1], 110.0)],
            "BBB.NS": [(dates[2], 100.0), (dates[3], 90.0)],
            "^CRSLDX": list(zip(dates, [100.0, 110.0, 110.0, 121.0])),
            "MONIFTY500.NS": list(zip(dates, [50.0, 54.0, 54.0, 59.4])),
        },
        volume_by_ticker={
            "MONIFTY500.NS": list(zip(dates, [1000.0, 2000.0, 3000.0, 4000.0])),
        },
    )

    result = run_competition(
        prospective_db_path=db_path,
        output_root=tmp_path / "out",
        monthly_contribution=5000.0,
        price_provider=provider,
        today=pd.Timestamp("2026-03-05").date(),
    )

    nifty500_snapshots = [row for row in result.snapshots if row.strategy_id == "NIFTY500_V1"]
    assert [row.monthly_return for row in nifty500_snapshots] == [0.1, 0.1]

    summary = json.loads((tmp_path / "out" / "competition_summary.json").read_text(encoding="utf-8"))
    representation = summary["nifty500_representation"]
    assert representation["contestant_return_source"] == "benchmark_index"
    assert representation["benchmark_index"]["ticker"] == "^CRSLDX"
    assert representation["benchmark_index"]["investable"] is False
    assert representation["benchmark_index"]["liquidity_applicable"] is False
    assert "median_daily_volume" not in representation["benchmark_index"]
    assert representation["execution_proxy"]["ticker"] == "MONIFTY500.NS"
    assert representation["execution_proxy"]["liquidity_applicable"] is True
    assert representation["execution_proxy"]["included_as_competition_contestant"] is False
    assert representation["benchmark_index"]["history_observations"] == 4
    assert representation["execution_proxy"]["history_observations"] == 4
    assert representation["execution_proxy"]["volume_observations"] == 4
    assert representation["execution_proxy"]["median_daily_volume"] == 2500.0
    assert representation["monthly_comparisons"]["2026-01"] == {
        "benchmark_index_return": 0.1,
        "execution_proxy_return": 0.08,
        "tracking_difference_pct_points": -2.0,
    }
    assert representation["annualized_daily_tracking_error_pct"] is not None
