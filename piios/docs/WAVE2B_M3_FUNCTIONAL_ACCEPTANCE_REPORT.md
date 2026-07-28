# Wave 2B M3 Functional Acceptance Report

## Executive Summary
Status: Accepted with Minor Limitations

Decision:
- The Recommendation Decision Intelligence Engine is functionally correct, deterministic, auditable, replayable, idempotent, and production-ready for Milestone 4 scope.
- No Milestone 3 functional defect requiring code change was identified in this validation run.

Minor limitations:
- In-memory repositories are non-transactional test doubles (`rollback()` is a no-op), so atomic rollback evidence is established on SQLModel/PostgreSQL repositories only.
- Portfolio intelligence remains signal-based (not optimization/risk-budgeting), which is expected for Milestone 3.

---

## Part 1 — Repository Baseline
Validation timestamp: 2026-07-27

Repository root:
- `/Users/sushilkumar/Documents/GitHub/personal-investment-intelligence-os`

Active branch:
- `wave-2b-decision-intelligence`

Latest commit (HEAD at baseline capture):
- `e0ad237 docs: record setup and packaging hygiene debt`

Working tree state at baseline capture:
- `git status -sb` showed one untracked doc from prior task:
- `?? piios/docs/adr/ADR-019-Milestone3-Architecture-Alignment.md`

Recent log snapshot (`git log --oneline --decorate -10`):
- `e0ad237` docs: record setup and packaging hygiene debt
- `2225fcc` piios-reproducible-test-gate
- `9c1e38e` wave-2b-m3-atomic-persistence
- `08d0cfd` wave-2b-m3-idempotency
- `8fc23b5` wave-2b-m3-determinism-hardening
- `63892dc` wave-2b-m3-strategy-governance
- `56e5363` wave-2b-test-isolation-fix
- `75403ec` wave-2b-m3-deterministic-decision-engine
- `bc46945` wave-2b-m2-persistence
- `34076a2` wave-2b-m1-domain-contracts

Python version:
- `Python 3.11.14`

Virtual environment:
- `/Users/sushilkumar/Documents/GitHub/personal-investment-intelligence-os/.venv`

PostgreSQL connection used:
- `postgresql+psycopg://piios:piios@localhost:5432/piios_db`

Current migration revision (`alembic current`):
- `0008_wave2b_m2_sqlmodel_persist (head)`

---

## Part 2 — End-to-End Functional Flow (Implementation-Based)
Actual execution path in `RecommendationDecisionEngine.generate_recommendation`:

Input
-> `RecommendationEngineInput` (proposal + thesis health + claims + evidence + interpretations + portfolio context + strategy key)

Validation
-> Dataclass invariants (`RecommendationEngineInput`, `PortfolioContextSnapshot`, component score bounds)
-> Failure behavior: raises `ValueError` for malformed inputs (e.g., blank proposal ID)

Scoring Components
-> `default_scoring_components()` produces 8 independent component scores (health, confidence, evidence quality, freshness, contradiction penalty, portfolio alignment, risk penalty, opportunity bonus)
-> Output: bounded `ComponentScore` list
-> Failure behavior: malformed metadata safely degrades evidence quality score to default path

Strategy
-> `_resolve_strategy` requires known strategy key
-> `WeightedRecommendationStrategy.evaluate` computes normalized contributions, weighted sum, action, review flag, priority, applied rules
-> Failure behavior: unknown strategy key raises `ValueError`; negative configured weight raises `ValueError`

Composite Score
-> `StrategyResult.overall_score` + ordered `component_breakdown`

Recommendation / Priority / Confidence
-> Action mapping via thresholds and portfolio state (`BUY/ADD/HOLD/REDUCE/SELL/WATCH/NO_ACTION`)
-> Priority from score distance and review flag
-> Confidence from confidence dimensions minus contradiction/risk penalties

Explanation
-> `_build_explanation` emits drivers + warnings from component contributions and penalty thresholds
-> Output is structured object, not free text

Canonical Trace
-> `_canonical_trace_payload` builds normalized JSON payload with sorted deterministic content
-> Includes strategy governance (`strategy_key`, `strategy_profile`, `strategy_hash`)
-> `input_hash = sha256(canonical_payload_json)`

Persistence
-> Transaction boundary in `generate_recommendation`:
  - create/get proposal
  - idempotency lookup by `input_hash`
  - create proposal version
  - create input snapshot
  - create reasons
  - create claim links
  - create evidence links
  - commit
-> Failure behavior: any exception triggers rollback and re-raise

Recommendation Proposal result
-> Returns `RecommendationGenerationResult` with proposal, proposal version, snapshot, reasons, trace links, and evaluation

---

## Part 3 — Functional Acceptance Scenarios
All scenarios executed on both repository implementations:
- In-memory repositories
- SQLModel/PostgreSQL repositories

### Scenario A — Strong Buy
Expected:
- high score, buy/add recommendation, strong confidence, positive drivers, deterministic hash, full persistence

Actual:
- action: `BUY`
- overall score: `0.909867`
- confidence: `0.767028`
- priority: `HIGH`
- reasons: `7`
- claim links: `1`
- evidence links: `2`
- deterministic hash stable across repositories
- persisted successfully

Result: PASS

### Scenario B — Strong Sell
Expected:
- very low score, sell recommendation, warnings and review gate, deterministic trace

Actual:
- action: `SELL`
- overall score: `0.1938`
- confidence: `0.0`
- priority: `URGENT`
- required human review: `true`
- warnings include contradiction and risk
- persisted successfully

Result: PASS

