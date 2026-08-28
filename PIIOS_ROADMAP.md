# PIIOS AUTHORITATIVE ROADMAP — REMEMBER AND DO NOT DRIFT

*This is the current master roadmap for PIIOS. Do not add new stages, factors, infrastructure, challengers, or side-projects unless explicitly approved by Sushil. This document remains authoritative until explicitly replaced.*

## CURRENTLY COMPLETE

- Core recommendation engine: Quality, Growth, Valuation, Momentum, Risk, Discovery, evidence/confidence, actions, ranking
- India / US / Singapore coverage
- Stage A1 price/risk PIT validation
- Historical PIT fundamentals investigation closed
- Prospective immutable decision ledger READY
- Stage C prospective competition framework READY

## THREE LAYERS — DO NOT MIX

### Layer 1 — REAL PERSONAL PORTFOLIO
Actual capital. Continues according to the investor's own allocation decisions — broad index exposure, existing holdings, cash. PIIOS development does not force this capital to sit idle. PIIOS may be used as research input / decision support / opportunity-ranking input for this layer at any time, but its experimental strategies must not be represented as validated alpha until evidence exists.

### Layer 2 — PIIOS SHADOW COMPETITION (D1-D4 + six-month freeze)
Governed by the immutable prospective ledger. **Starts now.** Paper/shadow capital — all contestants receive identical hypothetical capital and contribution timing. No requirement to put real money into every contestant. This is the layer that governs model development and the Case A-H decisions below. The six-month freeze applies to this layer's methodology, not to the investor's real portfolio.

### Layer 3 — EXPERIMENTAL REAL-MONEY COMPETITION
Deferred until Tier-1 (shadow competition) evidence exists. May later include LLM sleeves, human discretionary, additional factor strategies, professional active-fund challengers. Not cancelled — gated on evidence.

## REMAINING CORE BUILD — ONLY 4 STAGES (Layer 2)

### D1 — Mechanical Challenger League
- Freeze PIIOS_CORE_V1
- Add 52W_HIGH_V1
- Add PH_PH_MH_RS_V1 = Price High × Profit High × Momentum High × Relative Strength
  - Value = gate/risk modifier
  - Quality = gate/trust modifier
  - Risk = sizing modifier
- Compare against NIFTY50_V1, an appropriate broader India benchmark such as NIFTY500 (see benchmark note below), and CASH_V1
- No extra challenger zoo

**PIIOS_CORE_V1 is absolutely frozen for the duration of the shadow competition.** It is the fixed benchmark the other contestants are measured against — it must never be moved mid-competition. Any RS-enhanced or otherwise methodology-modified Core (including the D2 relative-strength addition) is a new registered strategy, `PIIOS_CORE_V2`, run alongside V1, not a silent update to it.

**NIFTY500 implementation note:** Stage C currently has NIFTY50_V1 via NIFTYBEES.NS. Codex must not invent a NIFTY500 proxy at implementation time — it must identify and document a defensible representation, explicitly distinguishing the **benchmark index series** used for performance comparison from the **investable ETF/fund proxy** used when transaction-level investability is required. If the ETF proxy has material tracking error or insufficient history/liquidity, the index and the investable proxy must not be treated as identical — report both separately, don't collapse them into one number.

### D2 — Relative Strength / Stock-vs-Index Intelligence
- 3m / 6m / 12m stock excess return vs index
- stock vs sector
- stock vs peers where feasible
- explicitly answer: why own the stock instead of the benchmark?
- Do not overwrite PIIOS_CORE_V1 — any later Core change becomes PIIOS_CORE_V2

### D3 — Exit / Reduce / Replace Intelligence
- ADD / HOLD / REDUCE / EXIT
- reason-coded triggers: fundamental deterioration, profit-high deterioration, momentum breakdown, relative-strength breakdown, valuation excess, thesis violation, portfolio risk
- REPLACE only once opportunity comparison and portfolio constraints are available

### D4 — Portfolio Guardrails + Incremental Capital Allocation
- max stock weight, sector cap, liquidity floor, cash allowed, simple concentration controls
- answer where the next INR/USD should go: existing holding / new stock / index / cash
- no sophisticated optimizer yet

## HARD FINISH LINE

After D4: CORE BUILD ENDS (Layer 2) → enter LIVE_VALIDATION_MODE → freeze Layer 2 feature development for 6 months. This freeze applies to PIIOS methodology only — it does not freeze the investor's real portfolio (Layer 1).

During freeze: no new factors, no reweighting due to performance, no retrospective edits, no new challengers mid-period unless predeclared, only critical defect/data fixes.

## CHECKPOINTS (Layer 2 shadow competition)

- 3 months: sanity check only — implementation-defect scan, not an investment conclusion
- 6 months: first evidence-guided *decision*, not a strategy conclusion. Enough to identify obvious weaknesses and authorize a maximum of one major intervention (per Case A-H) — not enough to conclude that a medium/long-horizon strategy has durable alpha. Treat any six-month result as directional, not final.
- 12 months: meaningful simplify/continue decision
- 18-24 months: multibagger conversion evidence becomes interpretable

## PHASED REAL-MONEY GATING (Layer 3 — when experimental capital may enter the challenger league)

