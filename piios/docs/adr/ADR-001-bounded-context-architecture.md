# ADR-001: Bounded Context Architecture

## Status
Proposed

## Context
The codebase contains portfolio, analytics, recommendations, research ingestion, risk controls, and UI concerns across backend and dashboard layers. This causes implicit coupling, duplicate calculations, and fragile changes.

## Decision
Adopt bounded contexts as the primary architecture:
- Portfolio
- Research
- Market Data
- Analytics
- Recommendations
- Risk
- Governance

Business logic will live inside context modules. Agents and workflows orchestrate context services but do not own core business logic.

## Alternatives Considered
- Layer-only architecture (API/service/repository): rejected due to weak business boundaries.
- Agent-first architecture: rejected because orchestration and reasoning can hide deterministic domain invariants.
- New repository rewrite: rejected to preserve existing investment logic and history.

## Consequences
- Clear ownership boundaries.
- Easier testability and refactoring.
- Temporary duplication during migration if adapters are not used carefully.

## Implementation Implications
- Introduce context modules under piios.
- Move deterministic logic from routes/nodes/UI into context services.
- Keep old entrypoints unchanged during transition.

## Migration Implications
- Incremental extraction per context.
- Compatibility adapters required until cutover.

## Open Questions
- Context ownership model by team/persona.
- Required API versioning strategy during mixed-mode operation.
