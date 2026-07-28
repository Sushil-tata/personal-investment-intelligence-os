# Wave 2B M5 Functional Acceptance Report

## Executive Summary
Status: Accepted

Wave 2B Milestone 5 closes human decision capture, diagnostics, and governance review projection for recommendation lifecycle governance.

## Delivered Architecture
- M5.1: human decision invariants in domain model.
- M5.2: persistence parity and PostgreSQL constraints for invariants.
- M5.3: idempotent DecisionCaptureService orchestration.
- M5.4: traceability diagnostics, confidence diagnostics, decision-lineage diagnostics, deterministic governance backlog.
- M5.5: end-to-end functional acceptance, PostgreSQL acceptance, query/API contracts, frontend readiness contract, and closure evidence.

## Key Invariants
- Decisions are immutable records.
- Proposal version and decision identities are distinct.
- MODIFIED and OVERRIDDEN state payload rules are enforced in domain and database.
- Diagnostic status/severity enums are explicit and stable.

## Idempotency
Decision capture idempotency is deterministic per logical request payload.
Repeated identical request returns existing decision and does not create duplicates.
Different valid request creates a new immutable decision.

## M5 Functional Scenarios
In-memory acceptance includes:
- clean acceptance flow from recommendation artifacts to diagnostics and backlog;
- modified decision classification and immutability checks;
- overridden decision classification and lineage visibility;
- deferred decision unresolved-review classification;
- request-research representation as REQUEST_RESEARCH_DECISION;
- traceability failure handling without record mutation;
- replay mismatch handling without decision corruption.

PostgreSQL acceptance includes:
- persistence of proposal/version/snapshot/trace/decision lineage;
- idempotent duplicate capture suppression;
- distinct immutable decision on changed request;
- diagnostic and backlog projection over SQLModel-backed repositories;
- transaction rollback behavior on capture persistence failure;
- DB constraint enforcement against invalid decision payload.

## Query and API Readiness
Transport-independent query contracts are implemented and consumed by minimal FastAPI routes for:
- decision capture;
- proposal/proposal-version detail;
- proposal-version decisions and latest decision;
- traceability, confidence, decision-lineage diagnostics;
- governance backlog.

## Governance Backlog
Backlog is deterministic projection (read-model) and not persisted workflow state.
Current reasons include replay mismatch, lineage gaps, evidence/claim gaps, low or unavailable confidence, and decision review semantics (deferred/research/modified/override).

## Known Limitations
- Distinct persisted DecisionState for REQUEST_RESEARCH is not yet modeled; current representation remains DEFERRED + reason_code REQUEST_RESEARCH.
- Some confidence components remain UNAVAILABLE where no persisted source exists.
- Governance backlog lifecycle state is computed, not durable workflow storage.

## Deferred Improvements
- First-class persisted decision meaning for REQUEST_RESEARCH without reason-code interpretation.
- Optional persisted backlog state machine for triage workflow.
- Wave 3 escalation/reporting workflow integration.

## Frontend Integration Boundary
- Advisory-only output.
- No order execution endpoint.
- No automated trade placement.

## Wave 3 Entry Criteria
- Wave 2B M5 remains green in full-suite and PostgreSQL gates.
- Contract drift safeguards remain green.
- Frontend consumes M5 contracts without schema drift.
- REQUEST_RESEARCH state-model decision logged for Wave 3 backlog planning.

## Final Acceptance Decision
Wave 2B Milestone 5 is functionally accepted and complete.
