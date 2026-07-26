# Repository Assessment Report (PIIOS v2 Blueprint)

Date: 2026-07-26
Scope: Existing repository audit and non-disruptive migration blueprint
Decision: Keep this repository and refactor in-place (no new repo)

## Executive Summary

This repository already contains the core assets for PIIOS v2:
- FastAPI service with route/domain separation
- LangGraph workflow and node graph
- PostgreSQL + Alembic migration foundation
- Scoring configuration and risk rules
- Streamlit MVP dashboard that can be migrated to modern frontend
- Test suite covering contracts, workflow, migrations, and guardrails

Primary recommendation:
1. Preserve current setup.
2. Add a parallel `piios/` target architecture scaffold.
3. Migrate incrementally from legacy modules into bounded contexts.
4. Keep agents as orchestration, not business-logic owners.

## Stage 1: Repository Audit

### Current top-level posture
- Language/runtime: Python 3.11 backend, Streamlit UI
- API framework: FastAPI
- Orchestration: LangGraph
- Persistence: PostgreSQL via SQLModel + Alembic
- Scheduling: APScheduler
- Vector memory: ChromaDB
- Testing: pytest

### Dependency inventory

Backend dependencies (from `backend/pyproject.toml`):
- fastapi
- uvicorn[standard]
- sqlmodel
- psycopg[binary]
- alembic
- pydantic-settings
- python-multipart
- pyyaml
- langgraph
- apscheduler
- yfinance
- chromadb
- pandas

Backend dev dependencies:
- pytest
- httpx
- pytest-asyncio
- ruff

Dashboard dependencies (from `dashboard/requirements.txt`):
- streamlit
- requests
- pandas

### Classification policy used
- keep: sound implementation and belongs in v2 target architecture with minimal move/rename.
- refactor: valid logic, but structure/contracts should be improved or relocated.
- replace: keep capability but rewrite implementation style/stack location.
- archive: preserve for history/legacy reference; not part of active runtime.

## Stage 1 File Inventory and Classification

