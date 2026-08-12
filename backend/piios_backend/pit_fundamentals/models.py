from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from enum import Enum


class AvailabilityMode(str, Enum):
    EXACT_PUBLICATION_DATE = "EXACT_PUBLICATION_DATE"
    EXACT_FILING_DATE = "EXACT_FILING_DATE"
    CONSERVATIVE_LAG = "CONSERVATIVE_LAG"
    UNKNOWN = "UNKNOWN"


class VersionStatus(str, Enum):
    ORIGINAL = "ORIGINAL"
    AMENDED = "AMENDED"
    RESTATED = "RESTATED"
    UNKNOWN_VERSION = "UNKNOWN_VERSION"


@dataclass(frozen=True)
class CompanySample:
    ticker_at_time: str
    company_name: str
    sector: str
    cohort: str
    is_financial: bool
    rationale: str


@dataclass(frozen=True)
class FundamentalObservation:
    security_id: str
    ticker_at_time: str
    company_name: str
    fiscal_period_end: date
    fiscal_period_type: str
    statement_type: str
    metric_name: str
    metric_value: float
    unit: str
    currency: str | None
    filing_date: date | None
    publication_date: date | None
    availability_date: date | None
    availability_mode: AvailabilityMode
    source_type: str
    source_name: str
    source_document_id: str
    source_reference: str
    retrieved_at: str
    restatement_flag: VersionStatus
    version_id: str
    ingest_hash: str
    lag_days: int | None = None

    def to_row(self) -> dict[str, object]:
        row = asdict(self)
        row["fiscal_period_end"] = self.fiscal_period_end.isoformat()
        row["filing_date"] = self.filing_date.isoformat() if self.filing_date else None
        row["publication_date"] = self.publication_date.isoformat() if self.publication_date else None
        row["availability_date"] = self.availability_date.isoformat() if self.availability_date else None
        row["availability_mode"] = self.availability_mode.value
        row["restatement_flag"] = self.restatement_flag.value
        return row


@dataclass(frozen=True)
class SourceQualityRecord:
    source: str
    access_method: str
    publicly_accessible: bool
    structured: bool
    timestamp_quality: str
    licensing_concern: str
    automation_feasibility: str
    rate_limit_concern: str
    pit_correctness: str
    history_depth: str
    restatement_visibility: str


@dataclass(frozen=True)
class JoinAuditRow:
    ticker: str
    ranking_date: date
    expected_latest_period: date | None
    expected_publication_date: date | None
    actual_joined_period: date | None
    actual_availability_date: date | None
    later_filing_excluded: bool
    result: str
    note: str

    def to_row(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "ranking_date": self.ranking_date.isoformat(),
            "expected_latest_period": self.expected_latest_period.isoformat() if self.expected_latest_period else None,
            "expected_publication_date": self.expected_publication_date.isoformat() if self.expected_publication_date else None,
            "actual_joined_period": self.actual_joined_period.isoformat() if self.actual_joined_period else None,
            "actual_availability_date": self.actual_availability_date.isoformat() if self.actual_availability_date else None,
            "later_filing_excluded": self.later_filing_excluded,
            "result": self.result,
            "note": self.note,
        }
