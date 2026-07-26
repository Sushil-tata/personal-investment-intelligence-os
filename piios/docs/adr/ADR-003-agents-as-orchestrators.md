# ADR-003: Agents as Orchestrators

## Status
Proposed

## Context
LangGraph workflows currently perform steps that can mix orchestration with domain decisions. This can make deterministic behavior harder to verify.

## Decision
Agents and LangGraph nodes are orchestration-only. They call bounded-context services and cannot own core financial calculations or policy invariants.

## Alternatives Considered
- Agent-owned business logic: rejected due to testability and audit concerns.
- Remove orchestration entirely: rejected; orchestration still needed for multi-step flows.

## Consequences
- Deterministic services remain independently testable.
- Clearer separation between process control and business rules.

## Implementation Implications
- Node code should delegate to portfolio/analytics/risk services.
- Add service contracts for node interactions.

## Migration Implications
- Existing nodes remain active initially, but internals are progressively delegated.

## Open Questions
- Node-level telemetry schema for service call traces.