| File | Role | Dependencies | Classification | Rationale |
|---|---|---|---|---|
| `.env.example` | Environment template | Runtime env vars | keep | Needed for reproducible setup |
| `IMPLEMENTATION_ROADMAP.md` | Roadmap notes | Planning | refactor | Align with staged migration plan |
| `README.md` | Primary repository documentation | Product architecture | refactor | Update docs to new piios module map |
| `backend/alembic.ini` | Alembic migration framework config | alembic sqlalchemy/sqlmodel | keep | Required for DB schema evolution |
| `backend/alembic/env.py` | Alembic migration framework config | alembic sqlalchemy/sqlmodel | keep | Required for DB schema evolution |
| `backend/alembic/script.py.mako` | Alembic migration framework config | alembic sqlalchemy/sqlmodel | keep | Required for DB schema evolution |
| `backend/alembic/versions/0001_initial_schema.py` | Database migration revision | alembic sqlmodel postgres | keep | Historical schema chain must be preserved |
| `backend/alembic/versions/0002_recommendation_review_queue.py` | Database migration revision | alembic sqlmodel postgres | keep | Historical schema chain must be preserved |
| `backend/alembic/versions/0003_theses_and_drift_linkage.py` | Database migration revision | alembic sqlmodel postgres | keep | Historical schema chain must be preserved |
| `backend/alembic/versions/0004_portfolio_layers.py` | Database migration revision | alembic sqlmodel postgres | keep | Historical schema chain must be preserved |
| `backend/config/scoring/drift_thresholds.yaml` | Scoring and risk configuration | pyyaml business rules | keep | Domain knowledge encoded in config |
| `backend/config/scoring/risk_limits.yaml` | Scoring and risk configuration | pyyaml business rules | keep | Domain knowledge encoded in config |
| `backend/config/scoring/source_credibility_weights.yaml` | Scoring and risk configuration | pyyaml business rules | keep | Domain knowledge encoded in config |
| `backend/config/scoring/stock_score_weights.yaml` | Scoring and risk configuration | pyyaml business rules | keep | Domain knowledge encoded in config |
| `backend/config/scoring/tactical_signal_weights.yaml` | Scoring and risk configuration | pyyaml business rules | keep | Domain knowledge encoded in config |
| `backend/config/scoring/target_allocation.yaml` | Scoring and risk configuration | pyyaml business rules | keep | Domain knowledge encoded in config |
| `backend/data/mock/graph_runs_fallback.json` | Mock dataset fixtures | tests local dev | refactor | Move under explicit fixtures namespace later |
| `backend/data/mock/holdings.json` | Mock dataset fixtures | tests local dev | refactor | Move under explicit fixtures namespace later |
| `backend/data/mock/journal_entries.json` | Mock dataset fixtures | tests local dev | refactor | Move under explicit fixtures namespace later |
| `backend/data/mock/recommendations.json` | Mock dataset fixtures | tests local dev | refactor | Move under explicit fixtures namespace later |
| `backend/data/mock/research_documents.json` | Mock dataset fixtures | tests local dev | refactor | Move under explicit fixtures namespace later |
| `backend/data/mock/tactical_signals.json` | Mock dataset fixtures | tests local dev | refactor | Move under explicit fixtures namespace later |
| `backend/data/mock/watchlist.json` | Mock dataset fixtures | tests local dev | refactor | Move under explicit fixtures namespace later |
| `backend/piios_backend/adapters/alpha_vantage_adapter.py` | External market data adapter | requests/yfinance provider APIs | refactor | Add retries, quotas, and fallback policy |
| `backend/piios_backend/adapters/fmp_adapter.py` | External market data adapter | requests/yfinance provider APIs | refactor | Add retries, quotas, and fallback policy |
| `backend/piios_backend/adapters/interfaces.py` | Market adapter contracts | typing protocols | keep | Good abstraction boundary |
| `backend/piios_backend/adapters/polygon_adapter.py` | External market data adapter | requests/yfinance provider APIs | refactor | Add retries, quotas, and fallback policy |
| `backend/piios_backend/adapters/tiingo_adapter.py` | External market data adapter | requests/yfinance provider APIs | refactor | Add retries, quotas, and fallback policy |
| `backend/piios_backend/adapters/yfinance_adapter.py` | External market data adapter | requests/yfinance provider APIs | refactor | Add retries, quotas, and fallback policy |
| `backend/piios_backend/api/routes/graph.py` | API resource routes | fastapi schemas services | refactor | Split by bounded context and service ports |
| `backend/piios_backend/api/routes/health.py` | Health route | fastapi | keep | Stable operational endpoint |
| `backend/piios_backend/api/routes/holdings.py` | API resource routes | fastapi schemas services | refactor | Split by bounded context and service ports |
| `backend/piios_backend/api/routes/journal.py` | API resource routes | fastapi schemas services | refactor | Split by bounded context and service ports |
| `backend/piios_backend/api/routes/portfolio.py` | API resource routes | fastapi schemas services | refactor | Split by bounded context and service ports |
| `backend/piios_backend/api/routes/portfolio_layers.py` | API resource routes | fastapi schemas services | refactor | Split by bounded context and service ports |
| `backend/piios_backend/api/routes/recommendations.py` | API resource routes | fastapi schemas services | refactor | Split by bounded context and service ports |
| `backend/piios_backend/api/routes/research.py` | API resource routes | fastapi schemas services | refactor | Split by bounded context and service ports |
| `backend/piios_backend/api/routes/risk.py` | API resource routes | fastapi schemas services | refactor | Split by bounded context and service ports |
| `backend/piios_backend/api/routes/scores.py` | API resource routes | fastapi schemas services | refactor | Split by bounded context and service ports |
| `backend/piios_backend/api/routes/tactical_signals.py` | API resource routes | fastapi schemas services | refactor | Split by bounded context and service ports |
| `backend/piios_backend/api/routes/theses.py` | API resource routes | fastapi schemas services | refactor | Split by bounded context and service ports |
| `backend/piios_backend/api/routes/watchlist.py` | API resource routes | fastapi schemas services | refactor | Split by bounded context and service ports |
| `backend/piios_backend/core/config.py` | Runtime settings model | pydantic-settings | keep | Central configuration is required |
| `backend/piios_backend/core/database.py` | DB session/engine setup | sqlmodel psycopg | keep | Foundational DB glue |
| `backend/piios_backend/core/guardrails.py` | Guardrail checks | domain constraints | refactor | Consolidate with service-level policy enforcement |
| `backend/piios_backend/graph/nodes/bear_case_node.py` | Workflow node logic | langgraph services repositories | refactor | Extract business rules into bounded contexts |
| `backend/piios_backend/graph/nodes/human_review_node.py` | Workflow node logic | langgraph services repositories | refactor | Extract business rules into bounded contexts |
| `backend/piios_backend/graph/nodes/portfolio_context_node.py` | Workflow node logic | langgraph services repositories | refactor | Extract business rules into bounded contexts |
| `backend/piios_backend/graph/nodes/portfolio_fit_node.py` | Workflow node logic | langgraph services repositories | refactor | Extract business rules into bounded contexts |
| `backend/piios_backend/graph/nodes/recommendation_node.py` | Workflow node logic | langgraph services repositories | refactor | Extract business rules into bounded contexts |
| `backend/piios_backend/graph/nodes/research_ingestion_node.py` | Workflow node logic | langgraph services repositories | refactor | Extract business rules into bounded contexts |
| `backend/piios_backend/graph/nodes/risk_check_node.py` | Workflow node logic | langgraph services repositories | refactor | Extract business rules into bounded contexts |
| `backend/piios_backend/graph/nodes/source_credibility_node.py` | Workflow node logic | langgraph services repositories | refactor | Extract business rules into bounded contexts |
| `backend/piios_backend/graph/nodes/thesis_generation_node.py` | Workflow node logic | langgraph services repositories | refactor | Extract business rules into bounded contexts |
| `backend/piios_backend/graph/state.py` | LangGraph workflow and shared state | langgraph pydantic | refactor | Keep orchestration thin over domain services |
| `backend/piios_backend/graph/workflow.py` | LangGraph workflow and shared state | langgraph pydantic | refactor | Keep orchestration thin over domain services |
| `backend/piios_backend/jobs/scheduler.py` | Scheduler and periodic tasks | apscheduler services | refactor | Separate schedule wiring from domain actions |
| `backend/piios_backend/jobs/tasks.py` | Scheduler and periodic tasks | apscheduler services | refactor | Separate schedule wiring from domain actions |
| `backend/piios_backend/main.py` | FastAPI app bootstrap | fastapi route includes | keep | Correct app entrypoint |
| `backend/piios_backend/models/entities.py` | SQLModel entities | sqlmodel | keep | Core domain persistence model |
| `backend/piios_backend/repositories/portfolio_layers.py` | Persistence repositories | sqlmodel session | keep | Useful boundary for domain data operations |
| `backend/piios_backend/repositories/theses.py` | Persistence repositories | sqlmodel session | keep | Useful boundary for domain data operations |
| `backend/piios_backend/schemas/common.py` | Pydantic request/response/domain schemas | pydantic | refactor | Group by bounded context, reduce cross-coupling |
| `backend/piios_backend/schemas/domain.py` | Pydantic request/response/domain schemas | pydantic | refactor | Group by bounded context, reduce cross-coupling |
| `backend/piios_backend/schemas/enums.py` | Pydantic request/response/domain schemas | pydantic | refactor | Group by bounded context, reduce cross-coupling |
| `backend/piios_backend/schemas/graph.py` | Pydantic request/response/domain schemas | pydantic | refactor | Group by bounded context, reduce cross-coupling |
| `backend/piios_backend/schemas/journal.py` | Pydantic request/response/domain schemas | pydantic | refactor | Group by bounded context, reduce cross-coupling |
| `backend/piios_backend/schemas/operations.py` | Pydantic request/response/domain schemas | pydantic | refactor | Group by bounded context, reduce cross-coupling |
| `backend/piios_backend/schemas/portfolio.py` | Pydantic request/response/domain schemas | pydantic | refactor | Group by bounded context, reduce cross-coupling |
| `backend/piios_backend/schemas/portfolio_layers.py` | Pydantic request/response/domain schemas | pydantic | refactor | Group by bounded context, reduce cross-coupling |
| `backend/piios_backend/schemas/recommendation.py` | Pydantic request/response/domain schemas | pydantic | refactor | Group by bounded context, reduce cross-coupling |
| `backend/piios_backend/schemas/thesis.py` | Pydantic request/response/domain schemas | pydantic | refactor | Group by bounded context, reduce cross-coupling |
| `backend/piios_backend/services/csv_io.py` | Application services | repositories schemas config | keep | Service layer is the right business-logic home |
| `backend/piios_backend/services/graph_persistence.py` | Application services | repositories schemas config | keep | Service layer is the right business-logic home |
| `backend/piios_backend/services/guardrails.py` | Application services | repositories schemas config | keep | Service layer is the right business-logic home |
| `backend/piios_backend/services/in_memory_store.py` | In-memory runtime storage | python collections | archive | Prefer explicit repository implementations |
| `backend/piios_backend/services/live_feeds.py` | Application services | repositories schemas config | keep | Service layer is the right business-logic home |
| `backend/piios_backend/services/mock_store.py` | Mock backend store | json fixtures | archive | Keep only as test/dev fixture adapter |
| `backend/piios_backend/services/portfolio_layers.py` | Application services | repositories schemas config | keep | Service layer is the right business-logic home |
| `backend/piios_backend/services/theses.py` | Application services | repositories schemas config | keep | Service layer is the right business-logic home |
| `backend/piios_backend/vector_store/chroma_store.py` | Research vector memory adapter | chromadb | refactor | Define storage interface and provider abstraction |
| `backend/pyproject.toml` | Backend packaging/dependency config | pip/setuptools | keep | Correct source of truth for backend deps |
| `backend/scripts/seed_sample_portfolio.py` | Seed/bootstrap scripts | sqlmodel config | keep | Useful for repeatable local setup |
| `backend/scripts/seed_sample_prices.py` | Seed/bootstrap scripts | sqlmodel config | keep | Useful for repeatable local setup |
| `backend/scripts/seed_sample_recommendations.py` | Seed/bootstrap scripts | sqlmodel config | keep | Useful for repeatable local setup |
| `backend/scripts/seed_sample_watchlist.py` | Seed/bootstrap scripts | sqlmodel config | keep | Useful for repeatable local setup |
| `backend/scripts/seed_scoring_config.py` | Seed/bootstrap scripts | sqlmodel config | keep | Useful for repeatable local setup |
| `backend/tests/conftest.py` | Pytest fixtures | pytest | keep | Critical test wiring |
| `backend/tests/test_adapters_yfinance.py` | Automated tests | pytest httpx | keep | Regression safety net for migration |
| `backend/tests/test_alembic_migrations.py` | Automated tests | pytest httpx | keep | Regression safety net for migration |
| `backend/tests/test_graph_workflow.py` | Automated tests | pytest httpx | keep | Regression safety net for migration |
| `backend/tests/test_guardrails.py` | Automated tests | pytest httpx | keep | Regression safety net for migration |
| `backend/tests/test_portfolio_layers.py` | Automated tests | pytest httpx | keep | Regression safety net for migration |
| `backend/tests/test_recommendation_queue.py` | Automated tests | pytest httpx | keep | Regression safety net for migration |
| `backend/tests/test_routes_contract.py` | Automated tests | pytest httpx | keep | Regression safety net for migration |
| `backend/tests/test_scheduler_jobs.py` | Automated tests | pytest httpx | keep | Regression safety net for migration |
| `backend/tests/test_scores_explainability.py` | Automated tests | pytest httpx | keep | Regression safety net for migration |
| `backend/tests/test_sprint2_thesis_and_drift.py` | Automated tests | pytest httpx | keep | Regression safety net for migration |
| `dashboard/Home.py` | Streamlit landing page | streamlit | archive | Legacy UI shell after frontend migration |
| `dashboard/lib/api_client.py` | Dashboard API client | requests | refactor | Bridge logic should move to frontend data layer |
| `dashboard/pages/01_Portfolio.py` | Streamlit feature page | streamlit requests pandas | archive | Preserve as legacy MVP surface after module migration |
| `dashboard/pages/02_Allocation.py` | Streamlit feature page | streamlit requests pandas | archive | Preserve as legacy MVP surface after module migration |
| `dashboard/pages/03_Watchlist.py` | Streamlit feature page | streamlit requests pandas | archive | Preserve as legacy MVP surface after module migration |
| `dashboard/pages/04_Research_Feed.py` | Streamlit feature page | streamlit requests pandas | archive | Preserve as legacy MVP surface after module migration |
| `dashboard/pages/05_Stock_Scorecard.py` | Stock scorecard UI | streamlit backend api | refactor | Migrate capability to frontend + research module |
| `dashboard/pages/06_Tactical_Signals.py` | Streamlit feature page | streamlit requests pandas | archive | Preserve as legacy MVP surface after module migration |
| `dashboard/pages/07_Risk_Console.py` | Streamlit feature page | streamlit requests pandas | archive | Preserve as legacy MVP surface after module migration |
| `dashboard/pages/08_Journal.py` | Streamlit feature page | streamlit requests pandas | archive | Preserve as legacy MVP surface after module migration |
| `dashboard/pages/09_LangGraph_Run_Monitor.py` | Streamlit feature page | streamlit requests pandas | archive | Preserve as legacy MVP surface after module migration |
| `dashboard/pages/10_Investment_Thesis_Registry.py` | Thesis registry UI | streamlit backend api | refactor | Migrate to Research bounded context UI/API |
| `dashboard/pages/11_Portfolio_Drift_Dashboard.py` | Streamlit feature page | streamlit requests pandas | archive | Preserve as legacy MVP surface after module migration |
| `dashboard/pages/12_Family_Portfolio_Registry.py` | Streamlit feature page | streamlit requests pandas | archive | Preserve as legacy MVP surface after module migration |
| `dashboard/pages/13_Net_Worth_Engine.py` | Streamlit feature page | streamlit requests pandas | archive | Preserve as legacy MVP surface after module migration |
| `dashboard/pages/14_Asset_Allocation_Dashboard.py` | Streamlit feature page | streamlit requests pandas | archive | Preserve as legacy MVP surface after module migration |
| `dashboard/pages/15_Currency_Exposure_Dashboard.py` | Streamlit feature page | streamlit requests pandas | archive | Preserve as legacy MVP surface after module migration |
| `dashboard/pages/16_IPS_Constraint_Layer.py` | Streamlit feature page | streamlit requests pandas | archive | Preserve as legacy MVP surface after module migration |
| `dashboard/pages/17_Instrument_Master.py` | Streamlit feature page | streamlit requests pandas | archive | Preserve as legacy MVP surface after module migration |
| `dashboard/pages/18_Data_Trust_Hierarchy.py` | Streamlit feature page | streamlit requests pandas | archive | Preserve as legacy MVP surface after module migration |
| `dashboard/pages/19_Top_Recommendations.py` | Streamlit feature page | streamlit requests pandas | archive | Preserve as legacy MVP surface after module migration |
| `dashboard/pages/20_Score_Explainability.py` | Streamlit feature page | streamlit requests pandas | archive | Preserve as legacy MVP surface after module migration |
| `dashboard/requirements.txt` | Dashboard dependency pinning | pip streamlit | keep | Needed until frontend replacement is complete |
| `docker-compose.yml` | Local infrastructure startup | PostgreSQL container | keep | Core non-code setup should remain stable |
| `piios/knowledge/REPOSITORY_ASSESSMENT_REPORT.md` | Repository file | context dependent | refactor | Needs explicit target placement in v2 modules |

