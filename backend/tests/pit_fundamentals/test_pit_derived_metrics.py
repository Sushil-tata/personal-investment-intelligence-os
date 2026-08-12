from __future__ import annotations

from datetime import date

from piios_backend.pit_fundamentals.joins import derive_metrics, valuation_snapshot
from piios_backend.pit_fundamentals.models import AvailabilityMode, FundamentalObservation, VersionStatus


def _obs(
    *,
    ticker: str,
    period_end: date,
    fiscal_period_type: str,
    statement_type: str,
    metric_name: str,
    value: float,
    availability_date: date,
) -> FundamentalObservation:
    return FundamentalObservation(
        security_id=ticker,
        ticker_at_time=ticker,
        company_name=ticker,
        fiscal_period_end=period_end,
        fiscal_period_type=fiscal_period_type,
        statement_type=statement_type,
        metric_name=metric_name,
        metric_value=value,
        unit="currency",
        currency="INR",
        filing_date=availability_date,
        publication_date=availability_date,
        availability_date=availability_date,
        availability_mode=AvailabilityMode.EXACT_PUBLICATION_DATE,
        source_type="PUBLIC",
        source_name="fixture",
        source_document_id=f"doc:{ticker}:{statement_type}:{period_end.isoformat()}",
        source_reference="fixture",
        retrieved_at="2026-01-01T00:00:00+00:00",
        restatement_flag=VersionStatus.ORIGINAL,
        version_id=f"v:{ticker}:{metric_name}:{period_end.isoformat()}",
        ingest_hash=f"h:{ticker}:{metric_name}:{period_end.isoformat()}",
        lag_days=None,
    )


def test_derived_metrics_and_yoy_alignment() -> None:
    ticker = "AAA.NS"
    observations = [
        _obs(ticker=ticker, period_end=date(2023, 3, 31), fiscal_period_type="FY", statement_type="income", metric_name="revenue", value=1000, availability_date=date(2023, 5, 15)),
        _obs(ticker=ticker, period_end=date(2024, 3, 31), fiscal_period_type="FY", statement_type="income", metric_name="revenue", value=1200, availability_date=date(2024, 5, 15)),
        _obs(ticker=ticker, period_end=date(2023, 3, 31), fiscal_period_type="FY", statement_type="income", metric_name="net_income", value=100, availability_date=date(2023, 5, 15)),
        _obs(ticker=ticker, period_end=date(2024, 3, 31), fiscal_period_type="FY", statement_type="income", metric_name="net_income", value=150, availability_date=date(2024, 5, 15)),
        _obs(ticker=ticker, period_end=date(2024, 3, 31), fiscal_period_type="FY", statement_type="income", metric_name="operating_income", value=200, availability_date=date(2024, 5, 15)),
        _obs(ticker=ticker, period_end=date(2024, 3, 31), fiscal_period_type="FY", statement_type="balance", metric_name="book_equity", value=600, availability_date=date(2024, 5, 15)),
        _obs(ticker=ticker, period_end=date(2024, 3, 31), fiscal_period_type="FY", statement_type="balance", metric_name="total_assets", value=1800, availability_date=date(2024, 5, 15)),
        _obs(ticker=ticker, period_end=date(2024, 3, 31), fiscal_period_type="FY", statement_type="balance", metric_name="total_debt", value=300, availability_date=date(2024, 5, 15)),
        _obs(ticker=ticker, period_end=date(2024, 3, 31), fiscal_period_type="FY", statement_type="cashflow", metric_name="operating_cash_flow", value=250, availability_date=date(2024, 5, 15)),
        _obs(ticker=ticker, period_end=date(2024, 3, 31), fiscal_period_type="FY", statement_type="cashflow", metric_name="free_cash_flow", value=180, availability_date=date(2024, 5, 15)),
        _obs(ticker=ticker, period_end=date(2023, 3, 31), fiscal_period_type="FY", statement_type="income", metric_name="eps_diluted", value=8, availability_date=date(2023, 5, 15)),
        _obs(ticker=ticker, period_end=date(2024, 3, 31), fiscal_period_type="FY", statement_type="income", metric_name="eps_diluted", value=10, availability_date=date(2024, 5, 15)),
    ]

    metrics = derive_metrics(observations, ticker, date(2024, 6, 1), strict=True)

    assert abs(metrics["operating_margin"] - (200 / 1200)) < 1e-12
    assert abs(metrics["profit_margin"] - (150 / 1200)) < 1e-12
    assert abs(metrics["roe"] - (150 / 600)) < 1e-12
    assert abs(metrics["roa"] - (150 / 1800)) < 1e-12
    assert abs(metrics["debt_equity"] - (300 / 600)) < 1e-12
    assert abs(metrics["revenue_growth_yoy"] - 0.2) < 1e-12
    assert abs(metrics["earnings_growth_yoy"] - 0.5) < 1e-12
    assert abs(metrics["eps_growth_yoy"] - 0.25) < 1e-12


def test_valuation_snapshot_is_pit_safe_and_traceable_inputs() -> None:
    ticker = "BBB.NS"
    observations = [
        _obs(ticker=ticker, period_end=date(2024, 3, 31), fiscal_period_type="FY", statement_type="income", metric_name="eps_diluted", value=12, availability_date=date(2024, 5, 15)),
        _obs(ticker=ticker, period_end=date(2024, 3, 31), fiscal_period_type="FY", statement_type="balance", metric_name="book_equity", value=3000, availability_date=date(2024, 5, 15)),
        _obs(ticker=ticker, period_end=date(2024, 3, 31), fiscal_period_type="FY", statement_type="balance", metric_name="shares_outstanding", value=100, availability_date=date(2024, 5, 15)),
        _obs(ticker=ticker, period_end=date(2024, 3, 31), fiscal_period_type="FY", statement_type="balance", metric_name="total_debt", value=1200, availability_date=date(2024, 5, 15)),
        _obs(ticker=ticker, period_end=date(2024, 3, 31), fiscal_period_type="FY", statement_type="balance", metric_name="cash_and_equivalents", value=200, availability_date=date(2024, 5, 15)),
        _obs(ticker=ticker, period_end=date(2024, 3, 31), fiscal_period_type="FY", statement_type="income", metric_name="operating_income", value=500, availability_date=date(2024, 5, 15)),
        _obs(ticker=ticker, period_end=date(2024, 3, 31), fiscal_period_type="FY", statement_type="cashflow", metric_name="free_cash_flow", value=250, availability_date=date(2024, 5, 15)),
    ]

    vals = valuation_snapshot(observations, ticker, date(2024, 6, 1), price_at_t=150.0, strict=True)

    assert abs(vals["pe"] - (150.0 / 12.0)) < 1e-12
    assert abs(vals["pb"] - ((150.0 * 100) / 3000.0)) < 1e-12
    assert "ev_ebitda_proxy" in vals
    assert "fcf_yield" in vals
