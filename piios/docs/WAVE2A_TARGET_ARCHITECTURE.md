# Wave 2A Target Architecture (Final)

Date: 2026-07-26
Scope: Final blueprint before broad Wave 2A implementation

## Bounded contexts

1. Identity context
- Company (issuer)
- Security (issued financial claim)
- Listing Instrument (exchange tradable representation)
- Identifier and relationship submodels

2. Thesis context
- company-anchored thesis root
- immutable thesis versions
- explicit thesis claims
- review events and schedules

3. Research context
- source registry
- evidence and provenance records
- internal interpretation separate from external facts

4. Recommendation context
- analytical proposals linked to thesis versions and subject references

5. Investment Decision context
- human/committee decisions linked to recommendations and portfolio snapshots
- execution tracking and outcomes

6. Portfolio context (Wave 1)
- remains system of record for holdings/snapshots and deterministic exposure analytics
- referenced via service interface and IDs only

7. Governance and audit context
- approval controls
- append-only audit event stream

8. Agent orchestration context
- read/propose only
- no direct durable state mutation

## Target module layout

- piios/identity/
  - domain/
  - application/
  - infrastructure/
- piios/thesis/
  - domain/
  - application/
  - infrastructure/
- piios/research/
  - domain/
  - application/
  - infrastructure/
- piios/recommendation/
  - domain/
  - application/
  - infrastructure/
- piios/investment_decision/
  - domain/
  - application/
  - infrastructure/
- piios/governance/
  - domain/
  - application/
  - infrastructure/
- piios/agents/
  - orchestration/
  - policies/

## Identity model

### Company
- company_id
- legal_name
- issuer_type
- domicile_country
- status
- effective dates

### Security
- security_id
- company_id
- security_type
- class/seniority
- terms metadata
- optional ISIN
- status
- effective dates

### Listing Instrument
- listing_id
- security_id
- exchange
- local_ticker
- trading_currency
- lot size
- listing_country
- mic
- active dates
- price source

### Supporting identity entities
- security identifiers (external namespace IDs)
- ticker history
- security relationships (ADR_OF, DUAL_LISTING_OF, SUCCESSOR_OF)

## Thesis anchoring and overlays
- Primary thesis anchor: company_id.
- Optional overlays:
  - security scoped claim or assumption
  - listing scoped claim or risk
- No full thesis duplication per listing.
- Overlay references are additive and versioned.

## Lifecycle model (final)

### Thesis state
- DRAFT
- ACTIVE
- UNDER_REVIEW
- INVALIDATED
- CLOSED

### Thesis review outcomes (events)
- REAFFIRMED
- WEAKENED
- POTENTIALLY_BROKEN
- INVALIDATED_REVIEW

### Recommendation state
- DRAFT
- READY_FOR_REVIEW
- PENDING_DECISION
- ACCEPTED
- MODIFIED
- REJECTED
- DEFERRED
- EXPIRED
- SUPERSEDED

### Investment decision state
- PROPOSED
- APPROVED
- APPROVED_WITH_CHANGES
- REJECTED
- DEFERRED
- CANCELLED
- PARTIALLY_EXECUTED
- EXECUTED
- EXPIRED

## Immutability and versioning
- Material thesis edits create new thesis versions.
- Evidence, reviews, decisions, executions, and audit events are append-only.
- Current-state projections may be mutable pointers.
- Hard delete prohibited for thesis versions, evidence, reviews, decisions, executions, audit events.

## Compatibility and cutover
- Current thesis endpoints remain stable via compatibility adapters.
- Existing Streamlit pages continue using stable route contracts.
- Route or UI cutover only after dual-run parity and migration checks pass.
