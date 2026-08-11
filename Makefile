PYTHON_BIN ?= python3.11
VENV_DIR ?= .venv
PYTHON := $(VENV_DIR)/bin/python
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest
UVICORN := $(PYTHON) -m uvicorn
STREAMLIT := $(PYTHON) -m streamlit
ALEMBIC := $(VENV_DIR)/bin/alembic

.DEFAULT_GOAL := help

help:
	@echo "PIIOS developer commands"
	@echo "  make setup        - Create repo .venv and install backend + dashboard + dev deps"
	@echo "  make db-up        - Start PostgreSQL container"
	@echo "  make db-down      - Stop PostgreSQL container"
	@echo "  make migrate      - Apply Alembic migrations to head"
	@echo "  make backend      - Start FastAPI backend on 127.0.0.1:8000"
	@echo "  make frontend     - Start Streamlit frontend on 127.0.0.1:8501"
	@echo "  make test         - Run deterministic suite + postgres integration suite"
	@echo "  make test-unit    - Run deterministic unit suites (no live providers)"
	@echo "  make test-postgres- Run PostgreSQL integration tests"
	@echo "  make lint         - Run Ruff checks"
	@echo "  make health       - Probe key backend endpoints"

setup:
	@test -x "$(PYTHON_BIN)" || (echo "Missing $(PYTHON_BIN). Install Python 3.11.x." && exit 1)
	$(PYTHON_BIN) -m venv $(VENV_DIR)
	$(PIP) install --upgrade pip
	$(PIP) install -e "backend[dev,dashboard]"

db-up:
	docker compose up -d postgres

db-down:
	docker compose stop postgres

migrate:
	cd backend && ../$(ALEMBIC) upgrade head

backend:
	$(UVICORN) piios_backend.main:app --reload --host 127.0.0.1 --port 8000

frontend:
	PIIOS_API_BASE=$${PIIOS_API_BASE:-http://127.0.0.1:8000/api/v1} $(STREAMLIT) run dashboard/Home.py --server.port 8501 --server.address 127.0.0.1

test: test-unit test-postgres

test-unit:
	$(PYTEST) backend/tests/test_wave3_recommendation_mvp.py backend/tests/test_recommendation_queue.py backend/tests/test_scores_explainability.py piios/tests dashboard/tests/test_api_client.py dashboard/tests/test_components.py -q

test-postgres:
	$(PYTEST) backend/tests/test_wave2b_m2_postgres_integration.py backend/tests/test_wave2b_m3_functional_acceptance_postgres.py backend/tests/test_wave2b_m4_traceability_functional_postgres.py backend/tests/test_wave2b_m5_functional_acceptance_postgres.py backend/tests/test_wave2b_m5_decision_invariants_postgres.py backend/tests/test_wave2a3_postgres_integration.py -q

lint:
	$(PYTHON) -m ruff check backend/piios_backend piios dashboard

health:
	curl -fsS http://127.0.0.1:8000/health
	curl -fsS http://127.0.0.1:8000/api/v1/decision-contracts/health
	curl -fsS http://127.0.0.1:8000/api/v1/portfolio