### Scenario C — Mixed Evidence
Input pattern:
- strong quality, weaker valuation context, mixed support/contradiction

Actual:
- action: `ADD`
- overall score: `0.625933`
- confidence: `0.447639`
- warning includes contradiction signal
- explanation drivers align with high-quality/support factors

Result: PASS (conflict handling present through penalties and warnings)

### Scenario D — Missing Evidence
Input pattern:
- one evidence source removed

Actual:
- action: `ADD`
- overall score: `0.643467`
- confidence: `0.514028`
- evidence links reduced to `1`
- deterministic replay/hash remained stable for identical input

Result: PASS

### Scenario E — Stale Evidence
Input pattern:
- stale thesis-health freshness (`0.05`)

Actual:
- action: `HOLD`
- overall score: `0.548867`
- confidence: `0.474028`
- stale handling visible via reduced freshness contribution and overall confidence

Result: PASS

### Scenario F — Boundary Conditions
Validated balanced strategy boundaries with exact and near-threshold scores:
- score `0.0` -> `SELL`, review true
- score `0.3` -> `WATCH`, review true
- score `0.46` -> `HOLD`
- score `0.62` -> `ADD`
- score `0.76` -> `ADD`
- score `1.0` -> `ADD`

Malformed input test:
- blank proposal ID raised: `ValueError: proposal_id must not be empty`

Result: PASS

### Scenario G — Portfolio Context
Portfolio-aware behavior exists and was validated with identical thesis/evidence but different context:
- concentrated/low-cash context:
  - action `ADD`, score `0.7256`, confidence `0.5095`, review true
- diversified/high-cash context:
  - action `BUY`, score `0.85`, confidence `0.714167`, review false

Result: PASS (recommendation changes with portfolio context)

---

## Part 4 — Determinism
Repeated identical requests produced identical:
- component-derived score
- action
- confidence
- explanation content
- canonical payload and SHA-256 hash

Evidence:
- `deterministic_repeat_equal: true`

Result: PASS

---

## Part 5 — Idempotency
Identical repeated submission behavior:
- no duplicate proposal version created
- existing recommendation reused by input-hash match

Evidence:
- `idempotent_same_version: true`
- `idempotent_version_count: 1`

Material input change behavior:
- changed evidence quality produced new hash and new proposal version
- original version unchanged

Evidence:
- `material_change_new_hash: true`
- `material_change_new_version: 2`
- `original_version_stable: true`

Result: PASS

---

## Part 6 — Atomicity
Injected persistence failure at reason-save stage (after proposal/version/snapshot staging):
- injected error: `injected failure`
- post-failure DB counts for proposal/version/snapshot by proposal ID: all `0`
- retry with normal repositories succeeded (`proposal:ATOMIC:...:v1`)

Result: PASS

---

## Part 7 — Explanation Quality
Checks performed across scenarios:
- explanation drivers and warnings derive from computed component contributions and penalty thresholds
- no invented evidence references (claim/evidence links persisted from actual input IDs)
- positive/negative signals properly separated:
  - drivers from high contributions
  - warnings from penalty conditions
- confidence and recommendation are distinct fields and remain stable in replay

Result: PASS

---

## Part 8 — Strategy Governance
Validated:
- strategy key and full strategy profile included in canonical trace
- strategy specification hash included in canonical trace

Hash sensitivity checks:
- weight change -> hash changed: `true`
- threshold change -> hash changed: `true`
- ordering-only change -> hash unchanged: `true`

Result: PASS

---

## Part 9 — Repository Parity
Identical business outcomes observed between In-memory and PostgreSQL for scenarios A-E:
- action parity: all equal
- overall score parity: all equal
- priority parity: all equal
- required_human_review parity: all equal

Result: PASS

---

## Part 10 — Performance Sanity (Observed)
PostgreSQL-backed observations (no optimization work performed):
- single recommendation end-to-end latency: `9.463 ms`
- persistence latency estimate: `9.275 ms`
- 100 recommendation batch total latency: `444.162 ms`
- 100 recommendation average latency: `4.442 ms`

Observation:
- Current performance is comfortably within expected synchronous service-range for this stage.

---

## Behaviour Trace (Concrete Example)
Scenario B (Strong Sell) trace summary:
1. Input accepted with high contradiction/risk and weak health/freshness/quality.
2. Components compute bounded values in [0,1].
3. Strategy applies weighted normalization and thresholds.
4. Composite score `0.1938` maps to `SELL` with required review.
5. Explanation includes contradiction + risk warnings.
6. Canonical payload generated and hashed (`9198225c...`).
7. Proposal/version/snapshot/reasons/links persisted atomically.
8. Result returned with stable hash and structured explanation.

---

## Functional Limitations

### Milestone 3 defects
- None identified in this validation run.

### Milestone 4 enhancements (non-defect)
- Add explicit RunMode field (Live/Simulation/Replay/Backtest) to persisted artifacts.
- Add explicit policy/version identity field in persisted recommendation artifacts (strategy hash already exists in trace).
- Add persisted replay corpus tests as permanent acceptance gate.

### Wave 3 architecture items (non-defect)
- First-class `EvidenceSet` aggregate.
- First-class `ScoringRun` aggregate.
- First-class `ScoringPolicyVersion` aggregate.
- Advanced Bayesian/graph/multi-agent strategy families.

---

## Final Recommendation
Milestone 4 may begin.

Answer to decision question:
- Yes. The current Recommendation Decision Intelligence Engine can be trusted to produce correct, reproducible, and auditable recommendations for pre-Portfolio-Intelligence progression, with no blocking functional defects found in this validation cycle.
