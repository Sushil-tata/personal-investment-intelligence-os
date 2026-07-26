# Wave 1 Legacy vs New Equivalence Report

Date: 2026-07-26

## Objective
Compare legacy portfolio outputs with new `piios` portfolio bounded-context outputs without changing active runtime flows.

## Legacy baseline used
- `piios_backend.services.in_memory_store.store.holdings`
- `piios_backend.services.portfolio_layers.PortfolioLayersService`

## New implementation used
- `piios.portfolio.infrastructure.legacy_adapter`
- `piios.portfolio.application.services.PortfolioAnalyticsService`

## Comparison scenarios

1. Allocation parity (`asset_class`)
- Legacy endpoint behavior: `PortfolioLayersService.allocation("asset_class")`
- New behavior: `to_legacy_allocation(...)`
- Result: Equivalent total values and item market values.
- Exact values observed:
	- Legacy total value: `19200.0`
	- New total value: `19200.0`
	- Legacy `ETF` percentage: `21.88`
	- New `ETF` percentage: `21.88`
	- Legacy `Retirement Fund` percentage: `78.12`
	- New `Retirement Fund` percentage: `78.13`
- Reason for difference:
	- Legacy path uses binary float accumulation and rounding at response serialization.
	- New path uses Decimal arithmetic and explicit quantization at output boundaries.
	- The difference is exactly `0.01` percentage points and does not change ranking, totals, or allocation class membership.
- Rounding policy:
	- Money and percentages are computed from unrounded intermediate Decimal values.
	- Rounding is applied only at output boundaries (`0.01` precision).
- Approved tolerance:
	- Monetary tolerance: `0.01`
	- Percentage tolerance: `0.01`
- Classification: Expected precision normalization, not a regression.

2. Currency exposure parity
- Legacy endpoint behavior: `PortfolioLayersService.currency_exposure()`
- New behavior: `to_legacy_currency_exposure(...)`
- Result: Equivalent totals and near-equivalent percentages within 0.01 tolerance.
- Classification: Acceptable rounding difference, not a regression.

3. Net worth parity
- Legacy endpoint behavior: `PortfolioLayersService.net_worth()`
- New behavior: `to_legacy_net_worth(...)`
- Result: Equivalent net worth.

## Additional deterministic checks
- Duplicate ticker across exchanges handled with exchange-qualified keys (`TICKER:EXCHANGE`).
- Listing-country and economic-country exposures can diverge and are reported separately.
- Missing FX and missing classification fields produce explicit data-quality warnings.

## Verdict
Wave 1 parity is sufficient for non-disruptive coexistence. Existing runtime should remain on legacy paths until broader endpoint-level contract parity is validated with production-like datasets.
