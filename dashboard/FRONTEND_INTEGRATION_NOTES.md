# Frontend Integration Notes — Wave 2B Decision Contracts

Scope of this document: what the frontend does with the live Wave 2B decision-contracts
API, what it deliberately does not render, and where the frontend contract
(`piios/docs/WAVE2B_M5_FRONTEND_CONTRACT.md`) left ambiguity that a page had to resolve
one way or another. This is not a restatement of the backend contract — read
`piios/docs/WAVE2B_M5_FRONTEND_CONTRACT.md` and `dashboard/API_GAPS.md` for that.

## Branch note

`integration/wave2b-frontend` did not exist on the remote when this work started (only
`frontend`, `main`, `wave-2b-decision-intelligence`, and the two `wave-2a*` branches did).
Per instruction, the branch was created from `wave-2b-decision-intelligence` at `b0d79bc`
(Wave 2B M5.5). `origin/frontend` was confirmed identical to `origin/main` for `dashboard/**`
— it never received the two prior frontend commits (`1f435f5`, `4b3aa90`'s parent), which
existed only locally in this sandbox clone. Both were cherry-picked onto the new branch;
`dashboard/API_GAPS.md` conflicted (both commits added it) and the backend-authored version
(the real Wave 2B M5 endpoint inventory, already present on `wave-2b-decision-intelligence`)
was kept — the frontend's older, speculative version of that file was discarded.

## Pages now using live Wave 2B APIs

- **Recommendation Review** (`pages/21_Recommendation_Review.py`) — proposal version detail,
  proposal detail, confidence diagnostic, traceability diagnostic, latest decision,
  governance backlog. All real, all by proposal-version-ID lookup.
- **Decisions** (`pages/22_Decisions.py`) — latest decision, full decision history, and
  decision capture (`POST /decision-contracts/decisions/capture`) are all live.
- **Governance Console** (`pages/23_Governance.py`) — Traceability, Replay (derived), Confidence
  Components, Decision Lineage, and Governance Review Queue tabs are live. The four
  legacy tabs (IPS Compliance, Identity Resolution, Data Quality) remain on the older,
  still-functioning identity/portfolio-layers endpoints — they were not Wave 2B work and
  were left alone per "do not replace working integration code."
- **Home** (`Home.py`) — new "Wave 2B Decision Intelligence" section shows live data for
  whichever proposal version was last looked up this session (see limitation below).

## The central frontend-only limitation: no discovery endpoint

There is no `GET /decision-contracts/proposals` (list) or equivalent for proposal versions
anywhere in the backend — confirmed by reading `backend/piios_backend/api/routes/decision_contracts.py`
and `piios/decision_contracts/application/decision_query_service.py` directly, not inferred.
Every read endpoint takes an already-known `proposal_id`, `proposal_version_id`, or
`decision_id`. Proposals are currently only created by the internal recommendation engine in
tests/functional-acceptance fixtures — there is no HTTP-visible creation path either (the
existing `/graph/run` endpoint drives an unrelated, older LangGraph pipeline that has no
linkage to decision-contracts IDs).

Consequence: Recommendation Review, Decisions, and Governance Console cannot offer a
picker/browser — they expose a **Proposal Version ID** (and, for Decision Lineage, a
**Decision ID**) text input, shared across all three pages via session state so a lookup on
one page carries over to the others. Home's new Wave 2B section only has something to show
once a proposal version has been looked up somewhere in the session; before that it shows an
honest empty state rather than an invented aggregate count.

This is not recorded as a new line in `dashboard/API_GAPS.md` because it isn't a gap in an
otherwise-listed endpoint — it's the absence of a listing capability that was never built at
any layer (no application-service method exists either, confirmed by grep). Flagging it here
for backend/product awareness: **a `GET /decision-contracts/proposal-versions` (with filters
for status/required_human_review/priority) would remove the single biggest UX limitation in
this integration.**

## Two parallel recommendation systems currently coexist

The legacy ticker-based `Recommendation` model (`GET /recommendations`, `/recommendations/queue`,
`/recommendations/top`, `PATCH /recommendations/{id}/status`) and the new decision-contracts
proposal/version/decision model are entirely separate — no shared IDs, no cross-reference field
in either direction. Home's KPI row and "Recommendation Queue"/"Recent Decisions" cards still
use the legacy system (real, live, unrelated to Wave 2B); the new "Wave 2B Decision
Intelligence" section is additive, not a replacement. Top Recommendations (`pages/19_...py`)
and the old Decisions status-PATCH flow still exist and still work — they were left alone.

## Fields intentionally not rendered

- **Supporting Claims / Supporting Evidence / Investment Thesis** on Recommendation Review:
  `RecommendationProposalVersionDetailResponse` links to a `snapshot_id` but there is no read
  endpoint for the underlying thesis/claims/evidence content. Rendered as
  "Unavailable from current persisted data" rather than guessed at.
- **Valuation, risk-impact, portfolio-impact figures**: not part of the M5 contract at all;
  not rendered, not estimated.
- **Evidence Completeness** tab (Governance Console): no such metric exists in the API.

## Contract ambiguities resolved

- **Replay has no dedicated endpoint.** The frontend contract lists a traceability diagnostic
  but no separate "replay" query. Replay is rendered by scanning the traceability diagnostic's
  `checks[]` for any entry whose `code` contains `REPLAY` (case-insensitive) and showing that
  check's status/message. If no such check is present, the Replay section shows
  "Unavailable from current persisted data" rather than a hardcoded assumption about what
  replay-check codes will be called.
- **Which optional decision-capture fields apply to which decision type** isn't stated
  explicitly in the contract beyond field naming. The frontend enables `preferred_alternative_target_key`
  only for `REJECT` and the six `modified_*` fields only for `MODIFIED`, disabling (not hiding)
  the others with an explanatory `help=` string — this is a frontend UX judgment call, not a
  backend behavior change; the backend will accept these fields regardless of decision type
  since the Pydantic model doesn't enforce that conditionality itself.
- **`UNAVAILABLE` vs `FAIL`**: confirmed in `DiagnosticStatus` usage that these are visually and
  semantically distinct everywhere in this frontend — `UNAVAILABLE` and `NOT_APPLICABLE` render
  in neutral grey, never the red used for `FAIL`. See `dashboard/DESIGN_GUIDELINES.md`.

## UX decisions worth flagging

- **Idempotent decision capture**: a `client_request_id` (UUID) is generated once per decision
  form and reused across resubmits of the same form, so an accidental double-click reuses the
  backend's own idempotency guarantee (same `decision_id` returned, no duplicate) rather than
  the frontend trying to block the click. A new UUID is only issued after a *successful*,
  distinct submission, so the next decision on the same proposal version isn't accidentally
  coupled to the prior one.
- **`REQUEST_RESEARCH` display**: per the contract, this decision type persists as
  `state=DEFERRED, reason_code=REQUEST_RESEARCH`. The frontend never renders `state` as the
  primary label — it always reads `decision_meaning` from the API response and labels it
  "Request Further Research" distinctly from ordinary "Deferred", exactly as instructed.
- **Latest vs. history**: Decisions page renders latest decision as its own section (with a
  ⭐ marker echoed in the history table) before the full immutable history table, so a reviewer
  never has to scan the whole history to find the current state.

## Unresolved backend gaps (already covered in `dashboard/API_GAPS.md`, not duplicated here)

Risk metrics beyond static limits, performance/returns, rebalancing trade tickets/tax impact,
accounts/households/tax lots, watchlist segmentation, and `/scores` typing remain open — see
that file for the full, standing list. This document only adds the discovery-endpoint gap
above, which is new since Wave 2B M5 landed.
