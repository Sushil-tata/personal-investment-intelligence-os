# ADR-004: Deterministic Analytics vs LLM Reasoning

## Status
Proposed

## Context
Portfolio value, exposures, concentration, and trade-impact metrics require exact reproducibility and auditability.

## Decision
All financial analytics remain deterministic code paths. LLMs may assist with narrative explanations only and must not compute or override numeric analytics.

## Alternatives Considered
- Hybrid LLM-calculated metrics: rejected due to nondeterminism.
- Fully LLM-generated recommendations with hidden calculations: rejected for governance risk.

## Consequences
- Reliable numeric outputs and reproducible tests.
- Need explicit explainability derivations from deterministic outputs.

## Implementation Implications
- Implement analytics in Python modules using Decimal.
- Include precise rounding policies and documented assumptions.

## Migration Implications
- Replace ad-hoc calculations in UI/workflow layers with shared analytics services.

## Open Questions
- Standardized explanation templates linked to metric provenance.