**PHASE 1 — now through D4:** paper/shadow competition only. Real passive/core investing continues separately (Layer 1). No real-money LLM challenger league.

**PHASE 2 — during the six-month freeze, starting after the 3-month sanity checkpoint:** a small, predeclared experimental-capital sleeve may begin — see rationale and safeguards below. Continue the immutable shadow competition throughout.

**PHASE 3 — after the 6-month evidence review:** only strategies that survive the first evidence review become eligible for meaningful real-capital allocation.

**PHASE 4 — 12 months+:** consider whether broader real-money competition is justified. Only then revisit LLM challengers, human discretionary sleeve, additional factor strategies, professional active-fund challengers.

### Recommended gate: start the small experimental sleeve after the 3-month sanity checkpoint, not immediately after D4 and not only after the full 6-month freeze.

Rationale across the four dimensions requested:

- **Learning value:** Real money teaches two things paper cannot — actual execution mechanics (order routing, cross-market currency handling, real vs. modeled costs) and whether the investor actually follows REDUCE/EXIT signals when real money is on the line rather than overriding them emotionally. Both are operational/behavioral, not statistical — the shadow ledger already uses real market prices, so it produces identical *strategy* evidence to real money. There is no learning-value argument for waiting the full 6 months, since the thing real money teaches has nothing to do with which strategy wins.
- **Risk:** This project has repeatedly shipped real defects that passed an initial review round (a tautological audit check, fabricated hash-based returns, hardcoded benchmark constants) and only surfaced under independent re-verification. Committing real capital — even small — before a dedicated defect-scan checkpoint repeats that exact failure pattern with money attached. Starting immediately after D4 is too risky for a system with zero live-operation hours. The 3-month checkpoint exists specifically to catch this class of defect before capital follows.
- **Behavioral contamination:** This is the strongest argument against early or careless entry. If a real-money sleeve tracks the same strategies feeding the 6-month Case A-H governance decision, the investor risks unconsciously favoring the sleeve holding real capital when interpreting evidence (loss aversion, sunk cost, motivated reasoning) — e.g. discounting a losing paper result for a strategy that happens to be "winning" with real money attached, or the reverse. Guard against this explicitly: **the experimental sleeve's real-money performance is not evidence for any Case A-H decision — only the shadow/paper ledger counts as competition evidence.** The pilot sleeve should mirror only the **investable subset** of the shadow contestant set, proportionally (same relative weights, same timing) — not the full set, since some shadow contestants may be non-investable constructs (e.g. a benchmark index series rather than its ETF proxy). This still removes the temptation to selectively back a favorite, without forcing money into something that can't actually be bought. The full shadow competition — investable and non-investable contestants alike — remains the sole evidence source for Case A-H decisions regardless of what the pilot sleeve can or can't hold.
- **Statistical usefulness:** None, either way — real money adds zero incremental statistical power over the shadow ledger, since both are now priced identically off real market data. This removes any statistical argument for waiting past the defect-scan checkpoint, and confirms the entire justification for Phase 2 is operational/behavioral learning, not evidence quality.

## COMPETITION GOVERNS DEVELOPMENT (Layer 2 evidence only — see contamination guard above)

- 52W_HIGH beats Core → question complexity / trend treatment
- PH_PH_MH_RS beats 52W_HIGH → fundamental-high + RS adds value
- PH_PH_MH_RS beats Core → consider simplifying/replacing Core
- good picks but poor exits → improve exit engine
- good picks but poor portfolio return → improve allocator
- sector-relative strategy dominates → consider sector intelligence
- index dominates → consider index-core + active-satellite, or simplify PIIOS

## NO PREDEFINED D5

D5 exists only if real competition evidence identifies a specific weakness worth solving.

## DEFER UNTIL EVIDENCE JUSTIFIES

More historical PIT reconstruction, ecosystem/dependency graph, news/catalyst engine, scenario/Monte Carlo engine, options engine, trading engine, LLM challenger sleeves, mutual-fund challenger zoo, sophisticated portfolio optimization, major dashboard expansion.

## THE EARLIER 8-SLEEVE REAL-MONEY IDEA

Placed in DEFERRED / TIER-3 EXPERIMENT (Layer 3). Not cancelled permanently — eligible only after Layer 2 (Tier-1 mechanical) competition has produced enough evidence to justify the added complexity. Principle: first PIIOS vs. simple rules vs. index vs. cash; later PIIOS vs. LLMs / humans / funds.

## MULTIBAGGER

Not a separate strategy yet. Treated initially as an extension/research label on PH_PH_MH_RS candidates using: persistent profit highs, reinvestment runway, ROIC, market-share gains, operating leverage, balance-sheet resilience, TAM/structural runway.

## ROLE DISCIPLINE

**Claude:** challenge methodology, review economic rationale, detect overengineering, propose simpler alternatives. Does not expand the roadmap independently.

**Codex:** implements only approved stage scope, writes deterministic tests, produces prospective proof. Does not invent new methodology or stages.

## GOVERNING RULE

No major capability is built unless: (1) competition evidence, (2) real portfolio use, or (3) a clearly identified investment decision gap shows why it is needed. If a much simpler strategy performs as well or better, simplify. "PIIOS is not yet validated" does not imply "the investor must stop investing" — the freeze stops methodology changes, not Layer 1 capital deployment.
