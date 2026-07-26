# ADR-016: ThesisClaim as First-Class Entity

## Status
Proposed

## Context
Evidence and monitoring linkage is weak when claims are buried inside narrative text sections.

## Decision
Introduce ThesisClaim as first-class entity linked to ThesisVersion.

## Alternatives Considered
- Keep claims as structured sections inside thesis version payload.
- Use implicit NLP claim extraction only.

## Consequences
- Queryable supports/contradictions and metric mapping.
- Requires disciplined claim authoring in workflows.

## Implementation Implications
- Claim CRUD via thesis services.
- Evidence and monitoring metrics link to claim IDs.

## Migration Implications
- Existing theses may start with one umbrella claim until manually refined.

## Open Questions
- Minimum claim granularity guidelines for analysts.
