from __future__ import annotations

from datetime import date, timedelta
import hashlib

from .models import AvailabilityMode


INCOME_METRICS = {
    "Total Revenue": ("revenue", "currency"),
    "Net Income": ("net_income", "currency"),
    "Diluted EPS": ("eps_diluted", "ratio"),
    "Basic EPS": ("eps_basic", "ratio"),
    "Operating Income": ("operating_income", "currency"),
}

BALANCE_METRICS = {
    "Stockholders Equity": ("book_equity", "currency"),
    "Total Debt": ("total_debt", "currency"),
    "Cash And Cash Equivalents": ("cash_and_equivalents", "currency"),
    "Total Assets": ("total_assets", "currency"),
    "Ordinary Shares Number": ("shares_outstanding", "shares"),
}

CASHFLOW_METRICS = {
    "Operating Cash Flow": ("operating_cash_flow", "currency"),
    "Free Cash Flow": ("free_cash_flow", "currency"),
    "Capital Expenditure": ("capex", "currency"),
}


def statement_metric_map(statement_type: str) -> dict[str, tuple[str, str]]:
    if statement_type == "income":
        return INCOME_METRICS
    if statement_type == "balance":
        return BALANCE_METRICS
    if statement_type == "cashflow":
        return CASHFLOW_METRICS
    return {}


def infer_fiscal_period_type(statement_scope: str) -> str:
    return "Q" if statement_scope == "quarterly" else "FY"


def conservative_availability_date(period_end: date, period_type: str, statement_type: str) -> tuple[date, int]:
    # Conservative reporting lag for exploratory PIT proof only.
    if period_type == "Q":
        lag = 60
    else:
        lag = 120
    if statement_type == "cashflow":
        lag += 15
    return period_end + timedelta(days=lag), lag


def make_version_id(
    ticker: str,
    statement_type: str,
    metric_name: str,
    period_end: date,
    source_document_id: str,
    metric_value: float,
    availability_date: date | None,
) -> str:
    payload = "|".join(
        [
            ticker,
            statement_type,
            metric_name,
            period_end.isoformat(),
            source_document_id,
            f"{metric_value:.8f}",
            availability_date.isoformat() if availability_date else "NA",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def make_ingest_hash(
    ticker: str,
    metric_name: str,
    period_end: date,
    availability_mode: AvailabilityMode,
    source_reference: str,
    metric_value: float,
) -> str:
    payload = "|".join(
        [
            ticker,
            metric_name,
            period_end.isoformat(),
            availability_mode.value,
            source_reference,
            f"{metric_value:.8f}",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
