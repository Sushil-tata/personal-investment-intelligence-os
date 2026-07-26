# PIIOS Container Architecture (C4 Level 2)

Date: 2026-07-26

## Container view

```mermaid
graph LR
    subgraph Users
      Investor[Investor]
      Analyst[Analyst]
      Admin[Admin]
      Committee[Committee]
    end

    subgraph PIIOS
      UI[Streamlit UI (Current)\nFuture Web UI (Planned)]
      API[FastAPI Backend]\n
      Ingestion[Ingestion Workers\n(Current limited, Planned expansion)]
      Analytics[Deterministic Analytics Layer\n(Current + Wave 1)]
      Agents[Agent Orchestration Layer\n(Planned, constrained)]
      Scheduler[Scheduled Automation\n(Current APScheduler)]
      Vector[Research Vector Index\n(Current Chroma)]
      DB[(PostgreSQL)]
    end

    subgraph External
      Broker[Broker/Custodian Exports]
      Market[Market Data APIs]
      Filings[Filings Sources]
      Research[News/Research Sources]
      LLM[LLM Providers]
      Auth[Auth Provider]
    end

    Investor --> UI
    Analyst --> UI
    Admin --> UI
    Committee --> UI

    UI --> API
    API --> Analytics
    API --> DB
    API --> Vector
    API --> Agents

    Ingestion --> API
    Ingestion --> DB
    Ingestion --> Vector

    Scheduler --> API
    Scheduler --> Ingestion

    Broker --> Ingestion
    Market --> Ingestion
    Filings --> Ingestion
    Research --> Ingestion
    Agents --> LLM
    API --> Auth
```

## Current vs planned
- Current:
  - Streamlit UI, FastAPI backend, PostgreSQL, Chroma, APScheduler, deterministic portfolio analytics.
- Planned in Wave 2A:
  - Thesis bounded context, company/security/listing identity, evidence provenance store, recommendation/decision split.
- Planned later:
  - Expanded web frontend, broader agent orchestration with strict command boundaries.
