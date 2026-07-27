# Personal Investment Intelligence OS (PIIOS)

Standalone advisory-only and research-only investment intelligence platform.

Product boundary:
- No broker integration
- No order placement
- No auto-trading
- No margin/leverage execution
- No broker credential storage

## Stack

- FastAPI backend package: piios_backend
- Streamlit MVP dashboard package: piios_frontend style UI under dashboard
- PostgreSQL database: piios_db
- LangGraph orchestration for recommendation workflow
- Chroma vector store collection: piios_research_memory
- APScheduler for recurring jobs
- Alembic for migrations

## Buckets

The system supports four investment buckets:
- Education
- Retirement
- Strategic Alpha
- Tactical Opportunities

Every holding, watchlist idea, recommendation, and tactical signal can map to one bucket.

## LangGraph workflow

Nodes:
1. portfolio_context_node
2. research_ingestion_node
3. source_credibility_node
4. thesis_generation_node
5. bear_case_node
6. portfolio_fit_node
7. risk_check_node
8. recommendation_node
9. human_review_node

Gates:
- recommendation output is blocked unless portfolio_fit_node and risk_check_node pass.
- accepted status requires human_review_node approval.

## FastAPI routes

- /api/v1/portfolio
- /api/v1/holdings
- /api/v1/watchlist
- /api/v1/research
- /api/v1/scores
- /api/v1/recommendations
- /api/v1/tactical-signals
- /api/v1/risk
- /api/v1/journal
- /api/v1/graph/run
- /api/v1/graph/status

CSV import/export is included for:
- holdings
- watchlist
- recommendations
- journal entries
- portfolio snapshots

## Setup

1. Start PostgreSQL

```bash
docker compose up -d
```

2. Backend install and run

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn piios_backend.main:app --reload --host 127.0.0.1 --port 8000
```

3. Dashboard run

```bash
cd dashboard
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run Home.py
```

4. Tests

```bash
cd backend
pytest
```

## Wave 2B Reproducible Gate

Run the full milestone acceptance sequence from the repository root:

```bash
bash scripts/wave2b_reproducible_test_gate.sh
```

This gate executes, in order:
- Wave 2B M1 domain contracts
- Wave 2B M2 persistence
- Wave 2B M3 deterministic decision engine
- Wave 2A.3 documented gate
- Full backend plus piios test suite

## Phase 1.5 upgrades included

- yfinance adapter plus extension interfaces for Polygon, Alpha Vantage, FMP, Tiingo
- APScheduler jobs: daily market refresh, daily watchlist score refresh, alert generation, weekly drift check, weekly recommendation refresh
- Alembic migration assets and seed scripts
- Guardrails enforced in API and model contracts
