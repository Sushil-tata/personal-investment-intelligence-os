# ADR-005: PostgreSQL as System of Record

## Status
Proposed

## Context
Current implementation already includes PostgreSQL and Alembic foundations, while some flows still rely on in-memory/mock data stores.

## Decision
PostgreSQL remains the long-term system of record. Wave 1 introduces repository protocols and in-memory implementations only; no runtime persistence cutover yet.

## Alternatives Considered
- Continue mixed ad-hoc stores indefinitely: rejected due to drift risk.
- Immediate persistence rewrite in Wave 1: rejected to avoid breaking changes.

## Consequences
- Clear target persistence architecture.
- Transitional adapter period with dual models.

## Implementation Implications
- Repository interfaces designed for future SQL-backed implementations.
- Snapshot metadata should include UTC timestamps and source lineage.

## Migration Implications
- Delay routing existing production paths to new repositories until equivalence tests pass.

## Open Questions
- Snapshot versioning and retention policy.
