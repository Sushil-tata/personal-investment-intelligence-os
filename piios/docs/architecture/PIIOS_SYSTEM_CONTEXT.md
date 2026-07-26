# PIIOS System Context (C4 Level 1)

Date: 2026-07-26
Purpose: define external actors and system boundaries for Wave 2A implementation.

## Scope boundary
PIIOS is an advisory-only platform. It does not execute trades and does not store broker credentials.

## Context diagram

```mermaid
graph TD
    Investor[Investor / Portfolio Owner]
    Analyst[Analyst]
    Admin[Administrator]
    Committee[Investment Committee]

    PIIOS[PIIOS Advisory Platform]

    BrokerFeeds[Broker / Custodian Export Sources]
    MarketData[Market Data Providers]
    Filings[Company Filings Sources]
    News[News / Research Providers]
    LLM[LLM Providers]
    Auth[Authentication Provider]

    Investor -->|View portfolio, thesis, recommendations| PIIOS
    Analyst -->|Create thesis, review evidence, issue recommendations| PIIOS
    Admin -->|Configure controls, policies, users| PIIOS
    Committee -->|Approve or reject investment decisions| PIIOS

    BrokerFeeds -->|Positions, transactions, snapshots| PIIOS
    MarketData -->|Prices, fundamentals, corporate actions| PIIOS
    Filings -->|Regulatory filings, disclosures| PIIOS
    News -->|Articles, reports, commentary| PIIOS
    LLM -->|Draft analysis and synthesis only| PIIOS
    Auth -->|Identity and access claims| PIIOS
```

## Boundary rules
- Humans own final investment decisions.
- Agents and models may propose but cannot mutate durable state directly.
- All durable state transitions must pass deterministic application services.
