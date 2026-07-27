# Provenance Exception Policy (Wave 2A.3)

## Purpose
Define how incomplete or ambiguous claims/evidence lineage is surfaced and resolved without silent correction.

## Policy
- Backfill and diagnostics must preserve ambiguity and create owner-review queue entries.
- Missing or non-deterministic source mappings must be marked as INCOMPLETE_PROVENANCE.
- Missing source material must be marked as UNMATCHED_EVIDENCE.
- Version-link failures must be marked as THESIS_VERSION_BINDING_FAILURE.
- Duplicate-candidate text detection must be marked as DUPLICATE_CANDIDATE.

## Non-Goals
- No automatic dedupe.
- No automatic conflict resolution.
- No mutation of historical thesis versions.

## Owner Review Handling
- Every queue item must include item_type, reference_id, reason_code, and details.
- Resolution is explicitly manual and auditable via new provenance records.
