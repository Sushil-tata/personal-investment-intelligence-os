# ADR-0008: Milestone 3 Architecture Alignment

## Status
Accepted

## Date
2026-07-27

## Context
An independent Wave 2B Milestone 3 architecture review was performed without original implementation artifacts and explicitly used a reconstructed baseline (likely monolithic scoring engine) as a critique anchor. The repository now contains completed Milestones 1-3 plus recovery/hardening work, including deterministic trace hashing, strategy governance hashing, idempotency by deterministic input hash, atomic persistence boundaries, and reproducible test gates.

This ADR records the objective alignment decision against actual implementation and defines the governing architecture inputs for Milestone 4 while preserving Milestones 1-3 stability and backward compatibility.

## Decision
Adopt a selective alignment approach:
- Keep current Milestone 3 architecture foundations that are already strong.
- Implement only low-risk additive improvements during Milestone 4.
- Defer larger aggregate-model expansions and advanced reasoning patterns to Wave 3.
- Reject over-engineering and redesign recommendations that would reduce delivery velocity without proportional governance benefit.

Milestones 1-3 are not redesigned by this ADR.

## Accepted Recommendations (Implement/Keep)

### A1. Keep deterministic, replayable scoring design
Rationale:
- Already implemented with canonical payload, normalized serialization, and stable SHA-256 hash.
- Required for governance and auditability.

### A2. Keep independent scoring components and pluggable strategy profile pattern
Rationale:
- Already implemented with component-level contracts and strategy selection.
- Preserves clean separation and future extension points.

### A3. Keep strategy governance traceability
Rationale:
- Already implemented with strategy key, profile, and governance hash in trace payload.
- Supports policy provenance without immediate heavy redesign.

### A4. Keep idempotency by deterministic input hash
Rationale:
- Already implemented and tested.
- Prevents duplicate version creation for equivalent deterministic inputs.

### A5. Keep atomic persistence boundary
Rationale:
- Already implemented via transactional uncommitted writes and commit/rollback boundary.
- Directly improves consistency and audit integrity.

### A6. Milestone 4 additive improvements (accepted for near-term implementation)
Rationale:
- Low-risk and backward compatible; improve governance without aggregate rewrite.

Accepted Milestone 4 improvements:
- Add RunMode (Live/Simulation/Replay/Backtest) to recommendation generation artifacts.
- Add explicit policy identity/version metadata alongside current strategy governance hash.
- Refine internal Score/Decide/Explain/Persist phase boundaries without changing external contracts.
- Add explanation schema versioning for evolution-safe rendering.
- Add persisted replay test harness based on stored deterministic snapshots.
- Add explicit missing-evidence status markers in structured trace outputs.

## Deferred Recommendations

### D1. Defer to Milestone 4
- Centralized explicit normalization stage abstraction (if done additively, without behavior break).
- Structured evidence-status policy expression for missing/stale/low-confidence evidence.
- Optional component-parallel execution if performance evidence justifies it.

Rationale:
- Useful but not blocking given current deterministic behavior.
- Can be introduced with limited refactor and no domain-model break.

### D2. Defer to Wave 3
- First-class immutable EvidenceSet aggregate and repository.
- First-class immutable ScoringPolicyVersion aggregate and lifecycle.
- First-class append-only ScoringRun aggregate.
- Independent RecommendationExplanation aggregate/read model.
- Bayesian strategy implementation.
- Graph reasoning and evidence graph model.
- Multi-agent orchestration and workflow-engine adoption.
- Advanced policy/rules engine or DSL.

Rationale:
- Valuable architecture expansions, but materially larger scope.
- Not required to safely proceed with Milestone 4.
- Should be introduced deliberately with explicit migration planning.

## Rejected Recommendations

### R1. Reject immediate significant redesign of Milestone 3
Rationale:
- Actual implementation is materially stronger than the reconstructed baseline assumed by the external review.
- Determinism, governance traceability, idempotency, and atomic persistence are already present.
- Full redesign now would introduce avoidable schedule risk and churn.

### R2. Reject immediate workflow-engine adoption
Rationale:
- Current use case remains synchronous and deterministic.
- Durable distributed orchestration is premature at this stage.

### R3. Reject immediate Bayesian/policy-engine-first replacement
Rationale:
- Current weighted + rule-threshold strategy is explainable and testable.
- Advanced strategy families should remain behind existing extension points until concrete need and data maturity are proven.

## Consequences

### Positive
- Preserves implementation stability and delivery velocity.
- Strengthens governance incrementally where benefit is highest.
- Avoids over-engineering while keeping forward compatibility.

### Trade-offs
- Some desirable aggregate purity is deferred.
- Long-term architectural expansion remains planned work for Wave 3.

## Milestone 4 Governance Role
This ADR is the governing architecture input for Milestone 4:
- Mandatory: preserve deterministic and replayable behavior.
- Mandatory: preserve backward compatibility of completed Milestones 1-3.
- Mandatory: no unnecessary new aggregate/repository proliferation.
- Preferred: additive improvements only unless a change is explicitly approved as structural.

## Alternatives Considered
- Full redesign before Milestone 4: rejected.
- No changes at all: rejected.
- Selective additive alignment (this ADR): accepted.

## Review Notes
The independent review remains valuable expert guidance. Its strongest recommendations are incorporated as accepted/deferred decisions here, adjusted to actual implementation reality and risk profile.