# ADR-009: Human Approval and Advisory-Only Controls

## Status
Proposed

## Context
The product must remain advisory-only and enforce human approval before accepted recommendation states.

## Decision
Keep hard controls:
- no broker integration
- no auto-trading
- no order placement
- no margin/leverage execution paths
- no broker credential storage
- recommendation acceptance requires explicit human approval

## Alternatives Considered
- Optional automated execution: rejected by policy boundary.
- Silent auto-approval heuristics: rejected due to governance risk.

## Consequences
- Preserves policy and risk posture.
- Requires explicit approval workflow UX and audit fields.

## Implementation Implications
- Guardrails validated in APIs and workflow transitions.
- Approval state transitions must be explicit and logged.

## Migration Implications
- Maintain control checks during all refactors.
- Parity tests must include advisory-only and approval constraints.

## Open Questions
- Required SLA for human review and escalation paths.
