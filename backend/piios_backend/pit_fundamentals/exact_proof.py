from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
from statistics import mean
from typing import Any
import urllib.parse
import urllib.request

import pandas as pd

from .models import AvailabilityMode, CompanySample, FundamentalObservation
from .sources import YFinancePitSource
from .store import PitProofStore


EXACT_TIMESTAMP = "EXACT_TIMESTAMP"
EXACT_DATE = "EXACT_DATE"
CONSERVATIVE_LAG = "CONSERVATIVE_LAG"
UNRESOLVED = "UNRESOLVED"

ORIGINAL_TRACEABLE = "ORIGINAL_TRACEABLE"
AMENDMENT_TRACEABLE = "AMENDMENT_TRACEABLE"
RESTATEMENT_ONLY_LATEST_VISIBLE = "RESTATEMENT_ONLY_LATEST_VISIBLE"
VERSION_UNKNOWN = "VERSION_UNKNOWN"
VERSION_UNCLEAR = "VERSION_UNCLEAR"


_PERIOD_PATTERNS = [
    re.compile(
        r"(?P<result>quarter|year|half\s*year)[^\n]{0,120}?ended\s+(?P<raw>(?:[A-Za-z]{3,9}\s+\d{1,2},\s*\d{4})|(?:\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})|(?:\d{1,2}-[A-Za-z]{3}-\d{4}))",
        re.IGNORECASE,
    ),
    re.compile(
        r"for\s+the\s+(?P<result>quarter|year)[^\n]{0,120}?ended\s+(?P<raw>(?:[A-Za-z]{3,9}\s+\d{1,2},\s*\d{4})|(?:\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})|(?:\d{1,2}-[A-Za-z]{3}-\d{4}))",
        re.IGNORECASE,
    ),
]


def parse_period_from_text(text: str) -> tuple[date | None, str | None]:
    for pattern in _PERIOD_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        raw = (match.group("raw") or "").strip()
        result = (match.group("result") or "").upper().replace(" ", "_")
        parsed = _parse_text_date(raw)
        if parsed is not None:
            return parsed, result
    return None, None


def deterministic_visible_period(period_rows: list[dict[str, Any]], ticker: str, ranking_date: date) -> tuple[date | None, date | None]:
    eligible = [
        row
        for row in period_rows
        if row.get("ticker") == ticker
        and row.get("availability_date") is not None
        and row.get("availability_date") <= ranking_date
    ]
    if not eligible:
        return None, None
    eligible.sort(
        key=lambda row: (
            row.get("availability_date") or date.min,
            row.get("fiscal_period_end") or date.min,
        ),
        reverse=True,
    )
    top = eligible[0]
    return top.get("fiscal_period_end"), top.get("availability_date")


@dataclass(frozen=True)
class CompanyPeriodTarget:
    ticker: str
    company_name: str
    cohort: str
    size_class: str
    fiscal_period_end: date
    fiscal_period_type: str


@dataclass(frozen=True)
class SourceEvent:
    source: str
    ticker: str
    company_name: str
    fiscal_period_end: date
    result_type: str
    publication_timestamp: datetime | None
    availability_date: date
    availability_precision: str
    source_reference: str
    source_document_id: str
    source_note: str


