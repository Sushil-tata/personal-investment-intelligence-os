# ADR-011: Company, Security, and Listing Identity Separation

## Status
Proposed

## Context
Ticker-centric identity cannot safely link holdings, theses, evidence, and recommendations across exchanges, ADRs, and ticker changes.

## Decision
Implement a unified Identity bounded context with three distinct entity layers:
- Company (issuer)
- Security (issued financial instrument class)
- ListingInstrument (exchange tradable representation)

Also include identifiers, relationships, and effective-dated ticker history.

## Alternatives Considered
- Ticker-only identity.
- Company and security collapsed in one table.
- Separate bounded contexts for company/security/listing in Wave 2A.

## Consequences
- Resolves cross-listing ambiguity.
- Adds up-front schema and backfill effort.

## Implementation Implications
- Create identity registries and relationship tables.
- Use security and listing references in thesis/recommendation/decision domains.

## Migration Implications
- Backfill from existing asset and instrument tables.
- Track unresolved identity matches in ambiguity reports.

## Open Questions
- Canonical external identifier precedence when providers conflict.

## Wave 2A.1 Amendment: Deterministic Resolution Precedence
- Internal PIIOS IDs are authoritative within the platform.
- Verified authoritative identifiers (for example ISIN) outrank provider-local identifiers.
- Provider identifiers are only evaluated within provider namespace.
- Exchange+ticker resolution is valid only within the effective date window.
- Ticker-only matching is permitted only when a unique candidate exists; ambiguous ticker-only input never auto-resolves.
- Conflicting authoritative identifiers produce a conflict outcome requiring owner review.
- Conflicts do not overwrite existing mappings or identity records automatically.
