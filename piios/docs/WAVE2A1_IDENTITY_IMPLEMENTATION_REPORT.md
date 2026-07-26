# Wave 2A.1 Identity Implementation Report

Date: 2026-07-26
Status: Completed

## Scope delivered
- Company Master
- Security Master
- Listing Instrument Master
- External identifiers
- Ticker history
- Security relationships
- Deterministic identity resolution service
- Repository protocols and persistence implementations
- Compatibility shadow adapters
- Backfill dry-run/apply tooling
- Tests and documentation

## Domain design decisions
- Company, Security, and ListingInstrument are separate entities within one Identity bounded context.
- Sector and industry are treated as mutable metadata rather than immutable identity keys.
- Security issuer is optional to support funds/sovereign-style issuance.
- Effective dating is required for identity entities and supporting relationships.
- Hard delete path is explicitly prohibited in application services.

## Bounded-context files
- piios/identity/domain/enums.py
- piios/identity/domain/value_objects.py
- piios/identity/domain/entities.py
- piios/identity/domain/policies.py
- piios/identity/domain/exceptions.py
- piios/identity/application/commands.py
- piios/identity/application/queries.py
- piios/identity/application/dto.py
- piios/identity/application/resolution.py
- piios/identity/application/services.py
- piios/identity/infrastructure/repository_protocols.py
- piios/identity/infrastructure/in_memory_repositories.py
- piios/identity/infrastructure/sqlmodel_repositories.py
- piios/identity/infrastructure/legacy_adapter.py
- piios/identity/infrastructure/importers.py

## Backend integration
- Added identity SQLModel entities in backend/piios_backend/models/entities.py
- Added identity API schemas in backend/piios_backend/schemas/identity.py
- Added backend service adapter in backend/piios_backend/services/identity.py
- Added non-invasive diagnostics in backend/piios_backend/services/identity_shadow.py
- Added compatibility enrichment helpers in backend/piios_backend/services/identity_compatibility.py
- Added API routes in backend/piios_backend/api/routes/identity.py
- Registered identity router in backend/piios_backend/main.py

## Database migration
- Added backend/alembic/versions/0005_identity_master_tables.py
- New additive tables:
  - identity_companies
  - identity_securities
  - identity_listing_instruments
  - identity_security_identifiers
  - identity_ticker_history
  - identity_security_relationships
  - identity_legacy_mappings
  - identity_resolution_issues
- Added indexes for identifiers, exchange+ticker lookups, status, and effective-date windows.
- No legacy table or column dropped.

## Validation summary
- Identity domain test suite: 21 passed
- Backend identity/backfill suite: 5 passed
- Full backend suite: 30 passed
- Wave 1 portfolio suite: 24 passed
- Migration cycle on clean SQLite DB: upgrade head, downgrade base, upgrade head passed

## Known limitations
- Backfill tool currently scans in-memory seeded records and local runtime data; production source adapters remain for subsequent waves.
- Owner-review UI is not implemented yet; issue queue and API contracts are in place.
