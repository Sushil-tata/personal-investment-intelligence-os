from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlmodel import Session

from piios_backend.core.database import engine
from piios_backend.services.claims_evidence_backfill import run_claims_evidence_backfill, write_backfill_reports


def main() -> None:
    parser = argparse.ArgumentParser(description="Wave 2A.3 claims/evidence backfill dry-run/apply tool")
    parser.add_argument("--apply", action="store_true", help="Apply deterministic backfill writes")
    parser.add_argument("--out-dir", default="reports", help="Output directory for backfill reports")
    args = parser.parse_args()

    dry_run = not args.apply
    with Session(engine) as session:
        result = run_claims_evidence_backfill(session, dry_run=dry_run)
        json_path, md_path = write_backfill_reports(result, Path(args.out_dir))

    print(
        json.dumps(
            {
                "dry_run": result.dry_run,
                "json_report": str(json_path),
                "summary_report": str(md_path),
                "created_claims": result.created_claims,
                "created_sources": result.created_sources,
                "created_evidence_items": result.created_evidence_items,
                "created_interpretations": result.created_interpretations,
                "created_provenance": result.created_provenance,
                "owner_review_items": len(result.owner_review_items),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
