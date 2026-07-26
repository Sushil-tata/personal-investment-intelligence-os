# ADR-007: Legacy Compatibility Strategy

## Status
Proposed

## Context
Wave 1 requires zero breaking changes while extracting portfolio logic into a new bounded context. Existing dashboard and backend imports must continue to function.

## Decision
Adopt adapter/facade compatibility strategy:
- Keep existing module locations and public import paths unchanged.
- Extract reusable logic into piios portfolio modules.
- Add legacy adapters that transform legacy objects into new domain models.
- Add reverse adapters where legacy-compatible output shapes are required.
- Mark temporary compatibility code clearly.

## Alternatives Considered
- Immediate module relocation with import rewrites: rejected due to high break risk.
- Duplicate old/new logic without adapters: rejected due to drift risk.

## Consequences
- Safe migration with verifiable equivalence.
- Temporary maintenance overhead for adapters and parity tests.

## Implementation Implications
- Add explicit compatibility entrypoints and contract tests.
- Maintain deterministic golden fixtures for legacy-vs-new comparisons.

## Migration Implications
- No production flow redirect until parity gates pass.
- Track and retire compatibility layer in staged cutover plan.

## Open Questions
- Objective parity threshold for floating-point legacy outputs when moved to Decimal.
- Sunset criteria and timing for legacy module retirement.
