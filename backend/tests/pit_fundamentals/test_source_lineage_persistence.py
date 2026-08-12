from __future__ import annotations

from datetime import date

from piios_backend.pit_fundamentals.models import AvailabilityMode, FundamentalObservation, VersionStatus


def test_source_lineage_fields_present() -> None:
    obs = FundamentalObservation(
        security_id="AAA.NS",
        ticker_at_time="AAA.NS",
        company_name="AAA",
        fiscal_period_end=date(2024, 3, 31),
        fiscal_period_type="FY",
        statement_type="income",
        metric_name="revenue",
        metric_value=100.0,
        unit="currency",
        currency="INR",
        filing_date=date(2024, 5, 15),
        publication_date=date(2024, 5, 15),
        availability_date=date(2024, 5, 15),
        availability_mode=AvailabilityMode.EXACT_PUBLICATION_DATE,
        source_type="PUBLIC_API",
        source_name="yfinance",
        source_document_id="doc:AAA.NS:income:2024-03-31",
        source_reference="yfinance:AAA.NS:income:annual",
        retrieved_at="2026-01-01T00:00:00+00:00",
        restatement_flag=VersionStatus.UNKNOWN_VERSION,
        version_id="v1",
        ingest_hash="h1",
        lag_days=None,
    )

    row = obs.to_row()
    assert row["source_type"] == "PUBLIC_API"
    assert row["source_name"] == "yfinance"
    assert row["source_document_id"] is not None
    assert row["source_reference"] is not None
    assert row["availability_date"] == "2024-05-15"
    assert row["publication_date"] == "2024-05-15"
    assert row["restatement_flag"] == "UNKNOWN_VERSION"
