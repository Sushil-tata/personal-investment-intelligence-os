from __future__ import annotations

from pathlib import Path

from piios_backend.services.identity_backfill import classify_resolution, write_backfill_reports


def test_backfill_classification_states() -> None:
    assert classify_resolution("RESOLVED", 1, "internal_listing_id") == "exact"
    assert classify_resolution("RESOLVED", 1, "exchange+ticker") == "high-confidence deterministic"
    assert classify_resolution("AMBIGUOUS", 2, "ticker+currency") == "ambiguous"
    assert classify_resolution("UNRESOLVED", 0, None) == "unresolved"
    assert classify_resolution("CONFLICTING", 2, "ISIN") == "conflicting"


def test_backfill_dry_run_report_write(tmp_path: Path) -> None:
    rows = []
    json_path, md_path = write_backfill_reports(rows, tmp_path)
    assert json_path.exists()
    assert md_path.exists()
    assert "dry_run" in json_path.name
    assert "Dry-Run Summary" in md_path.read_text(encoding="utf-8")
