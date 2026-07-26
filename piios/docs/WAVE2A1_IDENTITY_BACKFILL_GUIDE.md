# Wave 2A.1 Identity Backfill Guide

Date: 2026-07-26
Status: Implemented

## Purpose
Backfill legacy ticker-centric records into Company/Security/Listing references without breaking existing records or routes.

## Tool
- Script: backend/scripts/backfill_identity_map.py

## Inputs scanned
- holdings (legacy holding_id + ticker + currency)
- recommendations (recommendation_id + ticker)
- theses (thesis_id + ticker)

## Classification output
- exact
- high-confidence deterministic
- ambiguous
- unresolved
- conflicting

## Dry-run behavior (default)
- No database writes.
- Emits machine-readable JSON report.
- Emits human-readable Markdown summary.

## Apply behavior
- Requires explicit --apply flag.
- Writes only deterministic matches (exact/high-confidence deterministic).
- Ambiguous/conflicting/unresolved are never auto-mapped.
- Mapping provenance is persisted.
- Legacy source records are not overwritten.

## Usage
From backend folder:

./.venv/bin/python scripts/backfill_identity_map.py --out-dir reports

Optional apply:

./.venv/bin/python scripts/backfill_identity_map.py --out-dir reports --apply

## Safeguards
- Ticker-only ambiguous matches are not auto-resolved.
- Conflicting identifier outcomes remain reviewable.
- Mapping writes are append-only style records in identity_legacy_mappings.

## Follow-up owner workflow
- Review unresolved and conflict queues from /api/v1/identity/resolution-issues.
- Approve or reject suggested mappings with reviewer metadata.
