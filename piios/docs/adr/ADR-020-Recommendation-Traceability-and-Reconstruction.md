# ADR-020: Recommendation Traceability and Reconstruction

## Status
Accepted

## Date
2026-07-28

## Context
Wave 2B Milestone 3 delivered deterministic recommendation generation, persistence parity, idempotency, and atomic rollback guarantees. Milestone 4 requires auditable recommendation lineage reconstruction without storing hidden chain-of-thought or unconstrained free-form model reasoning.

The system must reconstruct, from persisted structured records, what input was used, what policy and strategy versions were applied, how components evaluated, what proposal was produced, and how human decisioning resolved the proposal.

## Decision
Adopt a structured traceability model within the existing decision-contracts boundary:

1. Add immutable RecommendationTrace aggregate and ordered TraceEntry records.
2. Persist rule outcomes using structured RuleEvaluation objects with explicit rule versions.
3. Persist deterministic component references using ComponentResultReference objects.
4. Store trace and proposal artifacts atomically in the same persistence boundary.
5. Keep Proposal and InvestmentDecision as separate append-only records.
6. Add RecommendationReconstructionService to reconstruct lineage by proposal version, trace ID, or investment decision ID.
7. Add deterministic RecommendationExplanation projection derived only from persisted proposal + trace records.
8. Explicitly reject hidden chain-of-thought storage and generative narrative explanations.

## Why Structured Traces
- Auditability requires deterministic, reviewable facts.
- Replayability requires stable execution identity and schema versioning.
- Governance requires explicit rule identifiers, thresholds, and outcomes.
- Safety requires bounded, testable fields rather than opaque metadata blobs.

## Aggregate Boundary
RecommendationTrace is the authoritative execution record for a single proposal version and execution identity.

Boundary constraints:
- one authoritative trace per proposal version;
- one authoritative trace per execution identity;
- strictly increasing deterministic sequence ordering of entries;
- completed authoritative traces are append-only and immutable;
- failed traces cannot be authoritative.

## Snapshot and Versioning Strategy
- Input state remains anchored by RecommendationInputSnapshot and deterministic input hash.
- Trace includes engine_name, engine_version, policy_version, strategy_version, and trace_schema_version.
- RuleEvaluation includes rule_id + rule_version for stable policy provenance.

## Atomic Persistence Boundary
Decision engine orchestration persists:
- proposal,
- proposal version,
- input snapshot,
- reasons,
- claim/evidence links,
- recommendation trace + entries,
in a single commit boundary via repository protocols.

Failure anywhere rolls back the entire bundle.

## Reconstruction Model
RecommendationReconstructionService reconstructs lineage:
- by proposal_version_id,
- by trace_id,
- by decision_id.

It verifies:
- schema support,
- trace completion state,
- contiguous ordered entries,
- action/priority parity between trace and proposal.

Errors are explicit and typed (missing trace, incomplete trace, integrity mismatch, unsupported schema version, etc).

## Explanation Projection Approach
RecommendationExplanation is a deterministic projection, not a generated narrative.

Projection rules:
- derive only from persisted structured records;
- stable ordering by persisted rank/sequence;
- explicit truncation of supporting/limiting reasons;
- include reason codes and source references;
- no recomputation of recommendation logic;
- no inferred unsupported claims.

A compact summary string is deterministic and template-based.

## Rejected Alternatives
- Storing free-form model internal reasoning text.
- Recomputing explanations by re-running strategy logic at read time.
- Combining proposal and decision into one mutable record.
- Event-bus or distributed tracing expansion in Milestone 4.

## Known Limitations
- Trace payload currently stores some structured subfields as JSON text columns for proportionate schema complexity.
- In-memory repositories remain non-transactional test doubles (rollback semantic coverage is authoritative on PostgreSQL).

## Future Extension Points
- Additional rule severity tiers and policy registries.
- Richer execution consideration and monitoring-trigger reference taxonomies.
- Dedicated read-model storage tuned for large-scale reporting queries.
