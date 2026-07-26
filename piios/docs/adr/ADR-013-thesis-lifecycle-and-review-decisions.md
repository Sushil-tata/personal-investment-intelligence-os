# ADR-013: Thesis Lifecycle and Review Outcomes

## Status
Proposed

## Context
Current thesis uses recommendation-oriented statuses. Review outcomes are not explicitly modeled.

## Decision
Use compact thesis lifecycle states:
- DRAFT
- ACTIVE
- UNDER_REVIEW
- INVALIDATED
- CLOSED

Model REAFFIRMED and WEAKENED as ThesisReview outcomes (events), not durable thesis states.

## Alternatives Considered
- Long thesis state list including REAFFIRMED/WEAKENED as durable states.
- Reusing recommendation status enum.

## Consequences
- Cleaner state machine.
- Requires explicit review event modeling.

## Implementation Implications
- Add ThesisReview entity with outcome and rationale.
- Enforce transition guards in thesis services.

## Migration Implications
- Map legacy statuses to thesis state + review outcome where needed.

## Open Questions
- Review SLA policy and escalation ownership.
