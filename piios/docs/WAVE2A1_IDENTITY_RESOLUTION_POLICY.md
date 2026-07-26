# Wave 2A.1 Identity Resolution Policy

Date: 2026-07-26
Status: Implemented

## Deterministic principles
- No LLM matching.
- Internal IDs are authoritative.
- Ticker text is never durable identity by itself.
- Effective-date windows are enforced.
- Conflicts are surfaced; no silent overwrite.

## Resolution precedence
1. Exact internal IDs: company_id, security_id, listing_id.
2. Verified authoritative identifiers: ISIN (and equivalent configured authoritative IDs).
3. Verified provider identifiers scoped by provider namespace.
4. Active exchange+ticker match within effective period.
5. Historical exchange+ticker when explicit past effective date is requested.
6. Legacy mapping table.
7. Company name + jurisdiction heuristic.
8. Ticker-only heuristic (allowed only when unique candidate; otherwise ambiguous).

## Outcomes
- RESOLVED
- HISTORICAL_MATCH
- UNRESOLVED
- AMBIGUOUS
- CONFLICTING

## Ambiguity handling
- Candidate list is always returned for ambiguous/conflicting cases.
- Ticker-only ambiguous matches require human review.
- Ambiguous outcomes are persisted to identity resolution issue queue.

## Conflict handling
- If authoritative identifier and provider identifier resolve to different entities, result is CONFLICTING.
- Existing records and mappings are not overwritten.
- Conflict enters owner-review workflow.

## Review contract fields
- issue_id
- source_record_type
- source_record_id
- reason
- candidate_payload
- recommended_resolution
- owner_decision
- reviewer
- reviewed_at
- notes
- resulting_mapping_id
- status

## Security and observability
- Resolution diagnostics are dev/test safe.
- Shadow diagnostics do not mutate legacy responses.
- Sensitive holding values are not logged by the resolution flow.