## Stage 2: Target Architecture Mapping

### Bounded contexts (business modules first)
- Portfolio
- Research
- Market Data
- Analytics
- Recommendations
- Risk
- Governance

### Canonical file mapping examples

| Existing file | New module target | Action |
|---|---|---|
| `dashboard/pages/01_Portfolio.py` | `piios/frontend/pages/portfolio.*` + `piios/backend/portfolio/*` | refactor |
| `backend/piios_backend/api/routes/portfolio.py` | `piios/backend/portfolio/api.py` | refactor |
| `backend/piios_backend/repositories/portfolio_layers.py` | `piios/backend/portfolio/repository_layers.py` | keep+move |
| `backend/piios_backend/services/portfolio_layers.py` | `piios/analytics/exposure.py` | refactor |
| `dashboard/pages/05_Stock_Scorecard.py` | `piios/frontend/pages/screener.*` + `piios/research/scorecard.py` | replace UI + refactor logic |
| `dashboard/pages/10_Investment_Thesis_Registry.py` | `piios/frontend/pages/thesis_registry.*` + `piios/research/thesis_registry.py` | replace UI + refactor logic |
| `backend/piios_backend/graph/nodes/portfolio_context_node.py` | `piios/agents/orchestrators/recommendation_graph/nodes/portfolio_context.py` | refactor |
| `backend/piios_backend/graph/workflow.py` | `piios/agents/orchestrators/recommendation_graph/workflow.py` | refactor |
| `backend/piios_backend/adapters/yfinance_adapter.py` | `piios/ingestion/market_data/yfinance.py` | keep+move |
| `backend/piios_backend/vector_store/chroma_store.py` | `piios/research/memory/chroma_adapter.py` | refactor |

