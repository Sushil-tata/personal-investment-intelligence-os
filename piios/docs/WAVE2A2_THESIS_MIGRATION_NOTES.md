# Wave 2A.2 Thesis Migration Notes

Date: 2026-07-26

## Migration Revision

- Revision: `0006_thesis_versioned_domain`
- Down revision: `0005_identity_master_tables`

## Schema Changes

Additive tables:

1. `thesis_roots`
- thesis_id (unique)
- ticker
- lifecycle_status
- current_version_number
- created_at, updated_at
- closed_reason, closed_at

2. `thesis_versions`
- version_id (unique)
- thesis_id (FK to thesis_roots.thesis_id)
- version_number (unique per thesis)
- thesis content fields (mirroring legacy contract content)
- status
- created_at

## Backfill Logic

For each row in `investment_theses`:

- Insert one root row in `thesis_roots`.
- Insert one version row in `thesis_versions` with `version_number=1` and `version_id={thesis_id}:v1`.
- If legacy status is `ARCHIVED`, mark root closure metadata.

## Safety Properties

- Legacy table remains untouched and queryable.
- Migration is additive and reversible (drops only new tables on downgrade).
- Version history starts with deterministic v1 from legacy source row.

## Validation

- `backend/tests/test_wave2a2_thesis_migration.py` verifies:
  - upgrade through `0006`
  - legacy row backfill into new tables
  - downgrade back to `0005`
  - removal of new tables on downgrade
