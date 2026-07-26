from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable

from sqlmodel import Session

from piios_backend.core.database import engine
from piios_backend.services.identity import BackendIdentityService
from piios_backend.services.identity_backfill import ClassifiedRecord, classify_resolution, write_backfill_reports
from piios_backend.services.in_memory_store import store


@dataclass(frozen=True)
class CandidateRecord:
    source_type: str
    source_id: str
    ticker: str | None
    currency: str | None


def _collect_candidates() -> list[CandidateRecord]:
    rows: list[CandidateRecord] = []
    for item in store.holdings:
        rows.append(CandidateRecord(source_type="holding", source_id=item.holding_id, ticker=item.ticker, currency=item.currency))
    for item in store.recommendations:
        rows.append(CandidateRecord(source_type="recommendation", source_id=item.recommendation_id, ticker=item.ticker, currency=None))
    for item in store.theses:
        rows.append(CandidateRecord(source_type="thesis", source_id=item.thesis_id, ticker=item.ticker, currency=None))
    return rows
def _evaluate(service: BackendIdentityService, rows: Iterable[CandidateRecord]) -> list[ClassifiedRecord]:
    evaluated: list[ClassifiedRecord] = []
    for row in rows:
        result = service.resolve(
            SimpleNamespace(
                company_id=None,
                security_id=None,
                listing_id=None,
                isin=None,
                exchange=None,
                ticker=row.ticker,
                provider=None,
                provider_identifier=None,
                legacy_asset_id=row.source_id,
                legacy_ticker=row.ticker,
                company_name=None,
                jurisdiction=None,
                trading_currency=row.currency,
                effective_date=date.today(),
            )
        )
        candidates = result.get("candidates", [])
        first_basis = candidates[0]["match_basis"] if candidates else None
        first_company_id = candidates[0]["company_id"] if candidates else None
        first_security_id = candidates[0]["security_id"] if candidates else None
        first_listing_id = candidates[0]["listing_id"] if candidates else None
        classification = classify_resolution(result["status"], len(candidates), first_basis)
        evaluated.append(
            ClassifiedRecord(
                source_type=row.source_type,
                source_id=row.source_id,
                ticker=row.ticker,
                currency=row.currency,
                classification=classification,
                status=result["status"],
                candidate_count=len(candidates),
                match_basis=first_basis,
                company_id=first_company_id,
                security_id=first_security_id,
                listing_id=first_listing_id,
                warnings=list(result.get("warnings", [])),
            )
        )
    return evaluated


def _apply_deterministic_mappings(service: BackendIdentityService, records: list[ClassifiedRecord]) -> int:
    # Writes are intentionally narrow: only deterministic matches are inserted.
    inserted = 0
    for row in records:
        if row.classification not in {"exact", "high-confidence deterministic"}:
            continue
        if row.match_basis in {None, ""} or not (row.company_id or row.security_id or row.listing_id):
            continue
        if row.classification == "high-confidence deterministic" and row.match_basis == "ticker-only":
            continue
        mapping_id = f"map-{row.source_type}-{row.source_id}"
        service.link_legacy_mapping(
            mapping_id=mapping_id,
            legacy_source=row.source_type,
            legacy_record_id=row.source_id,
            legacy_asset_id=row.source_id,
            legacy_ticker=row.ticker,
            company_id=row.company_id,
            security_id=row.security_id,
            listing_id=row.listing_id,
            resolution_status=row.status,
            provenance=f"backfill_apply:{row.match_basis}",
        )
        inserted += 1
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Wave 2A.1 identity backfill dry-run/apply tool")
    parser.add_argument("--apply", action="store_true", help="Apply deterministic mapping writes")
    parser.add_argument("--out-dir", default="reports", help="Output directory for dry-run reports")
    args = parser.parse_args()

    with Session(engine) as session:
        service = BackendIdentityService(session)
        candidates = _collect_candidates()
        evaluated = _evaluate(service, candidates)
        json_path, md_path = write_backfill_reports(evaluated, Path(args.out_dir))

        inserted = 0
        if args.apply:
            inserted = _apply_deterministic_mappings(service, evaluated)

    print(json.dumps({
        "json_report": str(json_path),
        "summary_report": str(md_path),
        "apply_mode": args.apply,
        "inserted_mappings": inserted,
        "total_candidates": len(evaluated),
    }, indent=2))


if __name__ == "__main__":
    main()
