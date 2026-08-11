# Personal Investment Intelligence OS (PIIOS)

PIIOS is an advisory-only and research-only investment intelligence platform.

Product boundary:
- No broker integration
- No order placement
- No auto-trading
- No margin/leverage execution
- No broker credential storage

Current packaged application version: **PIIOS 0.3.2**.

## Prerequisites

- Python **3.11.x** (supported range: `>=3.11,<3.12`)
- Docker Desktop (for local PostgreSQL)
- macOS/Linux shell with `make`

Do not use system-wide packages for project runtime. Use the repository-local virtual environment only.

## Canonical Local Setup

From repository root:

```bash
make setup
cp .env.example .env
```

This creates and manages the only supported development environment:

```text
<repo>/.venv
```

## Environment Variables

Environment is loaded from `.env` by backend settings.

Key variables (see `.env.example` for full list):
- `PIIOS_ENV`
- `PIIOS_API_PREFIX`
- `PIIOS_DB_URL`
- `PIIOS_CORS_ORIGINS`
- `PIIOS_API_BASE`
- `PIIOS_VECTOR_BACKEND`
- `PIIOS_VECTOR_PATH`
- `PIIOS_VECTOR_COLLECTION`
- `PIIOS_MODEL_VERSION`
- `PIIOS_LIVE_MARKET_FEEDS`
- `PIIOS_LIVE_TICKERS`

## PostgreSQL

Supported local database flow:

```bash
make db-up
```

Default local DB config:
- host: `localhost`
- port: `5432`
- database: `piios_db`
- user: `piios`
- password: `piios`

## Migrations (Alembic)

Apply migrations:

```bash
make migrate
```

Manual checks:

```bash
cd backend
../.venv/bin/alembic heads
../.venv/bin/alembic current
```

## Backend Startup

Start FastAPI from repo root:

```bash
make backend
```

Health checks:

```bash
make health
```

## Frontend Startup

Start Streamlit from repo root:

```bash
make frontend
```

Frontend uses `PIIOS_API_BASE` (default `http://127.0.0.1:8000/api/v1`).

## Tests

Run deterministic unit suite:

```bash
make test-unit
```

Run PostgreSQL integration suite:

```bash
make test-postgres
```

Run both:

```bash
make test
```

## Lint

```bash
make lint
```

## Live Market Data Behavior

- Live market providers are controlled by `PIIOS_LIVE_MARKET_FEEDS`.
- Provider-dependent checks should be treated as network/live smoke tests, separate from deterministic unit tests.

## Troubleshooting

- Backend import errors:
	Use `make setup` and `make backend` from repo root. Do not run with ad-hoc `PYTHONPATH`.
- Frontend cannot reach backend:
	Confirm backend is running and `PIIOS_API_BASE` points to `http://127.0.0.1:8000/api/v1`.
- Migration issues:
	Ensure PostgreSQL is up (`make db-up`) before `make migrate`.
- Wrong environment:
	Use `.venv` in repo root only. Do not use `backend/.venv` or `dashboard/.venv`.