### Practical module placement plan

- `piios/backend/`
  - bounded context services and APIs
- `piios/frontend/`
  - next UI layer replacing streamlit MVP pages incrementally
- `piios/agents/`
  - orchestration only (LangGraph), no core business rules
- `piios/analytics/`
  - scoring, exposure, drift, explainability engines
- `piios/database/`
  - migrations, schema ownership, and persistence contracts
- `piios/ingestion/`
  - external data connectors, normalization, quality checks
- `piios/tests/`
  - context-oriented test suites and contract tests
- `piios/docs/`
  - architecture decisions, runbooks, and migration notes

## Stage 3: Refactor Sequence (safe and incremental)

1. Freeze contracts and baselines
- Keep all existing runtime entrypoints untouched.
- Capture current API behavior with route contract tests.

2. Extract bounded-context services
- Move business logic out of graph nodes/routes into context services.
- Keep old imports as shims during transition.

3. Introduce orchestration envelope
- LangGraph nodes call bounded-context service ports only.
- Enforce no DB writes directly in orchestration layer.

4. Harden persistence
- Keep PostgreSQL + Alembic as source of truth.
- Add repository interfaces and transaction boundaries.

5. Frontend replacement path
- Start with stock scorecard and thesis registry screens.
- Retire Streamlit pages after parity checks pass.

6. Governance and risk controls
- Consolidate guardrails in Risk + Governance contexts.
- Keep human approval gate mandatory for recommendation acceptance.

## Non-disruption constraints applied

- No existing file moved or deleted.
- No existing runtime command changed.
- New `piios/` scaffold added in parallel only.
- Legacy modules remain callable until explicit cutover.

## Recommended next deliverables

1. Context-by-context ADR set under `piios/docs/adr/`.
2. Import-compatibility shim plan for each moved module.
3. API contract lockfile generated from current FastAPI routes.
4. Migration board: keep/refactor/replace/archive by file owner and sprint.
