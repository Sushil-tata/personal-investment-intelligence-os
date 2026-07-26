# ADR-006: Provider Abstraction for Market Data

## Status
Proposed

## Context
The codebase supports multiple market data providers and may require fallback behavior for missing/stale data.

## Decision
Define provider abstraction interfaces and normalization contracts. Portfolio and analytics logic consume normalized provider-agnostic data structures.

## Alternatives Considered
- Direct provider calls across modules: rejected due to coupling.
- Single provider lock-in: rejected due to resilience concerns.

## Consequences
- Easier provider substitution and testing.
- Added mapping layer complexity.

## Implementation Implications
- Keep adapter modules at ingestion/infrastructure boundaries.
- Standardize required fields and quality flags.

## Migration Implications
- Existing adapters continue to work while normalized interfaces are introduced.

## Open Questions
- Preferred provider priority and tie-break rules by instrument/region.
