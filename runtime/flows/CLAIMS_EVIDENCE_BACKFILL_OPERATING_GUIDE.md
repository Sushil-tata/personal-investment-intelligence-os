# Claims & Evidence Backfill Operating Guide (Wave 2A.3)

## Command
From backend root:

python scripts/backfill_claims_evidence.py

Apply mode:

python scripts/backfill_claims_evidence.py --apply

Custom report directory:

python scripts/backfill_claims_evidence.py --out-dir reports/wave2a3

## Deterministic Extraction Rules
- Claims are extracted from legacy thesis fields in fixed order:
  - thesis -> core_thesis
  - bull_case -> bull_case
  - bear_case -> bear_case
  - why_now -> why_now
  - why_not_now -> why_not_now
  - invalidation_trigger -> invalidation_trigger
- Only source tokens matching rd<integer> are considered deterministic evidence links.
- Non-matching tokens are retained as owner-review exceptions.

## Idempotency
- Deterministic IDs are used for all created rows.
- Existence checks prevent duplicate inserts.
- Re-running apply mode is safe and should produce zero additional creations once converged.

## Reports
Each run emits:
- JSON report with object counts and owner-review queue items.
- Markdown summary for committee/operations review.
