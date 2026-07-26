# PIIOS Component Architecture (C4 Level 3)

Date: 2026-07-26

## Component map

```mermaid
graph TB
    subgraph API[FastAPI Backend]
      PortfolioAPI[Portfolio API]
      ThesisAPI[Thesis API]
      RecommendationAPI[Recommendation API]
      DecisionAPI[Investment Decision API]
      ResearchAPI[Research API]
      RiskAPI[Risk API]
      GovernanceAPI[Governance/Audit API]
    end

    subgraph Portfolio[Portfolio Context]
      PortfolioSvc[Portfolio Application Services]
      PortfolioRepo[Portfolio Repositories]
      PortfolioAnalytics[Deterministic Portfolio Analytics]
    end

    subgraph Identity[Company/Security/Listing Identity Context]
      CompanySvc[Company Identity Services]
      SecuritySvc[Security Identity Services]
      ListingSvc[Listing Instrument Services]
      IdentityRepo[Identity Repositories]
    end

    subgraph Thesis[Thesis Registry Context]
      ThesisSvc[Thesis Services]
      ThesisVersioning[Versioning Service]
      ClaimSvc[Thesis Claim Service]
      MonitoringSvc[Monitoring Metric Service]
      ThesisRepo[Thesis Repositories]
    end

    subgraph Research[Research/Evidence Context]
      SourceSvc[Research Source Service]
      EvidenceSvc[Evidence Service]
      ProvenanceSvc[Provenance Service]
      ResearchRepo[Research Repositories]
    end

    subgraph Recommendations[Recommendation Context]
      RecommendationSvc[Recommendation Services]
      RecommendationRepo[Recommendation Repositories]
    end

    subgraph Decisions[Investment Decision Context]
      DecisionSvc[Decision Services]
      ExecutionSvc[Execution Tracking Services]
      DecisionRepo[Decision Repositories]
    end

    subgraph Governance[Governance and Audit]
      ApprovalSvc[Human Approval Service]
      AuditSvc[Audit Event Service]
      PolicySvc[Policy Validation Service]
    end

    subgraph Agents[Agent Orchestration Context]
      AgentOrchestrator[Agent Orchestrator]
      AgentRunSvc[Agent Run Tracking]
    end

    PortfolioAPI --> PortfolioSvc
    ThesisAPI --> ThesisSvc
    RecommendationAPI --> RecommendationSvc
    DecisionAPI --> DecisionSvc
    ResearchAPI --> EvidenceSvc
    RiskAPI --> PolicySvc
    GovernanceAPI --> AuditSvc

    ThesisSvc --> CompanySvc
    ThesisSvc --> SecuritySvc
    ThesisSvc --> ListingSvc
    ThesisSvc --> ClaimSvc
    ThesisSvc --> MonitoringSvc

    ClaimSvc --> EvidenceSvc
    EvidenceSvc --> SourceSvc

    RecommendationSvc --> ThesisSvc
    RecommendationSvc --> PortfolioSvc
    DecisionSvc --> RecommendationSvc
    DecisionSvc --> PortfolioSvc
    DecisionSvc --> PolicySvc
    DecisionSvc --> ApprovalSvc
    DecisionSvc --> AuditSvc

    AgentOrchestrator --> EvidenceSvc
    AgentOrchestrator --> ThesisSvc
    AgentOrchestrator --> RecommendationSvc
    AgentOrchestrator --> AgentRunSvc

    AgentOrchestrator -.no direct write.-> ThesisRepo
    AgentOrchestrator -.no direct write.-> DecisionRepo
```

## Component constraints
- Portfolio logic remains in Portfolio context.
- Thesis context references portfolio snapshots through IDs and query interfaces only.
- Recommendation and Investment Decision are separate bounded contexts.
- Agent orchestration is read/propose; mutation requires deterministic services + approval gates.
