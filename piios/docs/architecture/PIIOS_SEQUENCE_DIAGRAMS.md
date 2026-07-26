# PIIOS Sequence Diagrams

Date: 2026-07-26

## 1. Import Portfolio

```mermaid
sequenceDiagram
    participant User as Analyst
    participant UI as UI
    participant API as Portfolio API
    participant Loader as Portfolio Loader Service
    participant Repo as Portfolio Repository
    participant Audit as Audit Service

    User->>UI: Upload portfolio file
    UI->>API: POST import request
    API->>Loader: Parse and validate rows
    Loader-->>API: PortfolioSnapshot + warnings/errors
    API->>Repo: Save snapshot and holdings projection
    Repo-->>API: Snapshot ID
    API->>Audit: Record import event
    API-->>UI: Import result + quality issues
```

## 2. Create New Thesis

```mermaid
sequenceDiagram
    participant Analyst
    participant UI
    participant ThesisAPI as Thesis API
    participant Identity as Company/Security Identity Service
    participant ThesisSvc as Thesis Service
    participant ThesisRepo as Thesis Repository
    participant Audit

    Analyst->>UI: Submit thesis draft
    UI->>ThesisAPI: Create thesis
    ThesisAPI->>Identity: Resolve company/security/listing refs
    Identity-->>ThesisAPI: Valid references
    ThesisAPI->>ThesisSvc: Validate command
    ThesisSvc->>ThesisRepo: Create thesis root + version v1
    ThesisRepo-->>ThesisSvc: thesis_id + version_id
    ThesisSvc->>Audit: Append THESIS_CREATED
    ThesisSvc-->>UI: Thesis created response
```

## 3. Update Thesis After Earnings

```mermaid
sequenceDiagram
    participant Analyst
    participant UI
    participant ThesisAPI
    participant ThesisSvc
    participant ThesisRepo
    participant EvidenceSvc
    participant Audit

    Analyst->>UI: Submit thesis update
    UI->>ThesisAPI: Update thesis command
    ThesisAPI->>EvidenceSvc: Link earnings evidence
    EvidenceSvc-->>ThesisAPI: Evidence link references
    ThesisAPI->>ThesisSvc: Create new thesis version
    ThesisSvc->>ThesisRepo: Append version vN
    ThesisRepo-->>ThesisSvc: version_id
    ThesisSvc->>Audit: Append THESIS_VERSION_CREATED
    ThesisSvc-->>UI: Updated thesis projection
```

## 4. Generate Recommendation

```mermaid
sequenceDiagram
    participant AnalystOrAgent as Analyst/Agent
    participant RecommendationAPI
    participant RecommendationSvc
    participant ThesisSvc
    participant PortfolioSvc
    participant RiskSvc
    participant Repo as Recommendation Repository
    participant Audit

    AnalystOrAgent->>RecommendationAPI: Propose recommendation
    RecommendationAPI->>ThesisSvc: Resolve thesis version
    RecommendationAPI->>PortfolioSvc: Fetch portfolio snapshot context
    RecommendationAPI->>RiskSvc: Evaluate constraints
    RecommendationAPI->>RecommendationSvc: Validate and score proposal
    RecommendationSvc->>Repo: Persist recommendation
    RecommendationSvc->>Audit: Append RECOMMENDATION_CREATED
    RecommendationSvc-->>RecommendationAPI: Recommendation response
```

## 5. Make Investment Decision

```mermaid
sequenceDiagram
    participant Committee
    participant UI
    participant DecisionAPI as Decision API
    participant DecisionSvc as Decision Service
    participant PortfolioSvc
    participant RiskSvc
    participant Approval as Human Approval Service
    participant DecisionRepo
    participant Audit

    Committee->>UI: Submit decision on recommendation
    UI->>DecisionAPI: Decision command
    DecisionAPI->>PortfolioSvc: Bind to snapshot
    DecisionAPI->>RiskSvc: Validate constraints and concentration
    DecisionAPI->>Approval: Validate approver authority
    DecisionAPI->>DecisionSvc: Build decision record
    DecisionSvc->>DecisionRepo: Append decision
    DecisionSvc->>Audit: Append DECISION_CREATED
    DecisionSvc-->>UI: Decision outcome
```

## 6. Reject or Defer Recommendation

```mermaid
sequenceDiagram
    participant Committee
    participant DecisionAPI
    participant DecisionSvc
    participant RecommendationSvc
    participant DecisionRepo
    participant Audit

    Committee->>DecisionAPI: Reject or defer recommendation
    DecisionAPI->>DecisionSvc: Validate command
    DecisionSvc->>DecisionRepo: Append rejected/deferred decision
    DecisionSvc->>RecommendationSvc: Update recommendation status
    DecisionSvc->>Audit: Append DECISION_REJECTED_OR_DEFERRED
    DecisionSvc-->>Committee: Decision recorded
```

## 7. Execute Approved Trade

```mermaid
sequenceDiagram
    participant Operator
    participant ExecutionAPI
    participant DecisionSvc
    participant ExecutionSvc
    participant PortfolioSvc
    participant DecisionRepo
    participant Audit

    Operator->>ExecutionAPI: Mark execution update
    ExecutionAPI->>DecisionSvc: Fetch approved decision and trade refs
    ExecutionAPI->>ExecutionSvc: Validate execution state transition
    ExecutionSvc->>DecisionRepo: Append execution record
    ExecutionSvc->>PortfolioSvc: Create new portfolio snapshot link
    ExecutionSvc->>Audit: Append EXECUTION_RECORDED
    ExecutionSvc-->>Operator: Execution status projection
```

## 8. Review Thesis Using Monitoring Metrics

```mermaid
sequenceDiagram
    participant Analyst
    participant ReviewAPI
    participant MetricSvc
    participant ThesisSvc
    participant ReviewRepo
    participant Audit

    Analyst->>ReviewAPI: Trigger thesis review
    ReviewAPI->>MetricSvc: Fetch latest observations
    MetricSvc-->>ReviewAPI: Threshold evaluations
    ReviewAPI->>ThesisSvc: Create review outcome command
    ThesisSvc->>ReviewRepo: Append ThesisReview event
    ThesisSvc->>Audit: Append THESIS_REVIEW_RECORDED
    ThesisSvc-->>Analyst: Review outcome projection
```

## 9. Agent-Proposed Thesis Update With Human Approval

```mermaid
sequenceDiagram
    participant Agent
    participant AgentOrch as Agent Orchestrator
    participant ThesisAPI
    participant ThesisSvc
    participant Approval as Human Approval Service
    participant ThesisRepo
    participant Audit

    Agent->>AgentOrch: Propose thesis update payload
    AgentOrch->>ThesisAPI: Submit proposal as draft command
    ThesisAPI->>ThesisSvc: Validate deterministic rules
    ThesisSvc->>Approval: Require human approval
    Approval-->>ThesisSvc: Approved/Rejected
    alt Approved
      ThesisSvc->>ThesisRepo: Append new thesis version
      ThesisSvc->>Audit: Append THESIS_VERSION_CREATED_BY_AGENT_APPROVED
    else Rejected
      ThesisSvc->>Audit: Append THESIS_AGENT_PROPOSAL_REJECTED
    end
    ThesisSvc-->>AgentOrch: Result projection
```

## Control assertions
- Agents never write directly to repositories.
- Human approval gate is mandatory for state-changing agent proposals.
- All state changes are auditable append-only events.
