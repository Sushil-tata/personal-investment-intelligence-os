# Wave 2B M1 Domain Contracts

## Scope
This milestone defines SQLModel-independent domain contracts and deterministic in-memory behavior for:
- thesis health snapshots and calculation
- recommendation proposal contracts
- investment decision contracts
- shared enums and value objects
- protocol-first repositories

## Key Decisions
- Proposal and decision are separate aggregates.
- Proposal versions are immutable and append-only.
- One proposal version maps to exactly one input snapshot.
- Structured reasoning is represented with typed, ranked, weighted reason entries.
- Thesis health is computed deterministically from claims, evidence, interpretations, and provenance.

## Deferred to M2+
- SQLModel entities
- Alembic migrations
- PostgreSQL integration
- recommendation engine/scoring implementation
- relationship/opportunity engines
