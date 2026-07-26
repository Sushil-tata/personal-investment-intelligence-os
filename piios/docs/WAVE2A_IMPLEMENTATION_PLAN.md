# Wave 2A Implementation Plan (Final Sequence)

Date: 2026-07-26

## 2A.1 Company and Security Identity

Status:
- Completed on 2026-07-26.
- Additive migration 0005 implemented and validated with upgrade/downgrade/re-upgrade cycle on clean SQLite test DB.
- Identity bounded context, deterministic resolution service, SQLModel repositories, compatibility shadow diagnostics, and backfill dry-run tooling delivered.
- Existing backend and Wave 1 portfolio suites passed after integration.

Scope:
- Introduce identity model for company, security, listing instrument, identifiers, relationships, ticker history.

Files to create:
- piios/identity/domain/entities.py
- piios/identity/domain/value_objects.py
- piios/identity/domain/enums.py
- piios/identity/application/services.py
- piios/identity/application/commands.py
- piios/identity/application/queries.py
- piios/identity/infrastructure/repository_protocol.py

Files to change:
- backend/piios_backend/models/entities.py
- backend/alembic/versions/<new_identity_migration>.py

Schema changes:
- create company, security, listing instrument, identifier, relationship, ticker history tables

Migrations:
- backfill from asset + instrument_master
- ambiguity table for unresolved mappings

Tests:
- identity validation
- cross-listing and ADR relationship tests

Compatibility strategy:
- keep ticker fields in legacy entities for display
- add mapping adapters without changing existing routes

Entry criteria:
- approved architecture and ADRs complete

Exit criteria:
- identity tables and services stable; backfill dry-run successful

Risks:
- ambiguous ticker mapping

Rollback:
- migration down scripts + keep legacy identity untouched

## 2A.2 Thesis Domain and Versioning

Scope:
- thesis root + immutable thesis versions + lifecycle state machine

Files to create:
- piios/thesis/domain/entities.py
- piios/thesis/domain/value_objects.py
- piios/thesis/domain/enums.py
- piios/thesis/application/services.py
- piios/thesis/application/commands.py
- piios/thesis/application/queries.py
- piios/thesis/application/dto.py
- piios/thesis/infrastructure/repository_protocol.py

Files to change:
- backend/piios_backend/services/theses.py
- backend/piios_backend/repositories/theses.py
- backend/alembic/versions/<new_thesis_versioning_migration>.py

Schema changes:
- thesis root table
- thesis version table
- thesis lifecycle and closure reason fields

Migrations:
- legacy thesis rows become thesis root + v1 version

Tests:
- version immutability
- state transition guards

Compatibility strategy:
- current /theses endpoints project latest version

Entry criteria:
- identity IDs available

Exit criteria:
- append-only thesis versioning active behind adapters

Risks:
- unexpected legacy status mappings

Rollback:
- stop adapter switch, keep legacy repository path

## 2A.3 Thesis Claims and Monitoring Metrics

Scope:
- add first-class thesis claims and monitoring metric model

Files to create:
- piios/thesis/domain/claims.py
- piios/thesis/domain/metrics.py
- piios/thesis/application/claim_services.py
- piios/thesis/application/metric_services.py

Files to change:
- backend/alembic/versions/<new_claim_metric_migration>.py

Schema changes:
- thesis_claims
- monitoring_metrics
- metric_observations

Migrations:
- create empty claims for legacy theses only if minimally needed; do not fabricate content

Tests:
- claim-evidence linkage integrity
- metric threshold evaluation scaffolding

Compatibility strategy:
- claim and metrics endpoints internal first; legacy UI unaffected

Entry criteria:
- thesis versioning in place

Exit criteria:
- claims and metrics persisted with audit coverage

Risks:
- over-modeling qualitative claims

Rollback:
- keep claim and metric features feature-flagged off in routes

## 2A.4 Research Evidence and Provenance

Scope:
- first-class evidence and source provenance model

Files to create:
- piios/research/domain/entities.py
- piios/research/domain/enums.py
- piios/research/application/services.py
- piios/research/infrastructure/repository_protocol.py

Files to change:
- backend/piios_backend/api/routes/research.py
- backend/piios_backend/services/live_feeds.py
- backend/alembic/versions/<new_evidence_migration>.py

Schema changes:
- research_sources
- evidence
- evidence_links (claim/thesis)

Migrations:
- source_documents strings mapped to seed source references with completeness flags

Tests:
- evidence class validation
- external fact vs model interpretation separation

Compatibility strategy:
- maintain existing research feed response shape while enriching internals

Entry criteria:
- thesis claim model ready

Exit criteria:
- provenance-complete evidence ingestion path available

Risks:
- low-quality source metadata in legacy rows

Rollback:
- continue legacy source_documents usage while new evidence ingestion is disabled

## 2A.5 Recommendation Domain

