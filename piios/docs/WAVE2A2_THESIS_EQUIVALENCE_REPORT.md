# Wave 2A.2 Thesis Equivalence Report

Date: 2026-07-26

## Objective

Verify that current thesis API behavior remains shape-compatible while backend thesis logic is backed by the new versioned domain.

## Equivalence Strategy

- Keep legacy table `investment_theses` active.
- Use compatibility projection from latest versioned thesis record to legacy schema shape.
- Run shadow diagnostics comparing legacy rows against versioned projected rows for key fields.
- Auto-sync missing versioned rows from legacy during diagnostics for deterministic side-by-side comparison.

## Compared Fields

- ticker
- asset_name
- theme
- bucket
- thesis
- bull_case
- bear_case
- why_now
- why_not_now
- invalidation_trigger
- valuation_notes
- expected_holding_period
- source_documents (normalized)
- confidence_score
- status (normalized)

## Test Evidence

- `backend/tests/test_wave2a2_thesis_compatibility.py`
  - verifies thesis route contract shape remains unchanged.
  - verifies shadow diagnostics reports no mismatches after sync.
- `backend/tests/test_sprint2_thesis_and_drift.py`
  - existing lifecycle/route behavior remains functional.
- `backend/tests/test_routes_contract.py`
  - required route availability remains intact.

## Outcome

Route-level thesis contract parity is preserved for existing consumers while versioned thesis records are maintained append-only in the new domain.
