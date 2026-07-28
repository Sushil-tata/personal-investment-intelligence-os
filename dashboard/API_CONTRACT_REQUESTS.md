# API Contract Requests — Frontend → Backend

This document turns every gap in `dashboard/API_GAPS.md` into a concrete, implementable contract:
endpoint, request shape, response DTO, required vs. optional fields, an example payload, and a
priority. It is written so a backend developer can implement each endpoint directly, without
needing to reverse-engineer intent from the frontend code.

Conventions used below:
- All endpoints are assumed under the existing `/api/v1` prefix.
- All response DTOs follow the existing house style: Pydantic `BaseModel`, explicit types, no
  implicit `Any`/`dict` unless the field is genuinely free-form.
- Priority: **P0** blocks a whole page from being useful; **P1** materially improves an existing
  page; **P2** is a future-ready nice-to-have explicitly called out as "future module" in the
  frontend brief.

---

## 1. Risk Metrics — P0

**Problem:** `GET /risk` returns only three static position-limit numbers. There is no real risk
analytics anywhere in the backend.

**Endpoint:** `GET /risk/metrics`

**Request:** no body; optional query params `portfolio_id: str | None`, `as_of: date | None`.

**Response DTO:**
```python
class RiskMetricsResponse(BaseModel):
    as_of: str
    volatility_annualized_pct: float
    beta_vs_benchmark: float
    benchmark_symbol: str
    max_drawdown_pct: float
    current_drawdown_pct: float
    var_95_1d_pct: float
    var_99_1d_pct: float
    expected_shortfall_95_pct: float
    correlation_matrix: dict[str, dict[str, float]]  # ticker -> ticker -> correlation
    marginal_contribution_to_risk: list[MCTRItem]
    component_contribution_to_risk: list[CCTRItem]

class MCTRItem(BaseModel):
    ticker: str
    mctr_pct: float

class CCTRItem(BaseModel):
    ticker: str
    cctr_pct: float
```

**Required fields:** `as_of`, `volatility_annualized_pct`, `max_drawdown_pct`, `var_95_1d_pct`.
**Optional fields:** `beta_vs_benchmark`/`benchmark_symbol` (omit if no benchmark configured),
`correlation_matrix`, `marginal_contribution_to_risk`, `component_contribution_to_risk`.

**Example payload:**
```json
{
  "as_of": "2026-07-28",
  "volatility_annualized_pct": 14.2,
  "beta_vs_benchmark": 1.08,
  "benchmark_symbol": "SPX",
  "max_drawdown_pct": -18.4,
  "current_drawdown_pct": -3.1,
  "var_95_1d_pct": -2.1,
  "var_99_1d_pct": -3.4,
  "expected_shortfall_95_pct": -2.9,
  "correlation_matrix": {"NVDA": {"AVGO": 0.62}},
  "marginal_contribution_to_risk": [{"ticker": "NVDA", "mctr_pct": 22.5}],
  "component_contribution_to_risk": [{"ticker": "NVDA", "cctr_pct": 19.8}]
}
```

**Also requested, separate endpoints:**
- `GET /risk/stress-tests` → `list[StressTestResult]` with `{scenario_name, description, portfolio_impact_pct, as_of}`.
- `GET /risk/liquidity` → `list[LiquidityItem]` with `{ticker, days_to_liquidate_estimate, adv_pct_of_position}`.
- `GET /risk/tracking-error` → `{benchmark_symbol, tracking_error_annualized_pct, as_of}`.

---

## 2. Decision Capture — P0

**Problem:** `PATCH /recommendations/{id}/status` only accepts a generic status enum and an
`approved_by` string. There is no distinct decision type, rationale, override reason, approved
position size, proposal-version linkage, or immutable history.

**Endpoint:** `POST /recommendations/{id}/decisions`

**Request DTO:**
```python
class DecisionCreateRequest(BaseModel):
    decision_type: DecisionType  # ACCEPT | PARTIALLY_ACCEPT | REJECT | DEFER | REQUEST_FURTHER_RESEARCH | OVERRIDE
    reviewer: str
    rationale: str
    override_reason: str | None = None       # required if decision_type == OVERRIDE
    approved_position_size: float | None = None  # required if ACCEPT or PARTIALLY_ACCEPT
    proposal_version: int
```

