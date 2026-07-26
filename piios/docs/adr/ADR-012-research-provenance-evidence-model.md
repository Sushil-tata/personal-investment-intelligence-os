# ADR-012: Research Provenance and Evidence Model

## Status
Proposed

## Context
source_documents as string lists lacks provenance structure, claim linkage, and evidence-class distinction.

## Decision
Evidence is first-class and separated into classes:
- external factual evidence
- external opinion/forecast
- internally calculated metric
- human analyst judgement
- model-generated analysis
- agent-generated synthesis

External facts and internal/model interpretations must be separate linked records.

## Alternatives Considered
- Keep string-only source lists.
- Store provenance in free text fields.

## Consequences
- Better auditability and explainability.
- Requires richer ingestion and validation logic.

## Implementation Implications
- Add source registry and evidence entities with claim links.
- Add verification and freshness metadata.

## Migration Implications
- Map existing source_documents into seed source/evidence references with completeness flags.

## Open Questions
- Minimum metadata required for ACTIVE thesis state transitions.
