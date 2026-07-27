#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d .venv ]]; then
  python3.11 -m venv .venv
fi

source .venv/bin/activate

python -m pip install --upgrade pip >/dev/null
python -m pip install -e backend >/dev/null
python -m pip install "pytest>=8.3,<10" >/dev/null

run_suite() {
  local label="$1"
  shift
  printf '\n== %s ==\n' "$label"
  python -m pytest -q "$@"
}

run_suite "Wave 2B M1 domain contracts" \
  piios/decision_contracts/tests/test_enums_and_value_objects.py \
  piios/decision_contracts/tests/test_proposal_and_decision_entities.py \
  piios/decision_contracts/tests/test_in_memory_repositories.py

run_suite "Wave 2B M2 persistence" \
  piios/decision_contracts/tests/test_repository_contract_parity.py \
  piios/thesis_health/tests/test_thesis_health_repository_contract_parity.py \
  backend/tests/test_wave2b_m2_migration.py \
  backend/tests/test_wave2b_m2_postgres_integration.py

run_suite "Wave 2B M3 deterministic decision engine" \
  piios/decision_contracts/tests/test_recommendation_scoring_components.py \
  piios/decision_contracts/tests/test_recommendation_strategies.py \
  piios/decision_contracts/tests/test_decision_intelligence_engine.py

run_suite "Wave 2A.3 documented gate" \
  backend/tests/test_wave2a3_claims_migration.py \
  backend/tests/test_wave2a3_postgres_integration.py \
  piios/tests/test_wave2a3_claims_persistence.py \
  piios/tests/test_wave2a3_compatibility_shadow_backfill.py

run_suite "PIIOS full suite" \
  backend/tests \
  piios

printf '\nAll reproducible gates passed.\n'