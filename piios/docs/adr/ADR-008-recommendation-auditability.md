# ADR-008: Recommendation Auditability

## Status
Proposed

## Context
Recommendations must be reviewable, attributable, and reproducible across portfolio and research changes.

## Decision
Each recommendation must include deterministic provenance:
- input snapshot ID and as-of timestamp
- scoring/config versions
- analytics outputs used for the decision
- approval status and reviewer metadata

## Alternatives Considered
- Best-effort logs only: rejected for governance gaps.
- Opaque recommendation artifacts: rejected due to low traceability.

## Consequences
- Stronger governance and investigation capability.
- Additional metadata management requirements.

## Implementation Implications
- Define recommendation metadata contracts and storage schema.
- Enforce explicit version tags in generation pipeline.

## Migration Implications
- Add fields incrementally with backward-compatible defaults.

## Open Questions
- Minimum retention period and immutable audit log approach.
