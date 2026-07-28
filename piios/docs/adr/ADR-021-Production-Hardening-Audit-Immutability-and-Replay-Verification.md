# ADR-021: Production Hardening - Audit Immutability and Replay Verification

## Status
Accepted

## Date
2026-07-28

## Context
Wave 2B Milestone 4 established deterministic traceability and reconstruction. Reconstruction proves that persisted records can be assembled into an authoritative historical view.

Regulatory assurance requires one additional guarantee:
- reconstruction: "what was stored"
- replay verification: "if the frozen input is recomputed now, does it still match persisted recommendation output"

A second hardening need was identified in persistence constraints. Trace rows were linked with delete cascades from parent recommendation records, creating a risk that historical audit evidence could disappear through parent deletion.

## Decision
1. Harden trace foreign keys to prevent parent-delete cascade removal of audit traces.
- `decision_recommendation_traces.proposal_id` -> `RESTRICT`
- `decision_recommendation_traces.proposal_version_id` -> `RESTRICT`
- `decision_recommendation_traces.input_snapshot_id` -> `RESTRICT`

2. Add a read-only replay verification service.
- Load persisted immutable snapshot payload
- Reconstruct replay input
- Recompute with the decision engine in evaluate-only mode
- Compare recomputed output against persisted artifacts
- Return explicit PASS/FAIL plus detailed field-level differences

Compared fields include:
- action
- overall score
- component scores
- explanation
- trace hash
- deterministic input hash

## Rationale
- Immutability: regulatory audit records must not disappear as side effects of parent deletions.
- Referential integrity: `RESTRICT` blocks unsafe deletes while preserving valid relationships.
- Replay assurance: reconstruction alone cannot detect drift between persisted output and current deterministic computation.
- Safety: replay runs with an in-memory evaluate-only engine and does not mutate production data.

## Alternatives Considered
1. Keep CASCADE and enforce process controls only.
- Rejected: does not provide database-level protection.

2. Soft-delete parent records.
- Rejected: broader domain redesign outside this hardening scope.

3. Separate archive tables with copy-on-write.
- Rejected: higher migration and operational complexity for this milestone.

## Consequences
- Parent recommendation records with existing traces cannot be deleted until dependent trace history is handled explicitly.
- Historical recommendation lineage remains reconstructable.
- Replay verification supports internal audit, model validation, and regulator-driven evidence requests without changing scoring logic.