Scope:
- formal recommendation aggregate linked to thesis_version and subject reference

Files to create:
- piios/recommendation/domain/entities.py
- piios/recommendation/domain/enums.py
- piios/recommendation/application/services.py
- piios/recommendation/infrastructure/repository_protocol.py

Files to change:
- backend/piios_backend/api/routes/recommendations.py
- backend/piios_backend/schemas/recommendation.py
- backend/alembic/versions/<new_recommendation_domain_migration>.py

Schema changes:
- recommendation subject references
- recommendation lifecycle fields

Migrations:
- map existing recommendation rows into new lifecycle

Tests:
- recommendation state transitions
- thesis version pinning

Compatibility strategy:
- keep current recommendation API contract with projection adapters

Entry criteria:
- thesis versions available

Exit criteria:
- recommendations persist with version-aware linkage

Risks:
- legacy status mapping ambiguity

Rollback:
- restore legacy recommendation status projection

## 2A.6 Investment Decision Domain

Scope:
- separate decision aggregate and execution tracking

Files to create:
- piios/investment_decision/domain/entities.py
- piios/investment_decision/domain/enums.py
- piios/investment_decision/application/services.py
- piios/investment_decision/infrastructure/repository_protocol.py

Files to change:
- backend/alembic/versions/<new_decision_domain_migration>.py
- backend/piios_backend/api/routes/<new_decision_routes>.py

Schema changes:
- investment_decisions
- proposed_trades
- executions

Migrations:
- none required for legacy rows initially; new domain starts append-only

Tests:
- decision status transitions
- rejection and defer retention
- execution linkage

Compatibility strategy:
- no impact on existing endpoints until explicit feature exposure

Entry criteria:
- recommendation domain stable

Exit criteria:
- human decision records fully persisted and auditable

Risks:
- approval workflow complexity

Rollback:
- disable decision routes, keep tables intact

## 2A.7 Compatibility Adapters

Scope:
- route and schema compatibility with existing thesis and recommendation UI/pages

Files to create:
- piios/thesis/infrastructure/legacy_adapter.py
- piios/recommendation/infrastructure/legacy_adapter.py

Files to change:
- backend/piios_backend/api/routes/theses.py
- dashboard/pages/10_Investment_Thesis_Registry.py (optional shape-safe enhancements only)

Schema changes:
- none

Migrations:
- none

Tests:
- API contract parity tests
- UI smoke tests for unchanged behaviors

Compatibility strategy:
- old shapes in, old shapes out

Entry criteria:
- core new domains available

Exit criteria:
- legacy callers function without behavioral change

Risks:
- hidden UI assumptions

Rollback:
- route handler toggle to legacy repository/service path

## 2A.8 Backfill and Migration Utilities

Scope:
- scripted backfill for identity and thesis version references

Files to create:
- backend/scripts/backfill_identity_map.py
- backend/scripts/backfill_thesis_versions.py
- backend/scripts/backfill_recommendation_thesis_links.py

Files to change:
- backend/tests/<new_backfill_tests>.py

Schema changes:
- none

Migrations:
- utility-driven data migration with audit trail

Tests:
- dry-run idempotency
- ambiguity report generation

Compatibility strategy:
- run in shadow mode first

Entry criteria:
- schemas and repositories complete

Exit criteria:
- backfill report accepted

Risks:
- unresolved identity matches

Rollback:
- no destructive writes in dry-run; staged commits with rollback SQL

## 2A.9 Dual-Run Verification

Scope:
- dev/test-only legacy-vs-new parity checks for thesis/recommendation read paths

Files to create:
- backend/piios_backend/services/thesis_dual_run.py
- piios/tests/test_wave2a_thesis_dual_run.py

Files to change:
- backend/piios_backend/core/config.py
- backend/piios_backend/api/routes/theses.py

Schema changes:
- none

Migrations:
- none

Tests:
- parity, tolerance, mismatch classification

Compatibility strategy:
- non-invasive side effect only

Entry criteria:
- compatibility adapters complete

Exit criteria:
- parity gate accepted

Risks:
- noisy mismatches from legacy data quality issues

Rollback:
- disable dual-run flag; retain reports

## 2A.10 Controlled Route and UI Cutover

Scope:
- controlled promotion from compatibility adapters to new application services

Files to change:
- backend/piios_backend/api/routes/theses.py
- backend/piios_backend/services/theses.py
- dashboard/pages/10_Investment_Thesis_Registry.py (only once parity approved)

Schema changes:
- none

Migrations:
- none

Tests:
- end-to-end acceptance and contract regression

Compatibility strategy:
- feature-flagged rollout by route segment

Entry criteria:
- parity and governance sign-off

Exit criteria:
- stable production behavior on new domain services

Risks:
- latent edge cases from old UI assumptions

Rollback:
- immediate flag rollback to compatibility path
