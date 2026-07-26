# Wave 2A Assessment: Investment Thesis Registry and Research Provenance

Date: 2026-07-26
Scope: Assessment only (no broad migration yet)

## Files inspected
- `dashboard/pages/10_Investment_Thesis_Registry.py`
- `dashboard/pages/04_Research_Feed.py`
- `dashboard/pages/05_Stock_Scorecard.py`
- `dashboard/pages/19_Top_Recommendations.py`
- `backend/piios_backend/api/routes/theses.py`
- `backend/piios_backend/services/theses.py`
- `backend/piios_backend/repositories/theses.py`
- `backend/piios_backend/schemas/thesis.py`
- `backend/piios_backend/models/entities.py`
- `backend/alembic/versions/0003_theses_and_drift_linkage.py`
- `backend/piios_backend/api/routes/recommendations.py`
- `backend/piios_backend/schemas/recommendation.py`
- `backend/piios_backend/api/routes/research.py`
- `backend/piios_backend/schemas/operations.py`
- `backend/piios_backend/services/live_feeds.py`
- `backend/tests/test_sprint2_thesis_and_drift.py`

## Current thesis data model
Current `InvestmentThesisEntity` stores:
- `thesis_id`, `ticker`, `asset_name`, `theme`, `bucket`
- thesis narrative fields (`thesis`, `bull_case`, `bear_case`, `why_now`, `why_not_now`, `invalidation_trigger`, `valuation_notes`)
- `expected_holding_period`, `source_documents` (JSON text), `confidence_score`, `status`, `created_at`, `updated_at`

Notably absent:
- version model (edits overwrite row)
- structured evidence records
- explicit security reference beyond ticker text
- explicit link to holdings/positions/accounts
- review decision object and schedule

## Current lifecycle
Observed lifecycle statuses come from `RecommendationStatus`:
- `DRAFT`, `RESEARCHED`, `RISK_CHECKED`, `PENDING_REVIEW`, `APPROVED`, `ARCHIVED`

Current behavior:
- thesis create sets `DRAFT`
- thesis status can be patched to any enum value
- no constrained thesis-specific state machine
- no close reasons (sold, achieved, invalidated, etc.)

## Current persistence approach
- SQLModel entity table: `investment_theses`
- recommendation table optionally links `thesis_id`
- repository writes are deterministic and audited at service layer (`THESIS_CREATED`, `THESIS_STATUS_CHANGED`)
- `source_documents` stored as JSON-encoded text list, not normalized relation

## Duplicated logic and coupling
- Thesis and recommendation state semantics are coupled through shared status enum.
- Dashboard thesis page is directly coupled to route shape and string fields.
- Research feed and top recommendations are driven separately from thesis evidence model.
- Scorecard and top recommendations rely on live feed ranking with no durable thesis provenance linkage.

## Missing identifiers and references
- Security identity uses ticker-centric fields; no robust cross-market identity.
- No issuer-level identity, no listing lineage, no active/inactive ticker history.
- No first-class `SecurityReference`, `PortfolioReference`, or `RecommendationReference` models in thesis storage.

## Source and evidence handling gaps
Current `source_documents` is `list[str]` only.
Missing evidence attributes:
- source type
- publication/filing date
- retrieval date
- author/publisher
- URL/document ref + extract
- claim linkage (supports/contradicts)
- credibility/freshness dimensions
- factual vs analyst opinion vs model judgement classification

## Auditability gaps
- Audit log captures event type and blob details, but not version-diff semantics.
- No immutable thesis version chain.
- No explicit reviewer decision object with rationale and decision timestamp model.

## Migration risks
- ID fragility: ticker-only identity can merge unrelated listings.
- Silent semantic drift if thesis lifecycle remains recommendation-derived.
- Loss of historical reasoning if edits mutate single thesis row.
- Weak provenance can contaminate model-generated statements with external fact records.

## Wave 2A conclusion
Wave 2A should implement a deterministic thesis bounded context with:
- explicit versioned thesis model,
- normalized evidence/provenance entities,
- security identity abstraction beyond ticker,
- auditable review decisions,
- compatibility adapters preserving current routes/UI until parity and migration gates pass.