**Response DTO:**
```python
class DecisionResponse(BaseModel):
    decision_id: str
    recommendation_id: str
    proposal_version: int
    decision_type: str
    reviewer: str
    rationale: str
    override_reason: str | None
    approved_position_size: float | None
    decided_at: str
    is_immutable: bool = True
```

**New read endpoint:** `GET /recommendations/{id}/decisions` → `list[DecisionResponse]`, ordered
oldest-to-newest, append-only (no PUT/DELETE — a correction is a new decision record, never an
edit of a prior one).

**Required fields:** `decision_type`, `reviewer`, `rationale`, `proposal_version`.
**Optional fields:** `override_reason` (required only for `OVERRIDE`), `approved_position_size`
(required only for `ACCEPT`/`PARTIALLY_ACCEPT`).

**Example payload (request):**
```json
{
  "decision_type": "PARTIALLY_ACCEPT",
  "reviewer": "sushil",
  "rationale": "Agree with thesis but sizing down given existing sector concentration.",
  "approved_position_size": 1.5,
  "proposal_version": 1
}
```

**Priority:** P0 — this is the single highest-value gap; it blocks the Decisions page from being
more than a thin wrapper around a status field.

---

## 3. Recommendation Enrichment — P1

**Problem:** `Recommendation` lacks structured claims/evidence, a valuation summary, quantified
portfolio/risk impact, an uncertainties list, and traceability/replay status.

**Endpoint:** extend `GET /recommendations/{id}` (new single-item route) to include:
```python
class RecommendationDetailResponse(Recommendation):
    supporting_claims: list[ClaimResponse]
    valuation_summary: ValuationSummary | None
    portfolio_impact: PortfolioImpact | None
    risk_impact: RiskImpact | None
    uncertainties: list[str]
    traceability_status: TraceabilityStatus | None
    replay_verification_status: ReplayStatus | None
    proposal_version: int

class ClaimResponse(BaseModel):
    claim_id: str
    statement: str
    confidence_pct: float
    evidence_ids: list[str]

class ValuationSummary(BaseModel):
    method: str            # e.g. "DCF", "comparables"
    fair_value_estimate: float
    current_price: float
    upside_downside_pct: float

class PortfolioImpact(BaseModel):
    projected_weight_pct: float
    projected_bucket_weight_pct: float
    dollar_impact: float

class RiskImpact(BaseModel):
    marginal_var_contribution_pct: float
    marginal_beta_contribution: float

class TraceabilityStatus(BaseModel):
    trace_id: str
    is_complete: bool
    missing_links: list[str]

class ReplayStatus(BaseModel):
    result: str  # "PASS" | "FAIL" | "NOT_RUN"
    differences: list[str]
    replayed_at: str | None
```

**Required fields:** `proposal_version`. Everything else may be `null`/omitted if not yet computed
for a given recommendation — the frontend already renders "Awaiting backend support" for any
`null` section.

**Priority:** P1 (P0 for `proposal_version` alone, since Decisions depends on it).

---

## 4. Governance Backlog — P1

**Endpoint:** `GET /governance/backlog`

**Request:** optional query params `severity: str | None`, `status: str | None`,
`portfolio_id: str | None`, `instrument: str | None`, `since: date | None`.

**Response DTO:**
```python
class GovernanceBacklogItem(BaseModel):
    item_id: str
    item_type: str  # LOW_CONFIDENCE | REPLAY_MISMATCH | STALE_EVIDENCE | MISSING_DATA | POLICY_VIOLATION | OVERDUE_REVIEW | TRACEABILITY_GAP
    severity: str
    status: str
    portfolio_id: str | None
    instrument: str | None
    detail: str
    created_at: str
    due_at: str | None

class GovernanceBacklogResponse(BaseModel):
    items: list[GovernanceBacklogItem]
    total_count: int
```

**Example payload:**
```json
{"items": [{"item_id": "G1", "item_type": "STALE_EVIDENCE", "severity": "MEDIUM", "status": "OPEN",
  "portfolio_id": "P1", "instrument": "NVDA", "detail": "Evidence older than 30 days",
  "created_at": "2026-07-01T00:00:00Z", "due_at": "2026-08-01T00:00:00Z"}], "total_count": 1}
```

