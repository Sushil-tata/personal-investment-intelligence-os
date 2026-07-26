from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from piios.portfolio.infrastructure.csv_loader import load_portfolio_snapshot_from_csv
from piios.portfolio.infrastructure.excel_loader import load_portfolio_snapshot_from_excel


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_csv_loader_builds_typed_snapshot() -> None:
    snapshot, result = load_portfolio_snapshot_from_csv(
        file_path=str(FIXTURES / "portfolio_multicountry.csv"),
        reporting_currency="USD",
        as_of_utc=datetime(2026, 7, 26, tzinfo=timezone.utc),
        portfolio_id="p-fictional",
        portfolio_name="Fictional Household",
    )

    assert snapshot is not None
    assert result.snapshot is not None
    assert result.snapshot.source_filename == "portfolio_multicountry.csv"
    assert result.snapshot.reporting_currency == "USD"
    assert len(snapshot.portfolio.holdings) == 5
    assert snapshot.portfolio.holdings[0].raw_source["ticker"] == "INFY"


def test_csv_loader_flags_missing_sector_warning() -> None:
    snapshot, result = load_portfolio_snapshot_from_csv(
        file_path=str(FIXTURES / "portfolio_missing_sector.csv"),
        reporting_currency="USD",
    )

    assert snapshot is not None
    warnings = [issue for issue in result.issues if issue.severity == "warning"]
    assert any(issue.code == "MISSING_CLASSIFICATION" and issue.field_name == "sector" for issue in warnings)


def test_csv_loader_rejects_negative_quantity() -> None:
    snapshot, result = load_portfolio_snapshot_from_csv(
        file_path=str(FIXTURES / "portfolio_negative_quantity.csv"),
        reporting_currency="USD",
    )

    assert snapshot is None
    assert any(issue.severity == "error" and issue.code == "INVALID_ROW" for issue in result.issues)


def test_excel_loader_roundtrip(tmp_path: Path) -> None:
    pytest.importorskip("openpyxl")
    source = FIXTURES / "portfolio_multicountry.csv"
    df = pd.read_csv(source)
    xlsx_path = tmp_path / "portfolio_multicountry.xlsx"
    df.to_excel(xlsx_path, index=False)

    snapshot, result = load_portfolio_snapshot_from_excel(
        file_path=str(xlsx_path),
        reporting_currency="USD",
        as_of_utc=datetime(2026, 7, 26, tzinfo=timezone.utc),
    )

    assert snapshot is not None
    assert result.snapshot is not None
    assert len(result.snapshot.holdings) == 5
