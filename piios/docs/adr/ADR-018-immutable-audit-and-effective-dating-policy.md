# ADR-018: Immutable Audit and Effective Dating Policy

## Status
Proposed

## Context
Cross-domain traceability requires immutable event records and temporal identity consistency.

## Decision
- Audit events are append-only immutable records.
- Versioned thesis, decision, and execution records are append-only.
- Identity entities use effective dating for temporal correctness.
- Hard deletes prohibited for core decision-critical entities.

## Alternatives Considered
- Mutable audit blobs.
- No effective dating in identity entities.

## Consequences
- Strong forensic capability.
- Increased storage and retention planning needs.

## Implementation Implications
- Standard audit schema with actor type and provenance fields.
- Effective-date validation in identity services.

## Migration Implications
- Backfill scripts populate initial effective windows where unknown.

## Open Questions
- Archival retention horizon and cold-storage strategy.
