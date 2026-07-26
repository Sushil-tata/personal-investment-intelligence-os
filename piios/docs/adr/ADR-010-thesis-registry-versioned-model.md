# ADR-010: Thesis Registry Versioned Model

## Status
Proposed

## Context
Current thesis records are mutable single rows. Editing can overwrite prior reasoning and provenance context.

## Decision
Adopt immutable thesis versions:
- InvestmentThesis is the root identity.
- ThesisVersion is append-only and immutable after creation.
- Material edits require new version.
- Recommendations and decisions reference thesis_version_id used at decision time.

## Alternatives Considered
- Mutable single row with updated_at only.
- Non-structured snapshots in audit logs.

## Consequences
- Strong historical traceability.
- Need version projection logic for existing APIs.

## Implementation Implications
- Add thesis root + version tables.
- Implement projection adapter returning legacy-compatible thesis views.

## Migration Implications
- Existing thesis rows become root + version v1.
- Existing routes continue with latest-version projection during transition.

## Open Questions
- Need explicit material-change policy checklist per field group.
