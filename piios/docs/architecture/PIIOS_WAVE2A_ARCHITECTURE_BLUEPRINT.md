# PIIOS Wave 2A Final Architecture Blueprint

Date: 2026-07-26
Status: Approved blueprint for implementation planning

## Final boundary decisions

### Company vs Security vs Listing
- Separation is required now.
- Company (issuer) is distinct from Security.
- Security is distinct from Listing/Instrument.
- Two bounded components are sufficient for Wave 2A:
  - Identity Context: Company, Security, Listing/Instrument as three entity types.
  - Thesis/Research/Recommendation/Decision contexts reference identity IDs.
- Keep one cohesive Identity bounded context to avoid cross-context transaction complexity in early migration.

### Should Security Master become Company Master, Security Master, Instrument Master?
- Use one Identity context with three core registries:
  - Company Master
  - Security Master
  - Listing Instrument Master
- Do not collapse to one table.
- Do not split into unrelated bounded contexts yet.

### Thesis anchoring
- Primary thesis anchored to Company by default.
- Security or listing overlays allowed only when instrument or listing terms materially affect thesis outcomes.
- Overlay model:
  - Company thesis root remains canonical.
  - Security/listing overlay claims attach to thesis version with scoped references.

## Thesis, claims, and monitoring design

### Thesis ownership and structure
- InvestmentThesis root:
  - company-anchored default
  - optional scoped links to security/listing/portfolio
- ThesisVersion:
  - append-only immutable versions
  - prior recommendations and decisions reference exact thesis_version_id
- ThesisClaim:
  - first-class entity (required)
  - improves traceability for evidence, metrics, and review outcomes

### Monitoring metrics
- MonitoringMetric and MetricObservation are first-class persisted entities (required).
- Evaluation outcomes are event records first; thesis lifecycle state transitions are controlled by review service.

### Thesis review modeling
- Thesis lifecycle state should remain compact.
- REAFFIRMED and WEAKENED should be review outcomes/events, not durable thesis states.
- Final thesis lifecycle states:
  - DRAFT
  - ACTIVE
  - UNDER_REVIEW
  - INVALIDATED
  - CLOSED
- Review outcomes recorded in ThesisReview:
  - REAFFIRMED
  - WEAKENED
  - POTENTIALLY_BROKEN
  - INVALIDATED_REVIEW

## Recommendation and Investment Decision separation

### Recommendation domain
- Recommendation is analytical proposal.
- It may be authored by human or model, but remains advisory artifact.
- Proposed statuses:
  - DRAFT
  - READY_FOR_REVIEW
  - PENDING_DECISION
  - ACCEPTED
  - MODIFIED
  - REJECTED
  - DEFERRED
  - EXPIRED
  - SUPERSEDED

### Investment Decision domain
- InvestmentDecision is explicit human/committee decision record.
- It is separate and append-only.
- Proposed statuses:
  - PROPOSED
  - APPROVED
  - APPROVED_WITH_CHANGES
  - REJECTED
  - DEFERRED
  - CANCELLED
  - PARTIALLY_EXECUTED
  - EXECUTED
  - EXPIRED

### Retention rule
- Rejected and deferred recommendations and decisions are never overwritten or deleted.
- They are queryable for post-mortem analysis and governance reporting.

## Evidence and provenance model

### First-class Evidence required
Evidence classes:
1. external factual evidence
2. external opinion/forecast
3. internally calculated metric
4. human analyst judgement
5. model-generated analysis
6. agent-generated synthesis

- External source fact and internal interpretation are separate records linked by provenance relations.
- Model-generated summaries cannot be stored as external facts.

### Human vs model distinction
- Every mutable command must include contribution_type and contributor_id.
- contribution_type options:
  - HUMAN_ANALYST
  - MODEL_SYSTEM
  - AGENT_ORCHESTRATION
- Human verification status is explicit on evidence and on model-derived claims.

## Versioning and immutability rules

### New thesis version required when
- thesis statement, base/bull/bear framing, assumptions, valuation framework, expected return range, time horizon, confidence assessment, or claim structure changes.

### Metadata update only (no new version) when
- display tags, non-material indexing fields, or access metadata changes.

### Append-only child records
- evidence links
- thesis reviews
- metric observations
- audit events
- investment decisions
- executions

### Soft deletions only
- company/security/listing active flags via effective dating.
- recommendation supersede/cancel state transitions.

### Prohibited hard deletions
- thesis versions
- evidence
- thesis reviews
- recommendations
- investment decisions
- executions
- audit events

## Portfolio linkage contract
- Thesis context references portfolio IDs/snapshot IDs only.
- No portfolio business logic duplicated in thesis context.
- Supports:
  - one company held through multiple listings/accounts
  - one thesis linked to multiple securities/listings
  - multiple theses for one company when distinct
  - positions without active thesis
  - watchlist thesis without active holding
  - recommendations evaluated against concentration via portfolio services
  - decisions pinned to specific snapshot
  - proposed trade impact stored at decision time
  - expected vs realised outcome comparison later

## Agent boundaries
- Agents may retrieve, classify, draft, summarize, and propose.
- Agents cannot mutate durable state directly.
- Agent proposals become deterministic commands requiring validation and human approval where policy demands.

## Questions answered
1. Thesis attaches to Company by default, with optional Security/Listing overlays.
2. Company/Security/Listing separation is required now; do not defer.
3. ThesisClaim should be first-class.
4. Monitoring metrics should be first-class persisted entities.
5. Thesis review outcomes should be events; core thesis lifecycle stays compact.
6. Recommendation statuses represent proposal workflow, not thesis lifecycle.
7. Investment Decisions represent human decisions and execution state, separate from recommendations.
8. Rejected/deferred decisions are append-only retained records for analytics/governance.
9. Human judgement and agent/model content are distinguished by contribution_type + verification metadata.
10. External facts and model interpretation are separate evidence classes linked by provenance.
11. ThesisVersion, Evidence, ThesisReview, Recommendation history, Decision, Execution, AuditEvent are immutable append-only.
12. Effective dating required for company/security/listing/identifier/relationships/ticker history.
13. Minimum schema before legacy thesis UI migration:
    - company/security/listing identity tables
    - thesis root + thesis version
    - thesis claim
    - evidence/source tables
    - recommendation and decision linkage via thesis_version_id
    - compatibility projection adapters
14. Existing routes that can remain stable through adapters:
    - /api/v1/theses
    - /api/v1/theses/{thesis_id}
    - /api/v1/theses/{thesis_id}/status
    - /api/v1/theses/export
    - /api/v1/recommendations (shape-preserving extensions)
15. Before stock scorecard migration:
    - security identity and thesis linkage finalized
    - recommendation/decision split in place
    - evidence provenance for ranking rationale
    - dual-run parity checks and governance guardrails validated

## Implementation reference
Use this blueprint together with:
- system context
- container architecture
- component architecture
- domain model
- sequence diagrams
- ADR set
as mandatory reference before any broad Wave 2A coding.
