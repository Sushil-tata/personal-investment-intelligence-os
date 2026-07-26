# Wave 2A Security Identity Gap Assessment

Date: 2026-07-26

## Current state
Current repository has partial identity assets:
- `Asset` entity: `ticker`, `name`, `asset_class`
- `InstrumentMasterEntity`: `instrument_id`, `ticker`, `name`, `asset_class`, `currency`, `exchange`, `data_source`

Gaps for durable cross-context identity:
- no issuer/company ID
- no listing-country field in instrument master
- no ISIN/CUSIP storage
- no external-id namespace model
- no dual-listing / ADR relationship model
- no ticker history table for symbol changes
- thesis and recommendation tables still keyed by ticker text in critical fields

## Risk
Ticker-only identity is insufficient for thesis persistence and provenance:
- symbol collisions across exchanges
- dual-listing ambiguity
- ADR/local share confusion
- inability to preserve historical references when ticker changes

## Minimum Security Identity component required for Wave 2A
Introduce minimal deterministic identity model before broad thesis migration:

1. `security_master`
- `security_id` (internal primary ID)
- `issuer_id`
- `exchange_code`
- `local_ticker`
- `listing_country`
- `trading_currency`
- `isin` (nullable)
- `is_active`
- `effective_from_utc`, `effective_to_utc` (nullable)

2. `security_external_identifiers`
- `security_id`
- `id_type` (ISIN/CUSIP/FIGI/ProviderSymbol/etc.)
- `id_value`
- `source`

3. `security_relationships`
- `parent_security_id`
- `child_security_id`
- `relationship_type` (ADR_OF, DUAL_LISTING_OF, SUCCESSOR_OF)

4. `security_ticker_history`
- `security_id`
- `exchange_code`
- `ticker`
- `status` (ACTIVE/INACTIVE)
- `effective_from_utc`, `effective_to_utc`

## Recommendation
Security Identity should precede full thesis-domain migration. The thesis model should reference `security_id` while retaining ticker as display metadata.
