from __future__ import annotations

from datetime import date, datetime, timezone
from statistics import median
from typing import Any

import pandas as pd
import yfinance as yf

from .models import AvailabilityMode, CompanySample, FundamentalObservation, SourceQualityRecord, VersionStatus
from .normalization import (
    conservative_availability_date,
    infer_fiscal_period_type,
    make_ingest_hash,
    make_version_id,
    statement_metric_map,
)


FAIL_SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
FAIL_PUBLICATION_DATE_UNAVAILABLE = "PUBLICATION_DATE_UNAVAILABLE"
FAIL_PARSE_FAILURE = "PARSE_FAILURE"
FAIL_METRIC_UNAVAILABLE = "METRIC_UNAVAILABLE"
FAIL_VERSION_UNCLEAR = "VERSION_UNCLEAR"
FAIL_LOOKAHEAD_RISK = "LOOKAHEAD_RISK"
FAIL_SECTOR_INAPPLICABLE = "SECTOR_INAPPLICABLE"
FAIL_INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class YFinancePitSource:
    def source_quality(self) -> list[SourceQualityRecord]:
        return [
            SourceQualityRecord(
                source="yfinance_financial_statements",
                access_method="public_api_wrapper",
                publicly_accessible=True,
                structured=True,
                timestamp_quality="period_end_reliable_publication_often_missing",
                licensing_concern="verify_yahoo_terms_before_redistribution",
                automation_feasibility="moderate",
                rate_limit_concern="moderate",
                pit_correctness="partial",
                history_depth="moderate",
                restatement_visibility="limited",
            )
        ]

    def fetch_company_observations(
        self,
        company: CompanySample,
        *,
        use_conservative_lag: bool = True,
    ) -> tuple[list[FundamentalObservation], list[dict[str, str]]]:
        failures: list[dict[str, str]] = []
        ticker = company.ticker_at_time
        try:
            tk = yf.Ticker(ticker)
        except Exception as exc:
            return [], [{"ticker": ticker, "failure": FAIL_SOURCE_UNAVAILABLE, "detail": str(exc)}]

        earnings_dates = self._get_earnings_dates(tk)
        observations: list[FundamentalObservation] = []
        for statement_type, scope, frame in self._statement_frames(tk):
            if frame is None or frame.empty:
                failures.append(
                    {
                        "ticker": ticker,
                        "failure": FAIL_METRIC_UNAVAILABLE,
                        "detail": f"empty_{statement_type}_{scope}",
                    }
                )
                continue

            period_type = infer_fiscal_period_type(scope)
            metric_map = statement_metric_map(statement_type)
            for source_metric, (metric_name, unit) in metric_map.items():
                if source_metric not in frame.index:
                    continue
                series = frame.loc[source_metric]
                if isinstance(series, pd.Series):
                    values_iter = series.items()
                else:
                    continue

                for period_end_raw, metric_value_raw in values_iter:
                    metric_value = self._safe_float(metric_value_raw)
                    if metric_value is None:
                        continue
                    period_end = self._to_date(period_end_raw)
                    if period_end is None:
                        failures.append(
                            {
                                "ticker": ticker,
                                "failure": FAIL_PARSE_FAILURE,
                                "detail": f"unparseable_period_{period_end_raw}",
                            }
                        )
                        continue

                    publication_date = self._nearest_publication_date(period_end, earnings_dates)
                    filing_date = publication_date
                    lag_days = None
                    if publication_date is not None:
                        availability_date = publication_date
                        availability_mode = AvailabilityMode.EXACT_PUBLICATION_DATE
                    elif use_conservative_lag:
                        availability_date, lag_days = conservative_availability_date(period_end, period_type, statement_type)
                        availability_mode = AvailabilityMode.CONSERVATIVE_LAG
                    else:
                        availability_date = None
                        availability_mode = AvailabilityMode.UNKNOWN
                        failures.append(
                            {
                                "ticker": ticker,
                                "failure": FAIL_PUBLICATION_DATE_UNAVAILABLE,
                                "detail": f"{statement_type}:{metric_name}:{period_end.isoformat()}",
                            }
                        )

                    source_document_id = f"{ticker}:{statement_type}:{scope}:{period_end.isoformat()}"
                    source_reference = f"yfinance:{ticker}:{statement_type}:{scope}"
                    version_id = make_version_id(
                        ticker=ticker,
                        statement_type=statement_type,
                        metric_name=metric_name,
                        period_end=period_end,
                        source_document_id=source_document_id,
                        metric_value=metric_value,
                        availability_date=availability_date,
                    )
                    ingest_hash = make_ingest_hash(
                        ticker=ticker,
                        metric_name=metric_name,
                        period_end=period_end,
                        availability_mode=availability_mode,
                        source_reference=source_reference,
                        metric_value=metric_value,
                    )
                    observations.append(
                        FundamentalObservation(
                            security_id=ticker,
                            ticker_at_time=ticker,
                            company_name=company.company_name,
                            fiscal_period_end=period_end,
                            fiscal_period_type=period_type,
                            statement_type=statement_type,
                            metric_name=metric_name,
                            metric_value=metric_value,
                            unit=unit,
                            currency="INR",
                            filing_date=filing_date,
                            publication_date=publication_date,
                            availability_date=availability_date,
                            availability_mode=availability_mode,
                            source_type="PUBLIC_API",
                            source_name="yfinance",
                            source_document_id=source_document_id,
                            source_reference=source_reference,
                            retrieved_at=now_iso(),
                            restatement_flag=VersionStatus.UNKNOWN_VERSION,
                            version_id=version_id,
                            ingest_hash=ingest_hash,
                            lag_days=lag_days,
                        )
                    )

        if not observations:
            failures.append({"ticker": ticker, "failure": FAIL_INSUFFICIENT_HISTORY, "detail": "no_observations"})
        return observations, failures

    def _statement_frames(self, tk: yf.Ticker) -> list[tuple[str, str, pd.DataFrame | None]]:
        return [
            ("income", "quarterly", self._load_frame(tk, ["quarterly_income_stmt", "quarterly_financials"])),
            ("income", "annual", self._load_frame(tk, ["income_stmt", "financials"])),
            ("balance", "quarterly", self._load_frame(tk, ["quarterly_balance_sheet"])),
            ("balance", "annual", self._load_frame(tk, ["balance_sheet"])),
            ("cashflow", "quarterly", self._load_frame(tk, ["quarterly_cashflow", "quarterly_cash_flow"])),
            ("cashflow", "annual", self._load_frame(tk, ["cashflow", "cash_flow"])),
        ]

    def _load_frame(self, tk: yf.Ticker, attr_names: list[str]) -> pd.DataFrame | None:
        for name in attr_names:
            try:
                frame = getattr(tk, name)
            except Exception:
                continue
            if isinstance(frame, pd.DataFrame):
                return frame
        return None

    def _get_earnings_dates(self, tk: yf.Ticker) -> list[date]:
        try:
            frame = tk.get_earnings_dates(limit=40)
        except Exception:
            return []
        if frame is None or frame.empty:
            return []
        out: list[date] = []
        if isinstance(frame.index, pd.DatetimeIndex):
            for ts in frame.index:
                out.append(ts.date())
            return sorted(set(out))

        # Fallback if index is not datetime-like.
        for value in frame.get("Earnings Date", []):
            if isinstance(value, pd.Timestamp):
                out.append(value.date())
        return sorted(set(out))

    def _nearest_publication_date(self, period_end: date, earnings_dates: list[date]) -> date | None:
        candidates = [d for d in earnings_dates if d >= period_end and (d - period_end).days <= 150]
        if not candidates:
            return None
        return min(candidates)

    def _to_date(self, value: object) -> date | None:
        if isinstance(value, pd.Timestamp):
            return value.date()
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            ts = pd.Timestamp(value)
            if pd.isna(ts):
                return None
            return ts.date()
        except Exception:
            return None

    def _safe_float(self, value: Any) -> float | None:
        try:
            if value is None or pd.isna(value):
                return None
            return float(value)
        except Exception:
            return None
