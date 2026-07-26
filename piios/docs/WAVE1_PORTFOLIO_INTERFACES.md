# Wave 1 Portfolio Interfaces

## Scope
Portfolio bounded context and deterministic analytics only.

## Domain model interfaces

Primary entities:
- `Portfolio`
- `PortfolioSnapshot`
- `Account`
- `Holding`
- `Security`
- `CashBalance`
- `ProposedAllocation`
- `ProposedTradeImpact`
- `DataQualityIssue`

Primary value objects:
- `SecurityIdentifier`
- `Currency`
- `Money`
- `Quantity`
- `Price`
- `CostBasis`

Enums:
- `PortfolioBucket`
- `ExposureBasis`
- `CountryMode`
- `DataIssueSeverity`

## Application service interfaces

`PortfolioAnalyticsService` public methods:
- `total_portfolio_value(snapshot, fx_rates, basis)`
- `value_by_account(snapshot, fx_rates, basis)`
- `value_by_bucket(snapshot, fx_rates, basis)`
- `asset_class_exposure(snapshot, fx_rates, basis)`
- `country_exposure(snapshot, fx_rates, country_mode, basis)`
- `currency_exposure(snapshot, fx_rates, basis)`
- `sector_exposure(snapshot, fx_rates, basis)`
- `industry_exposure(snapshot, fx_rates, basis)`
- `theme_exposure(snapshot, fx_rates, basis)`
- `position_weights(snapshot, fx_rates, basis)`
- `top_holdings(snapshot, fx_rates, limit, basis)`
- `concentration_metrics(snapshot, fx_rates, basis)`
- `cash_percentage(snapshot, fx_rates)`
- `listed_equity_percentage(snapshot, fx_rates)`
- `valuation_breakdown(snapshot, fx_rates, basis)`
- `proposed_purchase_impact(snapshot, fx_rates, command_amount, proposed_country, proposed_sector, proposed_theme, proposed_ticker)`

## Infrastructure interfaces

Repository protocol (`PortfolioRepositoryProtocol`):
- `save_portfolio(portfolio)`
- `save_snapshot(snapshot)`
- `get_latest_snapshot(portfolio_id)`
- `get_snapshot_by_id(snapshot_id)`
- `list_holdings(portfolio_id, as_of_utc=None)`
- `get_portfolio_metadata(portfolio_id)`

Loader interfaces:
- `load_portfolio_snapshot_from_csv(file_path, reporting_currency, as_of_utc, portfolio_id, portfolio_name)`
- `load_portfolio_snapshot_from_excel(file_path, reporting_currency, as_of_utc, portfolio_id, portfolio_name)`

Legacy compatibility adapter:
- `from_legacy_holdings(legacy_holdings, reporting_currency, snapshot_id, owner)`
- `to_legacy_allocation(snapshot, fx_rates, dimension)`
- `to_legacy_currency_exposure(snapshot, fx_rates)`
- `to_legacy_net_worth(snapshot, fx_rates)`
