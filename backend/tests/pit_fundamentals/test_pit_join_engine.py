from __future__ import annotations

from datetime import date

from piios_backend.pit_fundamentals.joins import get_fundamental_snapshot, latest_observation
from piios_backend.pit_fundamentals.models import AvailabilityMode, FundamentalObservation, VersionStatus


def _obs(
    *,
    ticker: str,
    period_end: date,
    metric_name: str,
    value: float,
    availability_date: date | None,
    availability_mode: AvailabilityMode,
    version_id: str,
    restatement_flag: VersionStatus = VersionStatus.UNKNOWN_VERSION,
) -> FundamentalObservation:
    return FundamentalObservation(
        security_id=ticker,
        ticker_at_time=ticker,
        company_name=ticker,
        fiscal_period_end=period_end,
        fiscal_period_type="Q",
        statement_type="income",
        metric_name=metric_name,
        metric_value=value,
        unit="currency",
        currency="INR",
        filing_date=availability_date,
        publication_date=availability_date,
        availability_date=availability_date,
        availability_mode=availability_mode,
        source_type="PUBLIC",
        source_name="fixture",
        source_document_id=f"doc:{ticker}:{period_end.isoformat()}",
        source_reference="fixture",
        retrieved_at="2026-01-01T00:00:00+00:00",
        restatement_flag=restatement_flag,
        version_id=version_id,
        ingest_hash=f"hash:{version_id}",
        lag_days=None,
    )


def test_future_filing_invisibility() -> None:
    observations = [
        _obs(
            ticker="AAA.NS",
            period_end=date(2024, 12, 31),
            metric_name="revenue",
            value=100.0,
            availability_date=date(2025, 2, 1),
            availability_mode=AvailabilityMode.EXACT_PUBLICATION_DATE,
            version_id="v1",
        ),
        _obs(
            ticker="AAA.NS",
            period_end=date(2025, 3, 31),
            metric_name="revenue",
            value=150.0,
            availability_date=date(2025, 5, 15),
            availability_mode=AvailabilityMode.EXACT_PUBLICATION_DATE,
            version_id="v2",
        ),
    ]
    at_april = latest_observation(observations, "AAA.NS", "revenue", date(2025, 4, 30), strict=True)
    at_may_end = latest_observation(observations, "AAA.NS", "revenue", date(2025, 5, 31), strict=True)

    assert at_april is not None
    assert at_april.fiscal_period_end == date(2024, 12, 31)
    assert at_may_end is not None
    assert at_may_end.fiscal_period_end == date(2025, 3, 31)


def test_future_restatement_invisibility() -> None:
    observations = [
        _obs(
            ticker="BBB.NS",
            period_end=date(2024, 12, 31),
            metric_name="net_income",
            value=40.0,
            availability_date=date(2025, 2, 10),
            availability_mode=AvailabilityMode.EXACT_PUBLICATION_DATE,
            version_id="orig",
            restatement_flag=VersionStatus.ORIGINAL,
        ),
        _obs(
            ticker="BBB.NS",
            period_end=date(2024, 12, 31),
            metric_name="net_income",
            value=36.0,
            availability_date=date(2025, 7, 1),
            availability_mode=AvailabilityMode.EXACT_PUBLICATION_DATE,
            version_id="rest",
            restatement_flag=VersionStatus.RESTATED,
        ),
    ]

    pre_restatement = latest_observation(observations, "BBB.NS", "net_income", date(2025, 3, 1), strict=True)
    post_restatement = latest_observation(observations, "BBB.NS", "net_income", date(2025, 8, 1), strict=True)

    assert pre_restatement is not None
    assert pre_restatement.metric_value == 40.0
    assert post_restatement is not None
    assert post_restatement.metric_value == 36.0


