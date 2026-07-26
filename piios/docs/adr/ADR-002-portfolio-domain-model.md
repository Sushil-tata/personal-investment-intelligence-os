# ADR-002: Portfolio Domain Model

## Status
Proposed

## Context
Current portfolio calculations span multiple modules and UI pages. Domain concepts are often represented as loose dictionaries, making validation, currency precision, and exposure semantics inconsistent.

## Decision
Define an explicit Portfolio bounded-context domain model with typed entities and value objects using Decimal-based money math.
Required concepts include:
- Portfolio, PortfolioBucket, Account
- Holding, Security, SecurityIdentifier
- CashBalance, Currency, Money, Quantity, Price, CostBasis
- CountryExposure, SectorExposure, ThemeExposure
- PortfolioSnapshot, ProposedAllocation, ProposedTradeImpact

Required analytical distinctions:
- total net-worth exposure
- liquid investable portfolio exposure
- listed-equity exposure

Required value distinctions:
- country of listing vs country of economic exposure
- trading currency vs reporting currency
- current market value vs original cost value
- original vs converted reporting value
- realised vs unrealised PnL
- cash vs securities
- bucket vs account

Missing classifications must produce explicit warnings; no silent inference.

## Alternatives Considered
- Keep dictionary payloads: rejected due to low safety.
- ORM-first entities as domain model: rejected due to infrastructure coupling.
- Float-based money calculations: rejected due to rounding errors.

## Consequences
- Stronger validation and predictable analytics.
- Slightly more verbose DTO/entity mapping.

## Implementation Implications
- Use dataclasses for entities/value objects and Pydantic DTOs at boundaries.
- Use Decimal for all money/quantity calculations.
- Maintain original values and converted values separately.

## Migration Implications
- Add legacy adapters mapping old structures to new typed models.
- Preserve old imports while routing logic into new services.

## Open Questions
- Canonical source for economic exposure taxonomy.
- Tolerance rules for stale prices by asset class and market hours.
