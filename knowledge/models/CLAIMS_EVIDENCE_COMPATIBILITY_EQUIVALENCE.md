# Claims & Evidence Compatibility and Equivalence (Wave 2A.3)

## Scope
Internal compatibility adapters only. No public route shape changes.

## Legacy Thesis Equivalence
Legacy thesis fields remain authoritative for route contracts while overlap projections expose:
- claims_overlap: claim-level link summary
- evidence_overlap: evidence-level source summary

The adapter explicitly preserves:
- legacy_rationale (thesis text)
- legacy_source_documents

## Legacy Research Equivalence
Evidence rows can be projected into ResearchDocumentResponse-compatible objects with:
- title
- source
- timestamp
- url

## Shadow Diagnostics
Diagnostics are read-only and include:
- matched_records
- missing_claims
- unmatched_evidence
- conflicting_evidence
- incomplete_provenance
- stale_evidence
- duplicate_candidates
- thesis_version_binding_failures

## Risk Posture
Ambiguity is surfaced, not hidden. No automatic reconciliation.

## Milestone 3 Validation
Final validation executed on 2026-07-27.

- PostgreSQL integration suite: `backend/tests/test_wave2a3_postgres_integration.py` -> 3 passed.
- Route-contract suite: `backend/tests/test_routes_contract.py` -> 2 passed.
- Focused Wave 2A.3 gate:
	- `piios/thesis/tests/test_claims_domain.py`
	- `piios/thesis/tests/test_claims_services.py`
	- `piios/tests/test_wave2a3_claims_persistence.py`
	- `backend/tests/test_wave2a3_claims_migration.py`
	- `piios/tests/test_wave2a3_compatibility_shadow_backfill.py`
	- `backend/tests/test_routes_contract.py`
	- `backend/tests/test_wave2a3_postgres_integration.py`
	- Result: 18 passed.

- File-side-effect guard: `git diff -- backend/data/mock/graph_runs_fallback.json` returned no diff after gate execution.
