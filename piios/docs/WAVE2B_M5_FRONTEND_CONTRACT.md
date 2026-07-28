# Wave 2B M5 Frontend Contract

## Scope
This contract defines read/write integration points for Wave 2B decision capture and diagnostics.

Boundary:
- Recommendation Proposal != Human Investment Decision != Trade Execution.
- Advisory-only. No execution endpoint, no order routing, no broker control.

## Query/Service Names
Transport-independent application services:
- DecisionQueryService.get_recommendation_proposal_detail
- DecisionQueryService.get_proposal_version_detail
- DecisionQueryService.list_decisions_for_proposal_version
- DecisionQueryService.get_latest_decision_for_proposal_version
- DecisionQueryService.get_traceability_diagnostic
- DecisionQueryService.get_confidence_diagnostic
- DecisionQueryService.get_decision_lineage_diagnostic
- DecisionQueryService.get_governance_review_backlog

Write service:
- DecisionCaptureService.capture

## HTTP Endpoints (Current)
- POST /api/v1/decision-contracts/decisions/capture
- GET /api/v1/decision-contracts/proposals/{proposal_id}
- GET /api/v1/decision-contracts/proposal-versions/{proposal_version_id}
- GET /api/v1/decision-contracts/proposal-versions/{proposal_version_id}/decisions
- GET /api/v1/decision-contracts/proposal-versions/{proposal_version_id}/decisions/latest
- GET /api/v1/decision-contracts/proposal-versions/{proposal_version_id}/diagnostics/traceability
- GET /api/v1/decision-contracts/proposal-versions/{proposal_version_id}/diagnostics/confidence
- GET /api/v1/decision-contracts/decisions/{decision_id}/diagnostics/lineage
- GET /api/v1/decision-contracts/proposal-versions/{proposal_version_id}/governance-backlog

## Identifiers
- proposal_id: immutable recommendation proposal identity
- proposal_version_id: immutable recommendation proposal-version identity
- decision_id: immutable human decision identity
- review_item_id: deterministic governance backlog item identity

## Status/Severity Enums
Diagnostic status values:
- PASS
- FAIL
- WARNING
- UNAVAILABLE
- NOT_APPLICABLE

Diagnostic severity values:
- INFO
- LOW
- MEDIUM
- HIGH
- CRITICAL

Decision type values (capture request):
- ACCEPT
- REJECT
- MODIFIED
- OVERRIDDEN
- DEFERRED
- REQUEST_RESEARCH

Decision state values (persisted decision):
- ACCEPTED
- REJECTED
- MODIFIED
- OVERRIDDEN
- DEFERRED

Decision meaning values (frontend interpretation):
- ACCEPTED
- REJECTED
- MODIFIED
- OVERRIDDEN
- DEFERRED
- REQUEST_RESEARCH

## REQUEST_RESEARCH Representation
Current persisted representation is preserved:
- state = DEFERRED
- reason_code = REQUEST_RESEARCH (fallback if request omits reason_code)

Frontend must use decision_meaning from query projections:
- decision_meaning = REQUEST_RESEARCH when state==DEFERRED and reason_code==REQUEST_RESEARCH
- decision_meaning = DEFERRED for ordinary postponement

Governance backlog interpretation:
- reason_code = REQUEST_RESEARCH_DECISION indicates a governance review item derived from a REQUEST_RESEARCH human decision.

## Required vs Optional Fields
Recommendation proposal detail (required):
- proposal_id, target_type, target_key, scope, status, created_at, updated_at

Proposal-version detail (required):
- proposal_version_id, proposal_id, version_number, status, created_at, snapshot_id
- action, authoritative_confidence, priority_level, priority_score, required_human_review

Proposal-version detail (optional):
- action_note, action_min_weight, action_max_weight, supersedes_version_id

Decision detail (required):
- decision_id, proposal_version_id, state, decision_meaning, reason_code, decided_at

Decision detail (optional):
- reason_text, decided_by, preferred_alternative_target_key
- modified_action, modified_action_note
- modified_action_min_weight, modified_action_max_weight
- modified_position_min_weight, modified_position_max_weight

## Date/Time and Decimal Format
- Date-time: RFC 3339 / ISO-8601 UTC-compatible strings
- Decimal confidence and scores: numeric JSON values
- Confidence range: 0.0 to 1.0

## Confidence Representation
Authoritative confidence:
- authoritative_confidence is persisted recommendation confidence and must not be recomputed by frontend.

Diagnostic confidence components:
- Each component includes name, value, status, source, explanation.
- value may be null when status is UNAVAILABLE or NOT_APPLICABLE.

## Immutability and Versioning
- Proposal versions are append-only recommendation states.
- Decisions are immutable records; updates are represented by new decisions.
- Capture idempotency returns existing decision for identical request semantics.

## Idempotency Expectations
Repeated identical capture request:
- returns existing decision_id
- does not create duplicate decision records

Different capture request on same proposal_version_id:
- creates distinct immutable decision record when valid

## UI Loading / Error / Empty Semantics
Loading:
- show non-final state until all requested endpoints return.

Error:
- 404 for unknown identifiers
- 409 for lineage conflicts (for example orphan reference)
- 422 for invalid capture payload
- 503 for repository/persistence unavailable

Empty states:
- decisions list may be empty before human decision
- latest decision may be null
- governance backlog may be empty tuple for clean case

## Advisory-Only Label
All frontend surfaces must retain advisory-only indicator from API payloads.
No endpoint implies trade execution authority.