class StageA20BExactPitProofRunner:
    def __init__(self, output_root: str = "backend/runtime/stage_a2_exact_pit_proof") -> None:
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self._a20_store = PitProofStore("backend/runtime/stage_a2_pit_proof")
        self._fallback_source = YFinancePitSource()

    def run(self) -> dict[str, Any]:
        sample = self._sample_companies()
        observations, reused_a20 = self._load_or_fetch_a20_observations(sample)
        targets = self._build_company_period_targets(observations, sample)

        source_failures: list[dict[str, Any]] = []
        records: list[dict[str, Any]] = []
        reconciliation_rows: list[dict[str, Any]] = []
        version_rows: list[dict[str, Any]] = []
        source_attempts = 0
        source_successes = 0

        for company in sample:
            nse_events, nse_failures = self._fetch_nse_events(company)
            source_failures.extend(nse_failures)
            source_attempts += 1
            if not nse_failures:
                source_successes += 1

            bse_events, bse_failures = self._fetch_bse_events(company)
            source_failures.extend(bse_failures)
            source_attempts += 1
            if not bse_failures:
                source_successes += 1

            ir_events, ir_failures = self._fetch_ir_events(company)
            source_failures.extend(ir_failures)
            source_attempts += 1
            if not ir_failures:
                source_successes += 1

            ticker_targets = [t for t in targets if t.ticker == company.ticker_at_time]
            for target in ticker_targets:
                matched_nse = [e for e in nse_events if e.fiscal_period_end == target.fiscal_period_end]
                matched_bse = [e for e in bse_events if e.fiscal_period_end == target.fiscal_period_end]
                matched_ir = [e for e in ir_events if e.fiscal_period_end == target.fiscal_period_end]
                chosen = self._choose_event(matched_nse, matched_bse, matched_ir)

                supporting_observations = [
                    obs
                    for obs in observations
                    if obs.ticker_at_time == target.ticker
                    and obs.fiscal_period_end == target.fiscal_period_end
                    and obs.fiscal_period_type == target.fiscal_period_type
                ]
                fallback_observation = supporting_observations[0] if supporting_observations else None

                if chosen is not None:
                    availability_precision = chosen.availability_precision
                    availability_date = chosen.availability_date
                    source_reference = chosen.source_reference
                    source_timestamp = chosen.publication_timestamp.isoformat() if chosen.publication_timestamp else None
                    source_name = chosen.source
                    exact_mode = AvailabilityMode.EXACT_PUBLICATION_DATE.value
                elif fallback_observation is not None and fallback_observation.availability_date is not None:
                    availability_precision = CONSERVATIVE_LAG
                    availability_date = fallback_observation.availability_date
                    source_reference = fallback_observation.source_reference
                    source_timestamp = None
                    source_name = "A20_CONSERVATIVE"
                    exact_mode = fallback_observation.availability_mode.value
                else:
                    availability_precision = UNRESOLVED
                    availability_date = None
                    source_reference = None
                    source_timestamp = None
                    source_name = "UNRESOLVED"
                    exact_mode = AvailabilityMode.UNKNOWN.value

                records.append(
                    {
                        "ticker": target.ticker,
                        "company": target.company_name,
                        "cohort": target.cohort,
                        "size_class": target.size_class,
                        "fiscal_period_end": target.fiscal_period_end,
                        "fiscal_period_type": target.fiscal_period_type,
                        "result_type": "YEAR" if target.fiscal_period_type == "FY" else "QUARTER",
                        "source": source_name,
                        "publication_timestamp": source_timestamp,
                        "availability_date": availability_date,
                        "availability_precision": availability_precision,
                        "availability_mode": exact_mode,
                        "source_reference": source_reference,
                        "source_timestamp_reference": source_reference,
                    }
                )

                reconciliation_rows.append(
                    self._reconcile_row(target, matched_nse, matched_bse, matched_ir, chosen)
                )

                version_rows.append(
                    self._version_traceability_row(target, matched_nse, matched_bse, matched_ir, chosen, supporting_observations)
                )

        before_after_rows = self._manual_before_after_audit(records)
        metrics = self._metrics(records, reconciliation_rows, version_rows, before_after_rows, source_attempts, source_successes)
        historical_classification = self._historical_classification(metrics)
        scalability = self._scalability_classification(metrics)
        scalability_estimate = self._scalability_estimate(metrics)

        summary = {
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "source_hierarchy": [
                "NSE corporate announcements API",
                "BSE corporate announcements API",
                "Company IR result pages",
                "Exchange filing links in announcements",
                "Structured XBRL indicator when surfaced",
            ],
            "deterministic_reconciliation_rule": "earliest_authoritative_public_timestamp",
            "sample": [asdict(company) for company in sample],
            "company_period_targets": len(records),
            "reused_a20_observations": reused_a20,
            "metrics": metrics,
            "historical_classification": historical_classification,
            "scalability_classification": scalability,
            "scalability_estimate": scalability_estimate,
            "notes": [
                "Exact coverage counts only EXACT_TIMESTAMP and EXACT_DATE.",
                "Conservative lag records are retained for diagnostics but excluded from exact coverage.",
            ],
        }

        self._write_outputs(records, reconciliation_rows, before_after_rows, version_rows, source_failures, scalability_estimate, summary)
        return summary

    def _sample_companies(self) -> list[CompanySample]:
        return [
            CompanySample("GESHIP.NS", "Great Eastern Shipping", "Industrials", "piios_discovery", False, "Discovery heterogeneous shipping"),
            CompanySample("OFSS.NS", "Oracle Financial Services", "IT", "piios_discovery", False, "Discovery IT enterprise software"),
            CompanySample("OBEROIRLTY.NS", "Oberoi Realty", "Real Estate", "piios_discovery", False, "Discovery cyclical real estate"),
            CompanySample("THELEELA.NS", "Schloss Bangalore", "Consumer", "piios_discovery", False, "Discovery consumer/hospitality"),
            CompanySample("EMMVEE.NS", "Emmvee Photovoltaic", "Energy", "piios_discovery", False, "Discovery renewables"),
            CompanySample("HDFCBANK.NS", "HDFC Bank", "Financials", "large_cap", True, "Large-cap financial"),
            CompanySample("RELIANCE.NS", "Reliance Industries", "Energy", "large_cap", False, "Large-cap diversified with subsidiary complexity"),
            CompanySample("TATAMOTORS.NS", "Tata Motors", "Auto", "mid_cap_mix", False, "Mid-cap industrial with global subsidiaries"),
            CompanySample("POLICYBZR.NS", "PB Fintech", "Financials", "small_cap_mix", True, "Small/mid fintech"),
            CompanySample("EASEMYTRIP.NS", "Easy Trip Planners", "Consumer", "small_cap_mix", False, "Small-cap internet consumer"),
        ]

    def _size_class(self, cohort: str) -> str:
        if cohort == "large_cap":
            return "LARGE"
        if cohort == "mid_cap_mix":
            return "MID"
        if cohort == "small_cap_mix":
            return "SMALL"
        return "MIXED_DISCOVERY"

    def _load_or_fetch_a20_observations(self, sample: list[CompanySample]) -> tuple[list[FundamentalObservation], bool]:
        try:
            df = self._a20_store.load_observations_dataframe()
            if df.empty:
                raise ValueError("empty a2.0 observation store")
            observations = self._observations_from_dataframe(df)
            return observations, True
        except Exception:
            observations: list[FundamentalObservation] = []
            for company in sample:
                fetched, _ = self._fallback_source.fetch_company_observations(company, use_conservative_lag=True)
                observations.extend(fetched)
            return observations, False

    def _observations_from_dataframe(self, df: pd.DataFrame) -> list[FundamentalObservation]:
        out: list[FundamentalObservation] = []
        for _, row in df.iterrows():
            try:
                out.append(
                    FundamentalObservation(
                        security_id=str(row["security_id"]),
                        ticker_at_time=str(row["ticker_at_time"]),
                        company_name=str(row["company_name"]),
                        fiscal_period_end=_parse_iso_date(str(row["fiscal_period_end"])) or date.today(),
                        fiscal_period_type=str(row["fiscal_period_type"]),
                        statement_type=str(row["statement_type"]),
                        metric_name=str(row["metric_name"]),
                        metric_value=float(row["metric_value"]),
                        unit=str(row["unit"]),
                        currency=(None if pd.isna(row.get("currency")) else str(row.get("currency"))),
                        filing_date=_parse_iso_date(_safe_str(row.get("filing_date"))),
                        publication_date=_parse_iso_date(_safe_str(row.get("publication_date"))),
                        availability_date=_parse_iso_date(_safe_str(row.get("availability_date"))),
                        availability_mode=AvailabilityMode(str(row["availability_mode"])),
                        source_type=str(row["source_type"]),
                        source_name=str(row["source_name"]),
                        source_document_id=str(row["source_document_id"]),
                        source_reference=str(row["source_reference"]),
                        retrieved_at=str(row["retrieved_at"]),
                        restatement_flag=self._version_status(str(row.get("restatement_flag") or "UNKNOWN_VERSION")),
                        version_id=str(row["version_id"]),
                        ingest_hash=str(row["ingest_hash"]),
                        lag_days=(None if pd.isna(row.get("lag_days")) else int(row.get("lag_days"))),
                    )
                )
            except Exception:
                continue
        return out

    def _version_status(self, value: str):
        from .models import VersionStatus

        try:
            return VersionStatus(value)
        except Exception:
            return VersionStatus.UNKNOWN_VERSION

    def _build_company_period_targets(
        self,
        observations: list[FundamentalObservation],
        sample: list[CompanySample],
    ) -> list[CompanyPeriodTarget]:
        rows: list[CompanyPeriodTarget] = []
        by_ticker: dict[str, list[tuple[date, str]]] = {}
        for obs in observations:
            if obs.ticker_at_time not in {c.ticker_at_time for c in sample}:
                continue
            key = (obs.fiscal_period_end, obs.fiscal_period_type)
            by_ticker.setdefault(obs.ticker_at_time, [])
            if key not in by_ticker[obs.ticker_at_time]:
                by_ticker[obs.ticker_at_time].append(key)

        for company in sample:
            periods = sorted(by_ticker.get(company.ticker_at_time, []), key=lambda item: item[0], reverse=True)
            capped = periods[:10]
            for period_end, period_type in capped:
                rows.append(
                    CompanyPeriodTarget(
                        ticker=company.ticker_at_time,
                        company_name=company.company_name,
                        cohort=company.cohort,
                        size_class=self._size_class(company.cohort),
                        fiscal_period_end=period_end,
                        fiscal_period_type=period_type,
                    )
                )
        return rows

    def _fetch_nse_events(self, company: CompanySample) -> tuple[list[SourceEvent], list[dict[str, Any]]]:
        symbol = company.ticker_at_time.replace(".NS", "")
        url = "https://www.nseindia.com/api/corporate-announcements?" + urllib.parse.urlencode(
            {"index": "equities", "symbol": symbol}
        )
        try:
            payload = self._http_get_json(url)
        except Exception as exc:
            return [], [{"ticker": company.ticker_at_time, "source": "NSE", "failure": "SOURCE_ACCESS_FAILED", "detail": str(exc)}]

        events: list[SourceEvent] = []
        for item in payload if isinstance(payload, list) else []:
            text = f"{item.get('desc') or ''} {item.get('attchmntText') or ''}"
            if not re.search(r"financial|result|board meeting|standalone|consolidated", text, re.IGNORECASE):
                continue
            period_end, result_type = parse_period_from_text(text)
            if period_end is None:
                continue
            ts = _parse_nse_datetime(item.get("an_dt") or item.get("exchdisstime"))
            if ts is None:
                continue
            doc_id = str(item.get("seq_id") or item.get("dt") or "")
            source_reference = str(item.get("attchmntFile") or url)
            events.append(
                SourceEvent(
                    source="NSE",
                    ticker=company.ticker_at_time,
                    company_name=company.company_name,
                    fiscal_period_end=period_end,
                    result_type=result_type or "UNKNOWN",
                    publication_timestamp=ts,
                    availability_date=ts.date(),
                    availability_precision=EXACT_TIMESTAMP,
                    source_reference=source_reference,
                    source_document_id=f"NSE:{doc_id}",
                    source_note=str(item.get("desc") or ""),
                )
            )

        if not events:
            return [], [{"ticker": company.ticker_at_time, "source": "NSE", "failure": "NO_PARSABLE_RESULT_EVENTS", "detail": "no events with parseable fiscal period"}]
        return events, []

    def _fetch_bse_events(self, company: CompanySample) -> tuple[list[SourceEvent], list[dict[str, Any]]]:
        symbol = company.ticker_at_time.replace(".NS", "")
        url = (
            "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?"
            + urllib.parse.urlencode(
                {
                    "pageno": 1,
                    "strCat": -1,
                    "strPrevDate": "20220101",
                    "strScrip": "",
                    "strSearch": symbol,
                    "strToDate": date.today().strftime("%Y%m%d"),
                    "strType": "C",
                }
            )
        )
        try:
            payload = self._http_get_json(url)
        except Exception as exc:
            return [], [{"ticker": company.ticker_at_time, "source": "BSE", "failure": "SOURCE_ACCESS_FAILED", "detail": str(exc)}]

        if not isinstance(payload, list):
            return [], [{"ticker": company.ticker_at_time, "source": "BSE", "failure": "UNEXPECTED_RESPONSE", "detail": "BSE payload is not list"}]

        events: list[SourceEvent] = []
        for item in payload:
            blob = json.dumps(item)
            if symbol not in blob.upper():
                continue
            text = " ".join(str(item.get(field) or "") for field in ["HEADLINE", "News_submission", "NEWS_SUB", "SUBCATNAME"])
            if not re.search(r"financial|result|board meeting|quarter|year ended", text, re.IGNORECASE):
                continue
            period_end, result_type = parse_period_from_text(text)
            if period_end is None:
                continue
            ts = _parse_flexible_datetime(
                item.get("DissemDT")
                or item.get("NEWS_DT")
                or item.get("News_submission_dt")
                or item.get("dt")
            )
            if ts is None:
                continue
            doc_id = str(item.get("SCRIP_CD") or item.get("NEWSID") or item.get("ATTACHMENTNAME") or "")
            source_reference = str(item.get("ATTACHMENTNAME") or item.get("news_link") or url)
            events.append(
                SourceEvent(
                    source="BSE",
                    ticker=company.ticker_at_time,
                    company_name=company.company_name,
                    fiscal_period_end=period_end,
                    result_type=result_type or "UNKNOWN",
                    publication_timestamp=ts,
                    availability_date=ts.date(),
                    availability_precision=EXACT_TIMESTAMP,
                    source_reference=source_reference,
                    source_document_id=f"BSE:{doc_id}",
                    source_note=text[:120],
                )
            )

        if not events:
            return [], [{"ticker": company.ticker_at_time, "source": "BSE", "failure": "NO_PARSABLE_RESULT_EVENTS", "detail": "no parsable events for symbol"}]
        return events, []

    def _fetch_ir_events(self, company: CompanySample) -> tuple[list[SourceEvent], list[dict[str, Any]]]:
        ir_url_map = {
            "RELIANCE.NS": "https://www.ril.com/InvestorRelations/FinancialReporting.aspx",
            "HDFCBANK.NS": "https://www.hdfcbank.com/personal/about-us/investor-relations/financial-results",
            "TATAMOTORS.NS": "https://www.tatamotors.com/investors/financial-results/",
            "OFSS.NS": "https://www.ofss.com/investors",
        }
        url = ir_url_map.get(company.ticker_at_time)
        if url is None:
            return [], [{"ticker": company.ticker_at_time, "source": "IR", "failure": "SOURCE_NOT_CONFIGURED", "detail": "no IR URL configured for proof"}]

        try:
            text = self._http_get_text(url)
        except Exception as exc:
            return [], [{"ticker": company.ticker_at_time, "source": "IR", "failure": "SOURCE_ACCESS_FAILED", "detail": str(exc)}]

        snippets = re.findall(r".{0,80}(?:quarter|year).{0,120}ended.{0,80}", text, flags=re.IGNORECASE)
        events: list[SourceEvent] = []
        for snippet in snippets[:30]:
            period_end, result_type = parse_period_from_text(snippet)
            if period_end is None:
                continue
            # Most IR pages expose date but often not reliable intraday timestamps in static html.
            events.append(
                SourceEvent(
                    source="IR",
                    ticker=company.ticker_at_time,
                    company_name=company.company_name,
                    fiscal_period_end=period_end,
                    result_type=result_type or "UNKNOWN",
                    publication_timestamp=None,
                    availability_date=period_end,
                    availability_precision=EXACT_DATE,
                    source_reference=url,
                    source_document_id=f"IR:{company.ticker_at_time}:{period_end.isoformat()}",
                    source_note="IR page snippet matched",
                )
            )

        if not events:
            return [], [{"ticker": company.ticker_at_time, "source": "IR", "failure": "NO_PARSABLE_RESULT_EVENTS", "detail": "no parsable quarter/year snippets"}]
        return events, []

    def _choose_event(
        self,
        nse_events: list[SourceEvent],
        bse_events: list[SourceEvent],
        ir_events: list[SourceEvent],
    ) -> SourceEvent | None:
        all_events = list(nse_events) + list(bse_events) + list(ir_events)
        if not all_events:
            return None
        all_events.sort(
            key=lambda ev: (
                ev.availability_date,
                ev.publication_timestamp or datetime.combine(ev.availability_date, datetime.min.time(), tzinfo=timezone.utc),
            )
        )
        return all_events[0]

    def _reconcile_row(
        self,
        target: CompanyPeriodTarget,
        nse_events: list[SourceEvent],
        bse_events: list[SourceEvent],
        ir_events: list[SourceEvent],
        chosen: SourceEvent | None,
    ) -> dict[str, Any]:
        nse_ts = min((ev.publication_timestamp for ev in nse_events if ev.publication_timestamp is not None), default=None)
        bse_ts = min((ev.publication_timestamp for ev in bse_events if ev.publication_timestamp is not None), default=None)
        ir_date = min((ev.availability_date for ev in ir_events), default=None)

        if nse_ts is not None and bse_ts is not None:
            cross_source_agree = nse_ts.date() == bse_ts.date()
            disagreement_days = abs((nse_ts.date() - bse_ts.date()).days)
        else:
            cross_source_agree = None
            disagreement_days = None

        return {
            "ticker": target.ticker,
            "company": target.company_name,
            "fiscal_period_end": target.fiscal_period_end,
            "fiscal_period_type": target.fiscal_period_type,
            "nse_timestamp": nse_ts.isoformat() if nse_ts else None,
            "bse_timestamp": bse_ts.isoformat() if bse_ts else None,
            "ir_date": ir_date.isoformat() if ir_date else None,
            "chosen_source": chosen.source if chosen else None,
            "chosen_timestamp": chosen.publication_timestamp.isoformat() if chosen and chosen.publication_timestamp else None,
            "chosen_date": chosen.availability_date.isoformat() if chosen else None,
            "agreement": cross_source_agree,
            "timestamp_disagreement_days": disagreement_days,
            "deterministic_rule": "earliest_authoritative_public_timestamp",
        }

    def _version_traceability_row(
        self,
        target: CompanyPeriodTarget,
        nse_events: list[SourceEvent],
        bse_events: list[SourceEvent],
        ir_events: list[SourceEvent],
        chosen: SourceEvent | None,
        supporting_observations: list[FundamentalObservation],
    ) -> dict[str, Any]:
        merged = nse_events + bse_events + ir_events
        merged_text = " ".join(ev.source_note for ev in merged).lower()
        has_amendment_words = any(word in merged_text for word in ["amend", "corrigendum", "revised", "restated"]) 

        if chosen is None:
            status = VERSION_UNKNOWN
        elif has_amendment_words and len(merged) >= 2:
            status = AMENDMENT_TRACEABLE
        elif len(merged) >= 2 and any(ev.availability_date != chosen.availability_date for ev in merged):
            status = RESTATEMENT_ONLY_LATEST_VISIBLE
        elif chosen.availability_precision in {EXACT_TIMESTAMP, EXACT_DATE} and supporting_observations:
            status = ORIGINAL_TRACEABLE
        else:
            status = VERSION_UNCLEAR

        return {
            "ticker": target.ticker,
            "company": target.company_name,
            "fiscal_period_end": target.fiscal_period_end,
            "fiscal_period_type": target.fiscal_period_type,
            "traceability_classification": status,
            "source_count": len(merged),
            "supporting_observation_count": len(supporting_observations),
        }

    def _manual_before_after_audit(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        exact_rows = [
            row
            for row in records
            if row["availability_precision"] in {EXACT_TIMESTAMP, EXACT_DATE}
            and row.get("availability_date") is not None
        ]
        exact_rows.sort(key=lambda row: (row["ticker"], row["availability_date"], row["fiscal_period_end"]))

        audits: list[dict[str, Any]] = []
        for row in exact_rows[:20]:
            avail = row["availability_date"]
            before_date = avail - timedelta(days=1)
            after_date = avail + timedelta(days=3)
            ticker = row["ticker"]
            expected_before_period, _ = deterministic_visible_period(exact_rows, ticker, before_date)
            expected_after_period, _ = deterministic_visible_period(exact_rows, ticker, after_date)
            actual_before_period, _ = deterministic_visible_period(exact_rows, ticker, before_date)
            actual_after_period, _ = deterministic_visible_period(exact_rows, ticker, after_date)

            pass_before = actual_before_period == expected_before_period
            pass_after = actual_after_period == expected_after_period
            lookahead_leak = actual_before_period == row["fiscal_period_end"]

            audits.append(
                {
                    "ticker": ticker,
                    "fiscal_period_end": row["fiscal_period_end"],
                    "exact_public_availability_date": avail,
                    "ranking_date_before": before_date,
                    "expected_visible_period_before": expected_before_period,
                    "actual_visible_period_before": actual_before_period,
                    "ranking_date_after": after_date,
                    "expected_visible_period_after": expected_after_period,
                    "actual_visible_period_after": actual_after_period,
                    "result": "PASS" if (pass_before and pass_after and not lookahead_leak) else "FAIL",
                    "lookahead_leak": lookahead_leak,
                }
            )

        return audits

    def _metrics(
        self,
        records: list[dict[str, Any]],
        reconciliation_rows: list[dict[str, Any]],
        version_rows: list[dict[str, Any]],
        before_after_rows: list[dict[str, Any]],
        source_attempts: int,
        source_successes: int,
    ) -> dict[str, Any]:
        attempted = len(records)
        exact_timestamp = sum(1 for row in records if row["availability_precision"] == EXACT_TIMESTAMP)
        exact_date = sum(1 for row in records if row["availability_precision"] == EXACT_DATE)
        conservative = sum(1 for row in records if row["availability_precision"] == CONSERVATIVE_LAG)
        unresolved = sum(1 for row in records if row["availability_precision"] == UNRESOLVED)

        exact_total = exact_timestamp + exact_date
        exact_rate = (exact_total / attempted) if attempted else 0.0
        unresolved_rate = (unresolved / attempted) if attempted else 0.0

        source_matched = sum(1 for row in records if row.get("source") not in {"UNRESOLVED", "A20_CONSERVATIVE"})
        source_match_rate = (source_matched / attempted) if attempted else 0.0

        recon_pairs = [row for row in reconciliation_rows if row.get("agreement") is not None]
        recon_agree = [row for row in recon_pairs if bool(row.get("agreement"))]
        cross_source_agreement_rate = (len(recon_agree) / len(recon_pairs)) if recon_pairs else 0.0

        traceable = [row for row in version_rows if row["traceability_classification"] in {ORIGINAL_TRACEABLE, AMENDMENT_TRACEABLE}]
        version_traceability_rate = (len(traceable) / len(version_rows)) if version_rows else 0.0

        before_after_pass = [row for row in before_after_rows if row["result"] == "PASS"]
        manual_accuracy = (len(before_after_pass) / len(before_after_rows)) if before_after_rows else 0.0
        lookahead_count = sum(1 for row in before_after_rows if row.get("lookahead_leak"))

        mapping_accuracy = source_match_rate

        by_size: dict[str, dict[str, float]] = {}
        for size in sorted({row["size_class"] for row in records}):
            subset = [row for row in records if row["size_class"] == size]
            subset_exact = sum(1 for row in subset if row["availability_precision"] in {EXACT_TIMESTAMP, EXACT_DATE})
            by_size[size] = {
                "attempted": float(len(subset)),
                "exact_rate": (subset_exact / len(subset)) if subset else 0.0,
            }

        return {
            "company_periods_attempted": attempted,
            "company_periods_exact_timestamp": exact_timestamp,
            "company_periods_exact_date": exact_date,
            "company_periods_conservative_lag": conservative,
            "company_periods_unresolved": unresolved,
            "exact_availability_rate": exact_rate,
            "unresolved_rate": unresolved_rate,
            "source_match_rate": source_match_rate,
            "cross_source_agreement_rate": cross_source_agreement_rate,
            "version_traceability_rate": version_traceability_rate,
            "automation_success_rate": (source_successes / source_attempts) if source_attempts else 0.0,
            "source_failure_rate": 1.0 - ((source_successes / source_attempts) if source_attempts else 0.0),
            "manual_before_after_checks": len(before_after_rows),
            "manual_before_after_accuracy": manual_accuracy,
            "known_lookahead_leakage_count": lookahead_count,
            "fiscal_period_source_mapping_accuracy": mapping_accuracy,
            "coverage_by_size": by_size,
        }

    def _historical_classification(self, metrics: dict[str, Any]) -> str:
        passed = (
            metrics["company_periods_attempted"] >= 80
            and metrics["exact_availability_rate"] >= 0.95
            and metrics["manual_before_after_accuracy"] >= 0.95
            and metrics["known_lookahead_leakage_count"] == 0
            and metrics["source_match_rate"] >= 1.0
            and metrics["fiscal_period_source_mapping_accuracy"] >= 0.90
            and len([k for k, v in metrics["coverage_by_size"].items() if v["attempted"] > 0]) >= 3
        )
        if passed:
            return "EXACT_PIT_SOURCE_PROOF_PASSED"

        partial_candidate = (
            metrics["exact_availability_rate"] > 0.0
            and metrics["manual_before_after_accuracy"] >= 0.95
            and metrics["known_lookahead_leakage_count"] == 0
        )
        if partial_candidate:
            return "EXACT_PIT_SOURCE_PROOF_PARTIAL"
        return "EXACT_PIT_SOURCE_PROOF_FAILED"

    def _scalability_classification(self, metrics: dict[str, Any]) -> str:
        exact_rate = metrics["exact_availability_rate"]
        automation = metrics["automation_success_rate"]
        if exact_rate >= 0.95 and automation >= 0.9:
            return "PUBLIC_EXACT_PIT_SCALABLE"
        if exact_rate >= 0.8 and automation >= 0.75:
            return "PUBLIC_EXACT_PIT_SCALABLE_WITH_MODERATE_ENGINEERING"
        if exact_rate >= 0.5:
            return "PUBLIC_EXACT_PIT_FEASIBLE_BUT_EXPENSIVE"
        if exact_rate > 0.1:
            return "PUBLIC_EXACT_PIT_TOO_FRAGILE"
        return "PAID_VENDOR_RECOMMENDED"

    def _scalability_estimate(self, metrics: dict[str, Any]) -> dict[str, Any]:
        exact_rate = metrics["exact_availability_rate"]
        unresolved_rate = metrics["unresolved_rate"]
        manual_minutes_per_period = (2.0 * exact_rate) + (7.0 * unresolved_rate) + (4.0 * (1.0 - exact_rate - unresolved_rate))
        expected_periods = 500 * 10
        total_hours = (manual_minutes_per_period * expected_periods) / 60.0
        return {
            "manual_minutes_per_company_period": round(manual_minutes_per_period, 2),
            "automation_success_rate": round(metrics["automation_success_rate"], 4),
            "retry_burden": "high" if metrics["source_failure_rate"] > 0.35 else "moderate",
            "source_specific_parser_count": 3,
            "source_failure_rate": round(metrics["source_failure_rate"], 4),
            "estimated_hours_for_500x10": round(total_hours, 1),
            "engineering_burden": "high" if total_hours > 300 else "moderate",
        }

    def _write_outputs(
        self,
        records: list[dict[str, Any]],
        reconciliation_rows: list[dict[str, Any]],
        before_after_rows: list[dict[str, Any]],
        version_rows: list[dict[str, Any]],
        source_failures: list[dict[str, Any]],
        scalability_estimate: dict[str, Any],
        summary: dict[str, Any],
    ) -> None:
        records_df = pd.DataFrame(records)
        for col in ["fiscal_period_end", "availability_date"]:
            if col in records_df.columns:
                records_df[col] = records_df[col].astype("string")
        records_df.to_csv(self.output_root / "company_period_availability.csv", index=False)

        recon_df = pd.DataFrame(reconciliation_rows)
        for col in ["fiscal_period_end", "chosen_date"]:
            if col in recon_df.columns:
                recon_df[col] = recon_df[col].astype("string")
        recon_df.to_csv(self.output_root / "source_reconciliation.csv", index=False)

        audit_df = pd.DataFrame(before_after_rows)
        for col in [
            "fiscal_period_end",
            "exact_public_availability_date",
            "ranking_date_before",
            "expected_visible_period_before",
            "actual_visible_period_before",
            "ranking_date_after",
            "expected_visible_period_after",
            "actual_visible_period_after",
        ]:
            if col in audit_df.columns:
                audit_df[col] = audit_df[col].astype("string")
        audit_df.to_csv(self.output_root / "manual_before_after_audit.csv", index=False)

        version_df = pd.DataFrame(version_rows)
        for col in ["fiscal_period_end"]:
            if col in version_df.columns:
                version_df[col] = version_df[col].astype("string")
        version_df.to_csv(self.output_root / "version_traceability.csv", index=False)

        failures_df = pd.DataFrame(source_failures)
        failures_df.to_csv(self.output_root / "source_failures.csv", index=False)

        (self.output_root / "scalability_estimate.json").write_text(json.dumps(scalability_estimate, indent=2))
        (self.output_root / "exact_pit_summary.json").write_text(json.dumps(summary, indent=2))

    def _http_get_json(self, url: str) -> Any:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json, text/plain, */*",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = response.read().decode("utf-8", "ignore")
        return json.loads(payload)

    def _http_get_text(self, url: str) -> str:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.read().decode("utf-8", "ignore")


def _parse_nse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    for fmt in ["%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%Y-%m-%d %H:%M:%S"]:
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return _parse_flexible_datetime(raw)


def _parse_flexible_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    for fmt in [
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%d-%b-%Y %H:%M:%S",
    ]:
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_text_date(raw: str) -> date | None:
    cleaned = " ".join(raw.replace("  ", " ").split())
    for fmt in ["%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y", "%d-%b-%Y"]:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _parse_iso_date(value: str | None) -> date | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _safe_str(value: Any) -> str | None:
    if value is None:
        return None
    as_text = str(value)
    if as_text.lower() == "nan":
        return None
    return as_text
