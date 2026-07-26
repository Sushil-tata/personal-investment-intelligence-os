# Wave 1 Dual-Run Verification

Date: 2026-07-26

## Scope
Development/test-only verification comparing legacy portfolio outputs with new Portfolio bounded-context outputs.

## Compared interfaces
- total value
- cash value
- listed-equity value
- country exposure (listing)
- country exposure (economic)
- currency exposure
- sector exposure
- theme exposure
- position weights
- HHI
- top holdings
- proposed-trade impact

## Comparison policy
- Exact match required for identifiers, keys, classifications, and counts.
- Monetary tolerance: 0.01
- Percentage tolerance: 0.01
- No tolerance for missing holdings or classification mismatches.
- Structured mismatch objects include: metric, path, mismatch_type, legacy_value, new_value, tolerance.

## Runtime safety
- User-facing response remains legacy response.
- No production route redirect.
- Verification runs only when:
  - `PIIOS_ENV` in `dev` or `test`, and
  - `PIIOS_PORTFOLIO_DUAL_RUN_ENABLED=true`.
- Normal logs only emit mismatch count and trigger path; they do not print full sensitive value payloads.

## Entry points
- Side-effect checks on:
  - `/api/v1/portfolio/net-worth`
  - `/api/v1/portfolio/allocation`
  - `/api/v1/portfolio/currency-exposure`
- Dev/test diagnostics:
  - `POST /api/v1/portfolio/dual-run/verify`
  - `GET /api/v1/portfolio/dual-run/last`