def test_unknown_availability_excluded_in_strict_mode() -> None:
    observations = [
        _obs(
            ticker="CCC.NS",
            period_end=date(2025, 3, 31),
            metric_name="revenue",
            value=200.0,
            availability_date=date(2025, 5, 20),
            availability_mode=AvailabilityMode.CONSERVATIVE_LAG,
            version_id="known",
        ),
        _obs(
            ticker="CCC.NS",
            period_end=date(2025, 6, 30),
            metric_name="revenue",
            value=220.0,
            availability_date=date(2025, 8, 15),
            availability_mode=AvailabilityMode.UNKNOWN,
            version_id="unknown",
        ),
    ]

    strict_pick = latest_observation(observations, "CCC.NS", "revenue", date(2025, 9, 1), strict=True)
    loose_pick = latest_observation(observations, "CCC.NS", "revenue", date(2025, 9, 1), strict=False)

    assert strict_pick is not None
    assert strict_pick.version_id == "known"
    assert loose_pick is not None
    assert loose_pick.version_id == "unknown"


def test_input_order_invariance() -> None:
    a = _obs(
        ticker="DDD.NS",
        period_end=date(2024, 12, 31),
        metric_name="eps_diluted",
        value=12.0,
        availability_date=date(2025, 2, 5),
        availability_mode=AvailabilityMode.EXACT_PUBLICATION_DATE,
        version_id="a",
    )
    b = _obs(
        ticker="DDD.NS",
        period_end=date(2025, 3, 31),
        metric_name="eps_diluted",
        value=14.0,
        availability_date=date(2025, 5, 15),
        availability_mode=AvailabilityMode.EXACT_PUBLICATION_DATE,
        version_id="b",
    )
    left = latest_observation([a, b], "DDD.NS", "eps_diluted", date(2025, 6, 1), strict=True)
    right = latest_observation([b, a], "DDD.NS", "eps_diluted", date(2025, 6, 1), strict=True)

    assert left is not None and right is not None
    assert left.version_id == right.version_id


def test_duplicate_version_determinism() -> None:
    observations = [
        _obs(
            ticker="EEE.NS",
            period_end=date(2025, 3, 31),
            metric_name="book_equity",
            value=500.0,
            availability_date=date(2025, 5, 1),
            availability_mode=AvailabilityMode.EXACT_PUBLICATION_DATE,
            version_id="orig",
            restatement_flag=VersionStatus.ORIGINAL,
        ),
        _obs(
            ticker="EEE.NS",
            period_end=date(2025, 3, 31),
            metric_name="book_equity",
            value=520.0,
            availability_date=date(2025, 5, 1),
            availability_mode=AvailabilityMode.EXACT_PUBLICATION_DATE,
            version_id="amended",
            restatement_flag=VersionStatus.AMENDED,
        ),
    ]
    pick = latest_observation(observations, "EEE.NS", "book_equity", date(2025, 6, 1), strict=True)
    assert pick is not None
    assert pick.version_id == "amended"


def test_snapshot_strict_mode_behavior() -> None:
    observations = [
        _obs(
            ticker="FFF.NS",
            period_end=date(2025, 3, 31),
            metric_name="revenue",
            value=1000.0,
            availability_date=date(2025, 5, 1),
            availability_mode=AvailabilityMode.EXACT_PUBLICATION_DATE,
            version_id="rev",
        ),
        _obs(
            ticker="FFF.NS",
            period_end=date(2025, 3, 31),
            metric_name="net_income",
            value=120.0,
            availability_date=date(2025, 5, 1),
            availability_mode=AvailabilityMode.UNKNOWN,
            version_id="ni",
        ),
    ]
    strict_snapshot = get_fundamental_snapshot(observations, "FFF.NS", date(2025, 6, 1), strict=True)
    loose_snapshot = get_fundamental_snapshot(observations, "FFF.NS", date(2025, 6, 1), strict=False)

    assert "revenue" in strict_snapshot
    assert "net_income" not in strict_snapshot
    assert "net_income" in loose_snapshot