**Priority:** P1.

---

## 5. Rebalancing — Trade Tickets & Tax Impact — P1

**Endpoint:** `GET /portfolio/rebalance-proposal`

**Response DTO:**
```python
class ProposedTrade(BaseModel):
    ticker: str
    action: str  # BUY | SELL
    quantity: float
    estimated_price: float
    estimated_cash_impact: float
    estimated_tax_impact: float | None
    rationale: str

class RebalanceProposalResponse(BaseModel):
    generated_at: str
    trades: list[ProposedTrade]
    net_cash_impact: float
    net_estimated_tax_impact: float | None
    advisory_only: bool = True
```

**Priority:** P1. `estimated_tax_impact` is optional per-trade and may be `null` if no tax-lot data
is available yet — do not block the rest of the response on it.

---

## 6. Performance — P1

**Endpoint:** `GET /portfolio/performance`

**Request:** optional query params `start_date`, `end_date`, `benchmark_symbol`.

**Response DTO:**
```python
class AttributionItem(BaseModel):
    dimension: str  # asset_class | sector | geography | currency | security
    key: str
    contribution_pct: float

class PerformanceResponse(BaseModel):
    period_start: str
    period_end: str
    total_return_pct: float
    realized_return_pct: float
    unrealized_return_pct: float
    income_return_pct: float
    twr_pct: float
    xirr_pct: float
    benchmark_symbol: str | None
    benchmark_return_pct: float | None
    max_drawdown_pct: float
    attribution: list[AttributionItem]
```

**Priority:** P1 — currently zero coverage; this is the single biggest empty page in the app.

---

## 7. Portfolio Structure — Households / Accounts / Tax Lots — P2

**Endpoint:** `GET /portfolio/accounts`

**Response DTO:**
```python
class AccountResponse(BaseModel):
    account_id: str
    owner_member_id: str
    broker_custodian: str
    account_type: str  # e.g. TAXABLE, IRA, 401K
    cash_balance: float
    currency: str

class TaxLotResponse(BaseModel):
    lot_id: str
    account_id: str
    ticker: str
    quantity: float
    cost_basis_per_share: float
    acquired_at: str
```

Additional endpoints: `GET /portfolio/accounts/{id}/holdings`, `GET /portfolio/accounts/{id}/transactions`,
`GET /portfolio/accounts/{id}/tax-lots`.

**Priority:** P2 — needed for the deeper Holdings/Accounts hierarchy described in the Phase 1 brief.

---

## 8. Watchlist Segmentation — P2

**Endpoint:** extend `WatchlistIdea` with `watchlist_type: str` (`OWNED_POSITION | CANDIDATE |
EARNINGS | THESIS_RISK`) and `alert_status: str | None`. Backward compatible — existing consumers
that ignore the new fields are unaffected.

**Priority:** P2.

---

## 9. `/scores` and `/scores/explainability` typing — P2

**Problem:** both endpoints return untyped dicts with no `response_model`.

**Ask:** attach a real Pydantic `response_model` to both routes (whatever the current dict shape
already is, formalized), so the frontend can bind typed dataclasses instead of rendering raw JSON.

**Priority:** P2 — functional today, just untyped.

---

## Priority Summary

| # | Area | Priority |
|---|---|---|
| 1 | Risk metrics (volatility/VaR/ES/drawdown/beta/correlation/MCTR/CCTR/stress/liquidity/tracking error) | P0 |
| 2 | Decision capture (decision types, rationale, override, position size, immutable history) | P0 |
| 3 | Recommendation enrichment (claims, evidence, valuation, impact, traceability, replay, version) | P1 (P0 for `proposal_version`) |
| 4 | Governance backlog | P1 |
| 5 | Rebalancing trade tickets & tax impact | P1 |
| 6 | Performance (TWR/XIRR/attribution/benchmark/drawdown) | P1 |
| 7 | Accounts/households/tax lots | P2 |
| 8 | Watchlist segmentation | P2 |
| 9 | `/scores` typing | P2 |
