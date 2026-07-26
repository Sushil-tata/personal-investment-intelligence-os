# ADR-015: Thesis Anchoring and Overlay Scoping

## Status
Proposed

## Context
A single company can be held through multiple listings and instrument types. Duplicating full theses per listing causes drift.

## Decision
- Primary thesis anchors to Company.
- Security/listing overlays are optional scoped claim layers.
- Overlays capture listing, currency, liquidity, tax, custody, or instrument-term deltas.

## Alternatives Considered
- Thesis anchored only at ticker/listing level.
- Separate full thesis per listing.

## Consequences
- Preserves core investment view continuity across listing changes.
- Requires overlay reference and merge rules in read projections.

## Implementation Implications
- Add scope references on thesis versions or claims.
- Define projection rules for company-only vs company+overlay views.

## Migration Implications
- Legacy thesis rows become company-anchored unless evidence indicates listing-specific scope.

## Open Questions
- Overlay conflict precedence when multiple overlays apply.
