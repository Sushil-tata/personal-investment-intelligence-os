# ADR-014: Recommendation Linkage, Investment Decision Separation, and Audit

## Status
Proposed

## Context
Recommendations currently reference thesis ID but are not version-pinned, and decision records are not separated as first-class durable aggregates.

## Decision
- Recommendation and InvestmentDecision are separate aggregates.
- Recommendation references thesis_version_id and subject reference.
- InvestmentDecision references recommendation_id and portfolio_snapshot_id.
- Rejected/deferred records are retained append-only.
- Audit events are append-only immutable records.

## Alternatives Considered
- Merge recommendation and decision entities.
- Store decision outcomes by mutating recommendation status only.

## Consequences
- Strong governance traceability.
- Additional workflow orchestration and schema complexity.

## Implementation Implications
- Add decision and execution entities.
- Extend audit taxonomy for recommendation and decision lifecycle events.

## Migration Implications
- Existing recommendations remain valid through compatibility projections.
- Decision domain introduced without breaking legacy recommendation routes.

## Open Questions
- Required minimum fields for decision rationale standardization.
