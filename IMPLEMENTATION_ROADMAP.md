# PIIOS Implementation Roadmap

## Phase 1
- Standalone repo setup
- FastAPI route contracts
- LangGraph workflow and graph endpoints
- PostgreSQL schema and migration scaffold
- Streamlit dashboard pages
- CSV import and export
- Guardrails and advisory boundary

## Phase 1.5
- Live yfinance adapter
- APScheduler jobs
- Alembic migration and seed scripts
- Added route and graph tests

## Phase 2
- Expanded live data providers
- Advanced scoring calibration
- richer research ingestion and vector retrieval quality checks

## Phase 3
- backtesting suite
- workflow parallelization and committee style review
- advanced risk analytics

## Repository Hygiene Debt (Non-Blocking)
- `pip install -e backend` does not currently install `pytest`.
- Clean-clone setup currently requires a separate manual `pytest` installation.
- `backend/piios_backend.egg-info/SOURCES.txt` is tracked generated metadata and changes during editable installation.
- Preferred future improvement is repository-managed development dependency installation (for example, a `dev` optional dependency group or equivalent).
