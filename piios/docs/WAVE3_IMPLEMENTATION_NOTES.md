# Wave 3 Implementation Notes

## Existing Flow Trace (Before Wave 3)
portfolio input
-> in-memory snapshot and holdings from backend store
-> optional market enrichment via yfinance in `live_feeds`
-> score/research convenience projections (`/scores`, `/research`)
-> recommendation list route (`/api/v1/recommendations`)
-> API response with generic recommendation records
-> dashboard rendering in recommendation review pages

## What Already Worked
- Existing portfolio/holdings/watchlist APIs were available.
- Existing recommendation routes returned queue and status update contracts.
- Existing `live_feeds` service could enrich basic recommendation objects with market context.
- Dashboard had typed API client and robust error-handling primitives.

## What Was Incomplete
- No endpoint generated a deployable allocation recommendation for a specific amount.
- No deterministic local engine mapped portfolio context into BUY/ADD/HOLD/REDUCE/RESEARCH/AVOID actions with explicit allocation totals.
- Existing recommendation records did not include post-allocation weights, score components, market-data mode disclosure, fallback reasons, or limitations suitable for decision-grade UX.
- Dashboard did not have an investment recommendation page focused on actionable USD allocation.

## Why Product Value Was Limited
- Existing outputs emphasized diagnostics and contract integrity rather than a concrete deploy-now answer.
- Capital-allocation guidance was missing; users could not see a reconciled USD 5,000 plan.

## Components Extended in Wave 3
- `backend/piios_backend/schemas/recommendation.py`
- `backend/piios_backend/services/recommendation_mvp.py`
- `backend/piios_backend/api/routes/recommendations.py`
- `dashboard/lib/models.py`
- `dashboard/lib/api_client.py`
- `dashboard/pages/28_Investment_Recommendations.py`

## Components Intentionally Not Used for Wave 3 MVP
- No new provider stack (Twelve Data / additional external market-data providers) introduced.
- No new vector database or orchestration framework introduced.
- No external recommendation engine or LLM decision delegation introduced.
- Existing LangGraph/chromadb infrastructure left unchanged for this milestone.
