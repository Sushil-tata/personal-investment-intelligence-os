from __future__ import annotations

from datetime import date

from piios_backend.pit_fundamentals.exact_proof import (
    EXACT_DATE,
    EXACT_TIMESTAMP,
    StageA20BExactPitProofRunner,
    deterministic_visible_period,
    parse_period_from_text,
)


def test_parse_period_from_text_quarter_phrase() -> None:
    period_end, result_type = parse_period_from_text(
        "Outcome of Board Meeting: standalone and consolidated unaudited financial results for the quarter ended June 30, 2026"
    )
    assert period_end == date(2026, 6, 30)
    assert result_type == "QUARTER"


def test_parse_period_from_text_year_phrase() -> None:
    period_end, result_type = parse_period_from_text("Audited financial results for the year ended 31 March 2026")
    assert period_end == date(2026, 3, 31)
    assert result_type == "YEAR"


def test_deterministic_visible_period_respects_availability_boundary() -> None:
    rows = [
        {
            "ticker": "AAA.NS",
            "fiscal_period_end": date(2025, 12, 31),
            "availability_date": date(2026, 2, 1),
            "availability_precision": EXACT_TIMESTAMP,
        },
        {
            "ticker": "AAA.NS",
            "fiscal_period_end": date(2026, 3, 31),
            "availability_date": date(2026, 5, 10),
            "availability_precision": EXACT_DATE,
        },
    ]

    before_period, _ = deterministic_visible_period(rows, "AAA.NS", date(2026, 5, 9))
    after_period, _ = deterministic_visible_period(rows, "AAA.NS", date(2026, 5, 11))

    assert before_period == date(2025, 12, 31)
    assert after_period == date(2026, 3, 31)


def test_historical_gate_classification_failed_when_exact_zero() -> None:
    runner = StageA20BExactPitProofRunner(output_root="backend/runtime/stage_a2_exact_pit_proof_test")
    metrics = {
        "company_periods_attempted": 90,
        "exact_availability_rate": 0.0,
        "manual_before_after_accuracy": 1.0,
        "known_lookahead_leakage_count": 0,
        "source_match_rate": 0.0,
        "fiscal_period_source_mapping_accuracy": 0.0,
        "coverage_by_size": {"LARGE": {"attempted": 30.0}, "MID": {"attempted": 30.0}, "SMALL": {"attempted": 30.0}},
    }
    verdict = runner._historical_classification(metrics)
    assert verdict == "EXACT_PIT_SOURCE_PROOF_FAILED"
