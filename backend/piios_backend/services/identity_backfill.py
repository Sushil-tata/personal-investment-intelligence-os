from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class ClassifiedRecord:
    source_type: str
    source_id: str
    ticker: str | None
    currency: str | None
    classification: str
    status: str
    candidate_count: int
    match_basis: str | None
    company_id: str | None
    security_id: str | None
    listing_id: str | None
    warnings: list[str]


def classify_resolution(status: str, candidate_count: int, match_basis: str | None) -> str:
    if status == "CONFLICTING":
        return "conflicting"
    if status == "AMBIGUOUS":
        return "ambiguous"
    if status == "UNRESOLVED":
        return "unresolved"
    if status in {"HISTORICAL_MATCH", "INACTIVE_MATCH"}:
        return "high-confidence deterministic"
    if status == "RESOLVED" and candidate_count == 1 and match_basis and match_basis.startswith("internal_"):
        return "exact"
    if status == "RESOLVED" and candidate_count == 1:
        return "high-confidence deterministic"
    if status == "RESOLVED" and candidate_count > 1:
        return "ambiguous"
    return "unresolved"


def write_backfill_reports(records: list[ClassifiedRecord], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = out_dir / f"identity_backfill_dry_run_{ts}.json"
    md_path = out_dir / f"identity_backfill_dry_run_{ts}.md"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "records": [
            {
                "source_type": row.source_type,
                "source_id": row.source_id,
                "ticker": row.ticker,
                "currency": row.currency,
                "classification": row.classification,
                "status": row.status,
                "candidate_count": row.candidate_count,
                "match_basis": row.match_basis,
                "company_id": row.company_id,
                "security_id": row.security_id,
                "listing_id": row.listing_id,
                "warnings": row.warnings,
            }
            for row in records
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    summary = {
        "exact": sum(1 for row in records if row.classification == "exact"),
        "high-confidence deterministic": sum(1 for row in records if row.classification == "high-confidence deterministic"),
        "ambiguous": sum(1 for row in records if row.classification == "ambiguous"),
        "unresolved": sum(1 for row in records if row.classification == "unresolved"),
        "conflicting": sum(1 for row in records if row.classification == "conflicting"),
    }

    lines = [
        "# Wave 2A.1 Identity Backfill Dry-Run Summary",
        "",
        f"Generated at (UTC): {payload['generated_at']}",
        "",
        "## Classification counts",
        f"- exact: {summary['exact']}",
        f"- high-confidence deterministic: {summary['high-confidence deterministic']}",
        f"- ambiguous: {summary['ambiguous']}",
        f"- unresolved: {summary['unresolved']}",
        f"- conflicting: {summary['conflicting']}",
        "",
        "## Notes",
        "- Dry-run mode makes no database changes.",
        "- Ambiguous and conflicting cases require owner review.",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path
