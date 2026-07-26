# Wave 1 Migration Notes: Portfolio Context Extraction

Date: 2026-07-26

## Goals achieved
- Added explicit Portfolio domain model and value objects.
- Added deterministic analytics services using Decimal.
- Added CSV and XLSX loaders with validation and issue reporting.
- Added repository protocol and in-memory implementation.
- Added legacy adapter for bidirectional compatibility.
- Added regression and equivalence tests.

## Zero-break strategy used
- No legacy files moved.
- No legacy files deleted.
- No active API route redirected.
- No dashboard page behavior intentionally changed.

## Compatibility approach
- Legacy callers keep existing import paths.
- New code is invoked independently via `piios` modules.
- Legacy structures are transformed into new typed domain objects.
- New outputs can be emitted in legacy-compatible structures.

## Data-quality posture
- Missing FX is surfaced as warning/error, not silently ignored.
- Missing sector/economic country is surfaced as warnings.
- Invalid rows are reported with row-level issues.

## Known Wave 1 limits
- Excel ingestion requires `openpyxl` in the Python environment.
- New modules are not yet wired into existing FastAPI routes.
- Realized PnL is not computed because trade-lot realization data is not present in current fixtures.

## Suggested cutover gate
- Keep legacy runtime active.
- Add endpoint-level A/B checks (legacy vs new) for portfolio and allocation APIs.
- Cut over only when parity and data-quality thresholds are approved.
