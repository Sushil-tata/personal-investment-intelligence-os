# Dashboard API Gaps

## Available Now
- Decision capture (advisory-only): POST /api/v1/decision-contracts/decisions/capture
- Proposal detail: GET /api/v1/decision-contracts/proposals/{proposal_id}
- Proposal-version detail: GET /api/v1/decision-contracts/proposal-versions/{proposal_version_id}
- Decisions for proposal version: GET /api/v1/decision-contracts/proposal-versions/{proposal_version_id}/decisions
- Latest decision for proposal version: GET /api/v1/decision-contracts/proposal-versions/{proposal_version_id}/decisions/latest
- Traceability diagnostic: GET /api/v1/decision-contracts/proposal-versions/{proposal_version_id}/diagnostics/traceability
- Confidence diagnostic: GET /api/v1/decision-contracts/proposal-versions/{proposal_version_id}/diagnostics/confidence
- Decision-lineage diagnostic: GET /api/v1/decision-contracts/decisions/{decision_id}/diagnostics/lineage
- Governance review backlog: GET /api/v1/decision-contracts/proposal-versions/{proposal_version_id}/governance-backlog

## Application Service Exists, HTTP Endpoint Absent
- None identified for completed Wave 2B M5 scope.

## Planned for Wave 3
- Durable governance backlog workflow state transitions (acknowledged/resolved/escalated).
- First-class persisted REQUEST_RESEARCH decision semantic (if approved in Wave 3 domain model).
- Governance escalation workflow orchestration endpoints.

## Intentionally Excluded
- Trade execution endpoints.
- Broker connectivity and order placement controls.
- Automated approval endpoints.
- Portfolio construction/allocation/risk execution paths from decision-contract flows.
