# PIIOS Domain Model Blueprint

Date: 2026-07-26

## Core domain model

```mermaid
classDiagram
    class Company {
      company_id
      legal_name
      domicile_country
      issuer_type
      status
      effective_from_utc
      effective_to_utc
    }

    class Security {
      security_id
      company_id
      security_type
      class_rank
      voting_rights
      isin
      status
      effective_from_utc
      effective_to_utc
    }

    class ListingInstrument {
      listing_id
      security_id
      exchange_code
      local_ticker
      trading_currency
      listing_country
      lot_size
      mic
      active_from_utc
      active_to_utc
      price_source
    }

    class SecurityIdentifier {
      identifier_id
      listing_id
      id_type
      id_value
      source
      effective_from_utc
      effective_to_utc
    }

    class TickerHistory {
      ticker_history_id
      listing_id
      ticker
      status
      effective_from_utc
      effective_to_utc
    }

    class SecurityRelationship {
      relationship_id
      parent_security_id
      child_security_id
      relationship_type
      effective_from_utc
      effective_to_utc
    }

    class Portfolio {
      portfolio_id
      owner_id
      reporting_currency
      status
    }

    class Account {
      account_id
      portfolio_id
      provider
      account_currency
      status
    }

    class Holding {
      holding_id
      account_id
      listing_id
      quantity
      cost_basis
      status
    }

    class PortfolioSnapshot {
      snapshot_id
      portfolio_id
      as_of_utc
      source
      fx_snapshot_id
    }

    class InvestmentThesis {
      thesis_id
      company_id
      anchor_type
      current_version_id
      lifecycle_status
      closure_reason
      created_by
      created_at
    }

    class ThesisVersion {
      thesis_version_id
      thesis_id
      version_number
      thesis_type
      status
      horizon
      expected_return_low
      expected_return_high
      confidence
      authored_by
      created_at
    }

    class ThesisClaim {
      claim_id
      thesis_version_id
      claim_text
      claim_type
      materiality_weight
      expected_direction
      status
    }

    class Evidence {
      evidence_id
      source_id
      evidence_class
      support_direction
      summary
      extract
      credibility_score
      freshness_score
      verification_status
      created_at
    }

    class ResearchSource {
      source_id
      source_type
      publisher
      author
      publication_date
      retrieval_date
      filing_period
      url
      title
      source_version
      language
      jurisdiction
    }

    class MonitoringMetric {
      metric_id
      thesis_claim_id
      scope_type
      source_id
      expected_direction
      base_threshold
      warning_threshold
      break_threshold
      unit
      frequency
      weight
      metric_type
    }

    class MetricObservation {
      observation_id
      metric_id
      observed_value
      observed_at
      freshness
      qualitative_note
      evaluation_result
    }

    class ThesisReview {
      thesis_review_id
      thesis_id
      thesis_version_id
      review_outcome
      rationale
      reviewed_by
      reviewed_at
      next_review_at
    }

    class Recommendation {
      recommendation_id
      subject_type
      subject_id
      thesis_version_id
      recommendation_action
      valuation_summary
      expected_return
      confidence
      proposed_size
      risk_summary
      status
      expiry_at
      authored_by
      created_at
    }

    class InvestmentDecision {
      decision_id
      recommendation_id
      portfolio_snapshot_id
      decision_status
      final_instruction
      rationale
      approver_id
      approved_at
      execution_status
    }

    class ProposedTrade {
      proposed_trade_id
      decision_id
      listing_id
      side
      quantity
      target_weight
      constraint_context
      impact_summary
    }

    class Execution {
      execution_id
      proposed_trade_id
      execution_status
      executed_quantity
      executed_price
      executed_at
      broker_reference
    }

    class AuditEvent {
      audit_event_id
      entity_type
      entity_id
      event_type
      actor_type
      actor_id
      occurred_at
      payload
      immutable
    }

    class AgentRun {
      agent_run_id
      agent_name
      objective
      model_ref
      prompt_ref
      run_status
      started_at
      completed_at
    }

    class HumanApproval {
      approval_id
      target_entity_type
      target_entity_id
      decision
      approver_id
      rationale
      approved_at
    }

    Company "1" --> "*" Security
    Security "1" --> "*" ListingInstrument
    ListingInstrument "1" --> "*" SecurityIdentifier
    ListingInstrument "1" --> "*" TickerHistory
    Security "1" --> "*" SecurityRelationship
    Portfolio "1" --> "*" Account
    Account "1" --> "*" Holding
    ListingInstrument "1" --> "*" Holding
    Portfolio "1" --> "*" PortfolioSnapshot

    Company "1" --> "*" InvestmentThesis
    InvestmentThesis "1" --> "*" ThesisVersion
    ThesisVersion "1" --> "*" ThesisClaim
    ThesisClaim "1" --> "*" MonitoringMetric
    MonitoringMetric "1" --> "*" MetricObservation
    InvestmentThesis "1" --> "*" ThesisReview

    ResearchSource "1" --> "*" Evidence
    Evidence "*" --> "*" ThesisClaim
    Evidence "*" --> "*" ThesisVersion

    ThesisVersion "1" --> "*" Recommendation
    Recommendation "1" --> "*" InvestmentDecision
    InvestmentDecision "1" --> "*" ProposedTrade
    ProposedTrade "1" --> "*" Execution

    PortfolioSnapshot "1" --> "*" InvestmentDecision

    AgentRun "1" --> "*" AuditEvent
    HumanApproval "1" --> "*" AuditEvent
```

## Relationship rules

| Relationship | Cardinality | Ownership | Lifecycle dependency | Deletion behavior | Audit requirement |
|---|---|---|---|---|---|
| Company -> Security | 1 to many | Identity context | Security depends on company | Soft-delete company only after no active securities | Required |
| Security -> ListingInstrument | 1 to many | Identity context | Listing depends on security | Listing inactive effective-dated; no hard delete | Required |
| ListingInstrument -> Holding | 1 to many | Portfolio context reference | Holding references listing | Holdings immutable via snapshots; soft close position | Required |
| InvestmentThesis -> ThesisVersion | 1 to many | Thesis context | Version depends on thesis root | No hard delete of version | Required append-only |
| ThesisVersion -> ThesisClaim | 1 to many | Thesis context | Claim scoped to version | Claim may be superseded, not hard deleted | Required |
| ThesisClaim -> Evidence | many to many | Research + Thesis link | Evidence independent, links versioned | Do not hard delete evidence; revoke link via status | Required |
| ThesisVersion -> Recommendation | 1 to many | Recommendation context reference | Recommendation pinned to thesis version | No overwrite, supersede via status | Required |
| Recommendation -> InvestmentDecision | 1 to many | Decision context | Decision depends on recommendation | Rejected/deferred retained forever | Required |
| InvestmentDecision -> ProposedTrade | 1 to many | Decision context | Proposed trade depends on decision | Cancel via status, no hard delete | Required |
| ProposedTrade -> Execution | 1 to many | Decision/Execution context | Execution depends on proposed trade | Never hard delete executions | Required immutable |
| PortfolioSnapshot -> InvestmentDecision | 1 to many | Portfolio context reference | Decision evaluated on fixed snapshot | Snapshot immutable | Required |

## Immutability baseline
- Immutable append-only records:
  - ThesisVersion, ThesisReview, AuditEvent, Evidence, MetricObservation, InvestmentDecision, Execution.
- Mutable projections:
  - InvestmentThesis current status pointer, ListingInstrument active window, Recommendation status.
- Effective dating required:
  - Company, Security, ListingInstrument, SecurityIdentifier, TickerHistory, SecurityRelationship.
