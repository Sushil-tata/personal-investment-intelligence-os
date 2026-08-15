"""Single, dedicated API client layer for the PIIOS Streamlit frontend.

Every page must go through this module rather than calling ``requests``
directly, so that:

- the backend base URL is configured in exactly one place;
- errors (connection failures, timeouts, 4xx/5xx) are handled consistently
  and surfaced to the page as a typed result instead of an uncaught
  exception that crashes the whole app;
- response payloads are parsed into the typed models in ``lib.models``,
  so a field the backend renamed or removed fails loudly here rather than
  silently rendering as blank/missing further down in a page.

This module never fabricates data. If an endpoint does not exist, or a
response is missing a field a screen wants, that is an API gap — record it
in dashboard/API_GAPS.md and leave the screen honest about the absence,
per the frontend's advisory-only, no-parallel-engine mandate.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

import requests

from lib import models as m

API_BASE = os.getenv("PIIOS_API_BASE", "http://127.0.0.1:8000/api/v1")

T = TypeVar("T")


@dataclass
class ApiResult:
    """Outcome of a single API call, used by pages to render loading/
    error/empty/success states consistently (see lib.ui)."""

    ok: bool
    data: Any = None
    error: str | None = None
    status_code: int | None = None

    @property
    def is_empty(self) -> bool:
        if not self.ok:
            return False
        if self.data is None:
            return True
        if isinstance(self.data, (list, dict)):
            return len(self.data) == 0
        return False


def _request(method: str, path: str, **kwargs) -> ApiResult:
    url = f"{API_BASE}{path}"
    try:
        response = requests.request(method, url, timeout=20, **kwargs)
    except requests.exceptions.ConnectionError:
        return ApiResult(ok=False, error=f"Could not reach the PIIOS API at {API_BASE}. Is the backend running?")
    except requests.exceptions.Timeout:
        return ApiResult(ok=False, error=f"Request to {url} timed out after 20s.")
    except requests.exceptions.RequestException as exc:
        return ApiResult(ok=False, error=f"Request to {url} failed: {exc}")

    if response.status_code >= 400:
        detail = response.text
        try:
            detail = response.json().get("detail", detail)
        except ValueError:
            pass
        return ApiResult(ok=False, error=f"{response.status_code}: {detail}", status_code=response.status_code)

    try:
        payload = response.json() if response.content else None
    except ValueError:
        payload = response.text
    return ApiResult(ok=True, data=payload, status_code=response.status_code)


def get_json(path: str, params: dict | None = None) -> ApiResult:
    return _request("GET", path, params=params)


def patch_json(path: str, json_body: dict) -> ApiResult:
    return _request("PATCH", path, json=json_body)


def get(path: str):
    """Backward-compatible helper used by earlier pages. Raises on error
    (matches historical behaviour) rather than returning ApiResult, so
    existing pages built before the typed client keep working unchanged."""
    response = requests.get(f"{API_BASE}{path}", timeout=20)
    response.raise_for_status()
    return response.json()


def _map(result: ApiResult, fn: Callable[[Any], T]) -> ApiResult:
    if not result.ok:
        return result
    try:
        return ApiResult(ok=True, data=fn(result.data), status_code=result.status_code)
    except (KeyError, TypeError, AttributeError, IndexError) as exc:
        return ApiResult(ok=False, error=f"Unexpected response shape from backend: {exc}")


def _holding(d: dict) -> m.Holding:
    return m.Holding(
        holding_id=d["holding_id"], ticker=d["ticker"], name=d["name"], quantity=d["quantity"],
        market_value=d["market_value"], bucket=d.get("bucket"), geography=d.get("geography", "Global"),
        currency=d.get("currency", "USD"), asset_class=d.get("asset_class", "Equity"),
        sector=d.get("sector", "Multi-Sector"), theme=d.get("theme", "Core"),
    )


def _snapshot(d: dict) -> m.PortfolioSnapshot:
    return m.PortfolioSnapshot(
        snapshot_id=d["snapshot_id"], owner=d["owner"], total_value=d["total_value"],
        holdings=[_holding(h) for h in d["holdings"]],
    )


def _drift_item(d: dict) -> m.DriftItem:
    return m.DriftItem(**{k: d[k] for k in (
        "dimension", "key", "target_percentage", "actual_percentage", "drift_amount",
        "drift_percentage", "severity", "recommended_action", "advisory_only")})


def _recommendation(d: dict) -> m.Recommendation:
    return m.Recommendation(**{k: d.get(k) for k in (
        "recommendation_id", "ticker", "thesis_id", "bucket", "portfolio_bucket", "bull_case", "bear_case",
        "why_now", "why_not_now", "thesis_invalidation_trigger", "position_size_suggestion", "time_horizon",
        "confidence_score", "portfolio_fit_score", "data_freshness_timestamp", "source_documents",
        "source_links", "rationale", "data_source", "model_version", "status", "created_at", "updated_at",
        "approved_by", "advisory_only")})


def _top_recommendation(d: dict) -> m.TopRecommendation:
    return m.TopRecommendation(**{k: d[k] for k in (
        "ticker", "sector", "score", "daily_pct", "weekly_pct", "close", "volume_ratio", "recommended_action")})


def _cross_market_candidate(d: dict) -> m.CrossMarketCandidate:
    allowed = set(m.CrossMarketCandidate.__dataclass_fields__.keys())
    return m.CrossMarketCandidate(**{k: v for k, v in d.items() if k in allowed})


def _universe_summary(d: dict) -> m.UniverseSummary:
    return m.UniverseSummary(
        markets=d.get("markets", {}),
        total_candidates=d.get("total_candidates", 0),
        eligible_candidates=d.get("eligible_candidates", 0),
        partial_candidates=d.get("partial_candidates", 0),
        ineligible_candidates=d.get("ineligible_candidates", 0),
    )


def _data_quality_summary(d: dict) -> m.DataQualitySummary:
    return m.DataQualitySummary(
        providers=list(d.get("providers", [])),
        latest_timestamps=d.get("latest_timestamps", {}),
        missing_inputs=list(d.get("missing_inputs", [])),
        excluded_securities=list(d.get("excluded_securities", [])),
        portfolio_total_mismatch=bool(d.get("portfolio_total_mismatch", False)),
        portfolio_total_source=d.get("portfolio_total_source"),
        portfolio_total_authoritative=d.get("portfolio_total_authoritative"),
        market_retrieval_stats=d.get("market_retrieval_stats"),
        fx_availability=d.get("fx_availability"),
    )


def _sensitivity_summary(d: dict) -> m.SensitivitySummary:
    return m.SensitivitySummary(
        classification=d.get("classification", "UNKNOWN"),
        scenarios=list(d.get("scenarios", [])),
        top_candidates_stable=bool(d.get("top_candidates_stable", False)),
    )


def _tactical_signal(d: dict) -> m.TacticalSignal:
    return m.TacticalSignal(**{k: d.get(k) for k in (
        "signal_id", "ticker", "bucket", "status", "entry_zone", "invalidation", "target", "advisory_only")})


def _thesis(d: dict) -> m.InvestmentThesis:
    return m.InvestmentThesis(**{k: d[k] for k in (
        "thesis_id", "ticker", "asset_name", "theme", "bucket", "thesis", "bull_case", "bear_case", "why_now",
        "why_not_now", "invalidation_trigger", "valuation_notes", "expected_holding_period", "source_documents",
        "confidence_score", "status", "created_at", "updated_at")})


def _resolution_issue(d: dict) -> m.ResolutionIssueResponse:
    return m.ResolutionIssueResponse(**{k: d.get(k) for k in (
        "issue_id", "source_record_type", "source_record_id", "reason", "candidates", "recommended_resolution",
        "owner_decision", "reviewer", "reviewed_at", "notes", "resulting_mapping_id", "status", "created_at")})


# --- Portfolio -------------------------------------------------------------

def get_portfolio() -> ApiResult:
    return _map(get_json("/portfolio"), lambda d: [_snapshot(s) for s in d])


def get_portfolio_targets() -> ApiResult:
    return _map(get_json("/portfolio/targets"), lambda d: m.PortfolioTargetsResponse(**d))


def get_portfolio_drift() -> ApiResult:
    return _map(get_json("/portfolio/drift"), lambda d: m.PortfolioDriftResponse(
        generated_at=d["generated_at"], items=[_drift_item(i) for i in d["items"]]))


def get_holdings() -> ApiResult:
    return _map(get_json("/holdings"), lambda d: [_holding(h) for h in d])


def get_watchlist() -> ApiResult:
    return _map(get_json("/watchlist"), lambda d: [
        m.WatchlistIdea(watchlist_id=w["watchlist_id"], ticker=w["ticker"], note=w["note"], bucket=w.get("bucket"))
        for w in d])


# --- Portfolio layers (household / net worth / allocation / exposure) -----

def get_family_portfolios() -> ApiResult:
    return _map(get_json("/family/portfolios"), lambda d: m.FamilyPortfolioResponse(
        households=[m.FamilyPortfolioMember(**h) for h in d["households"]]))


def get_net_worth() -> ApiResult:
    return _map(get_json("/portfolio/net-worth"), lambda d: m.NetWorthResponse(
        owner=d["owner"], total_assets=d["total_assets"], total_liabilities=d["total_liabilities"],
        net_worth=d["net_worth"], breakdown=[m.NetWorthItem(**b) for b in d["breakdown"]]))


def get_allocation(dimension: str = "asset_class") -> ApiResult:
    """dimension must be one of: asset_class, sector, theme, bucket, geography
    (the only values the backend's PortfolioLayersService.allocation() accepts;
    anything else silently falls back to asset_class server-side)."""
    return _map(get_json("/portfolio/allocation", params={"dimension": dimension}), lambda d: m.AllocationResponse(
        total_value=d["total_value"], items=[m.AllocationItem(**i) for i in d["items"]]))


def get_currency_exposure() -> ApiResult:
    return _map(get_json("/portfolio/currency-exposure"), lambda d: m.CurrencyExposureResponse(
        total_value=d["total_value"], items=[m.CurrencyExposureItem(**i) for i in d["items"]]))


def get_ips_constraints() -> ApiResult:
    return _map(get_json("/ips/constraints"), lambda d: m.IPSConstraintResponse(
        constraints=[m.IPSConstraint(**c) for c in d["constraints"]]))


def get_instrument_master() -> ApiResult:
    return _map(get_json("/instruments"), lambda d: m.InstrumentMasterResponse(
        instruments=[m.InstrumentMasterItem(**i) for i in d["instruments"]]))


def get_data_trust_hierarchy() -> ApiResult:
    return _map(get_json("/data-trust/hierarchy"), lambda d: m.DataTrustHierarchyResponse(
        hierarchy=[m.DataTrustSourceItem(**s) for s in d["hierarchy"]]))


# --- Recommendations / decisions -------------------------------------------

def get_recommendations() -> ApiResult:
    return _map(get_json("/recommendations"), lambda d: [_recommendation(r) for r in d])


def get_recommendation_queue() -> ApiResult:
    return _map(get_json("/recommendations/queue"), lambda d: [_recommendation(r) for r in d["items"]])


def get_top_recommendations(limit: int = 50, sector: str | None = None, market: str | None = None) -> ApiResult:
    params = {"limit": limit}
    if sector:
        params["sector"] = sector
    if market:
        params["market"] = market
    return _map(get_json("/recommendations/top", params=params), lambda d: [_top_recommendation(r) for r in d])


def update_recommendation_status(recommendation_id: str, status: str, approved_by: str | None = None) -> ApiResult:
    body = {"status": status, "approved_by": approved_by}
    return _map(patch_json(f"/recommendations/{recommendation_id}/status", body), _recommendation)


def get_tactical_signals() -> ApiResult:
    return _map(get_json("/tactical-signals"), lambda d: [_tactical_signal(s) for s in d])


def generate_investment_recommendation(
    investable_amount: float = 5000.0,
    market_data_mode: str = "auto",
    use_demo_portfolio: bool = True,
    portfolio_snapshot_id: str | None = None,
    as_of_date: str | None = None,
    base_currency: str = "USD",
    eligible_markets: list[str] | None = None,
    mandate_override: dict | None = None,
) -> ApiResult:
    mode = (market_data_mode or "").strip().lower()
    use_demo_endpoint = use_demo_portfolio or mode == "development_seed"

    body = {
        "portfolio_snapshot_id": portfolio_snapshot_id,
        "investable_amount": investable_amount,
        "as_of_date": as_of_date,
        "market_data_mode": market_data_mode,
        "use_demo_portfolio": use_demo_portfolio,
        "base_currency": base_currency,
        "eligible_markets": eligible_markets,
        "mandate_override": mandate_override,
    }

    def _parse(d):
        universe_summary = d.get("universe_summary")
        screening_summary = d.get("screening_summary")
        screening = None
        if screening_summary:
            screening = m.ScreeningSummary(
                eligible_by_market=screening_summary.get("eligible_by_market", {}),
                partial_by_market=screening_summary.get("partial_by_market", {}),
                ineligible_by_market=screening_summary.get("ineligible_by_market", {}),
                excluded_reasons=list(screening_summary.get("excluded_reasons", [])),
                discovery_size_counts=screening_summary.get("discovery_size_counts"),
                discovery_status_counts=screening_summary.get("discovery_status_counts"),
            )
        portfolio_before = d.get("portfolio_before")
        portfolio_after = d.get("portfolio_after")
        data_quality_summary = d.get("data_quality_summary")
        sensitivity = d.get("sensitivity")

        return m.PortfolioRecommendationResponse(
            recommendation_id=d["recommendation_id"],
            status=d["status"],
            as_of_timestamp=d["as_of_timestamp"],
            market_data_provider=d["market_data_provider"],
            market_data_mode=d["market_data_mode"],
            input_freshness=d["input_freshness"],
            investable_amount=d["investable_amount"],
            allocation_total=d["allocation_total"],
            allocation_difference=d["allocation_difference"],
            overall_confidence=d["overall_confidence"],
            advisory_only=d.get("advisory_only", True),
            portfolio_observations=[m.PortfolioObservation(**o) for o in d["portfolio_observations"]],
            recommendations=[
                m.AllocationRecommendation(
                    action=row["action"],
                    ticker=row["ticker"],
                    instrument_name=row["instrument_name"],
                    portfolio_role=row["portfolio_role"],
                    current_value=row["current_value"],
                    current_weight=row["current_weight"],
                    proposed_allocation=row["proposed_allocation"],
                    proposed_total_value=row["proposed_total_value"],
                    post_weight=row["post_weight"],
                    score=row["score"],
                    confidence=row["confidence"],
                    market_data_provider=row["market_data_provider"],
                    market_data_mode=row["market_data_mode"],
                    market_data_as_of=row.get("market_data_as_of"),
                    is_stale=row.get("is_stale", False),
                    fallback_reason=row.get("fallback_reason"),
                    seeded_input=row.get("seeded_input", False),
                    rationale=row["rationale"],
                    diversification_contribution=row["diversification_contribution"],
                    risks=list(row.get("risks", [])),
                    unavailable_inputs=list(row.get("unavailable_inputs", [])),
                    conditions_to_change=list(row.get("conditions_to_change", [])),
                    components=[m.RecommendationScoreComponent(**c) for c in row.get("components", [])],
                    evidence=[m.RecommendationEvidence(**e) for e in row.get("evidence", [])],
                )
                for row in d["recommendations"]
            ],
            universe_summary=_universe_summary(universe_summary) if universe_summary else None,
            screening_summary=screening,
            top_ranked_candidates=[_cross_market_candidate(row) for row in d.get("top_ranked_candidates", [])],
            actionable_recommendations=list(d.get("actionable_recommendations", [])),
            existing_holding_actions=list(d.get("existing_holding_actions", [])),
            portfolio_before=m.PortfolioExposureSummary(**portfolio_before) if portfolio_before else None,
            portfolio_after=m.PortfolioExposureSummary(**portfolio_after) if portfolio_after else None,
            residual_cash=d.get("residual_cash"),
            data_quality_summary=_data_quality_summary(data_quality_summary) if data_quality_summary else None,
            sensitivity=_sensitivity_summary(sensitivity) if sensitivity else None,
            assumptions=list(d.get("assumptions", [])),
            limitations=[m.RecommendationLimitation(**l) for l in d.get("limitations", [])],
        )

    path = "/recommendations/demo" if use_demo_endpoint else "/recommendations/generate"
    request_kwargs = {} if use_demo_endpoint else {"json": body}
    return _map(_request("POST", path, **request_kwargs), _parse)


# --- Risk / governance / research ------------------------------------------

def get_risk_limits() -> ApiResult:
    """The /risk endpoint currently returns only three static position-limit
    numbers (see dashboard/API_GAPS.md) — no volatility, drawdown, beta,
    correlation, VaR, ES or stress-test data exists on this branch."""
    return get_json("/risk")


def get_resolution_issues(limit: int = 100) -> ApiResult:
    return _map(get_json("/identity/resolution-issues", params={"limit": limit}),
                lambda d: [_resolution_issue(i) for i in d])


def get_shadow_diagnostics() -> ApiResult:
    return _map(get_json("/identity/shadow/diagnostics"), lambda d: m.ShadowIdentityDiagnosticsResponse(
        enabled=d["enabled"], checked_records=d["checked_records"], unresolved_records=d["unresolved_records"],
        items=[m.ShadowIdentityCheckItem(**i) for i in d["items"]]))


def get_research_feed() -> ApiResult:
    return _map(get_json("/research"), lambda d: m.ResearchFeedResponse(
        items=[m.ResearchDocumentResponse(**i) for i in d["items"]]))


def get_journal() -> ApiResult:
    return _map(get_json("/journal"), lambda d: [m.JournalEntry(**e) for e in d])


def get_theses() -> ApiResult:
    return _map(get_json("/theses"), lambda d: [_thesis(t) for t in d])


def update_thesis_status(thesis_id: str, status: str) -> ApiResult:
    return _map(patch_json(f"/theses/{thesis_id}/status", {"status": status}), _thesis)


def get_scores() -> ApiResult:
    """Untyped: the backend returns a bare dict built by a live-feeds
    service with no response_model / schema, so no field contract exists
    to bind a dataclass to yet (see dashboard/API_GAPS.md)."""
    return get_json("/scores")


def get_score_explainability(limit: int = 25, sector: str | None = None) -> ApiResult:
    params = {"limit": limit}
    if sector:
        params["sector"] = sector
    return get_json("/scores/explainability", params=params)


def get_health() -> ApiResult:
    return _map(get_json("/health"), lambda d: m.HealthResponse(**d))


# --- Wave 2B decision-contracts (live) --------------------------------------
# Endpoints per piios/docs/WAVE2B_M5_FRONTEND_CONTRACT.md and
# backend/piios_backend/api/routes/decision_contracts.py. There is currently
# no list/discovery endpoint for proposals or proposal versions anywhere in
# the backend — every read below requires an already-known ID. See
# dashboard/FRONTEND_INTEGRATION_NOTES.md.

def _diagnostic_check(d: dict) -> m.DiagnosticCheck:
    required = {k: d[k] for k in ("code", "status", "severity", "message", "related_entity_type")}
    optional = {k: d.get(k) for k in ("related_entity_id", "remediation_hint")}
    return m.DiagnosticCheck(**required, **optional)


# Required vs. optional fields below follow
# piios/docs/WAVE2B_M5_FRONTEND_CONTRACT.md's "Required vs Optional Fields"
# section exactly. Required fields use direct indexing (`d["x"]`) so a
# malformed/incomplete payload raises KeyError -> a friendly ApiResult error
# via _map(); optional fields use `.get()` since a missing key is valid.

def _decision_detail(d: dict) -> m.DecisionDetail:
    required = {k: d[k] for k in ("decision_id", "proposal_version_id", "state", "decision_meaning",
                                   "reason_code", "decided_at")}
    optional = {k: d.get(k) for k in (
        "reason_text", "decided_by", "preferred_alternative_target_key", "modified_action",
        "modified_action_note", "modified_action_min_weight", "modified_action_max_weight",
        "modified_position_min_weight", "modified_position_max_weight")}
    return m.DecisionDetail(**required, **optional)


def get_proposal(proposal_id: str) -> ApiResult:
    def _parse(d):
        required = {k: d[k] for k in ("proposal_id", "target_type", "target_key", "scope", "status",
                                       "created_at", "updated_at")}
        return m.RecommendationProposalDetail(**required, advisory_only=d.get("advisory_only", True))
    return _map(get_json(f"/decision-contracts/proposals/{proposal_id}"), _parse)


def get_proposal_version(proposal_version_id: str) -> ApiResult:
    def _parse(d):
        required = {k: d[k] for k in (
            "proposal_version_id", "proposal_id", "version_number", "status", "created_at", "snapshot_id",
            "action", "authoritative_confidence", "priority_level", "priority_score", "required_human_review")}
        optional = {k: d.get(k) for k in ("action_note", "action_min_weight", "action_max_weight",
                                           "supersedes_version_id")}
        return m.RecommendationProposalVersionDetail(**required, **optional, advisory_only=d.get("advisory_only", True))
    return _map(get_json(f"/decision-contracts/proposal-versions/{proposal_version_id}"), _parse)


def list_decisions_for_proposal_version(proposal_version_id: str) -> ApiResult:
    return _map(get_json(f"/decision-contracts/proposal-versions/{proposal_version_id}/decisions"),
                lambda d: [_decision_detail(row) for row in d])


def get_latest_decision_for_proposal_version(proposal_version_id: str) -> ApiResult:
    def _parse(d):
        return _decision_detail(d) if d is not None else None
    return _map(get_json(f"/decision-contracts/proposal-versions/{proposal_version_id}/decisions/latest"), _parse)


def get_traceability_diagnostic(proposal_version_id: str) -> ApiResult:
    return _map(get_json(f"/decision-contracts/proposal-versions/{proposal_version_id}/diagnostics/traceability"),
                lambda d: m.TraceabilityDiagnostic(
                    proposal_version_id=d["proposal_version_id"], proposal_id=d.get("proposal_id"),
                    overall_status=d["overall_status"], checks=[_diagnostic_check(c) for c in d["checks"]],
                    diagnostic_codes=list(d["diagnostic_codes"]), severity=d["severity"],
                    generated_at=d["generated_at"], advisory_only=d.get("advisory_only", True)))


def get_confidence_diagnostic(proposal_version_id: str) -> ApiResult:
    return _map(get_json(f"/decision-contracts/proposal-versions/{proposal_version_id}/diagnostics/confidence"),
                lambda d: m.ConfidenceDiagnostic(
                    proposal_version_id=d["proposal_version_id"],
                    authoritative_confidence=d.get("authoritative_confidence"),
                    components=[m.ConfidenceComponent(**c) for c in d["components"]],
                    limitations=list(d["limitations"]), generated_at=d["generated_at"],
                    advisory_only=d.get("advisory_only", True)))


def get_decision_lineage_diagnostic(decision_id: str) -> ApiResult:
    return _map(get_json(f"/decision-contracts/decisions/{decision_id}/diagnostics/lineage"),
                lambda d: m.DecisionLineageDiagnostic(
                    decision_id=d["decision_id"], proposal_id=d.get("proposal_id"),
                    proposal_version_id=d["proposal_version_id"], decision_state=d["decision_state"],
                    decision_meaning=d["decision_meaning"], overall_status=d["overall_status"],
                    checks=[_diagnostic_check(c) for c in d["checks"]], diagnostic_codes=list(d["diagnostic_codes"]),
                    severity=d["severity"], generated_at=d["generated_at"], advisory_only=d.get("advisory_only", True)))


def get_governance_backlog(proposal_version_id: str) -> ApiResult:
    return _map(get_json(f"/decision-contracts/proposal-versions/{proposal_version_id}/governance-backlog"),
                lambda d: m.GovernanceReviewBacklog(
                    proposal_version_id=d["proposal_version_id"],
                    items=[m.GovernanceReviewItem(**{k: it.get(k) for k in (
                        "review_item_id", "proposal_id", "proposal_version_id", "decision_id", "reason_code",
                        "severity", "status", "created_at", "source_diagnostic", "summary")}) for it in d["items"]],
                    generated_at=d["generated_at"], advisory_only=d.get("advisory_only", True)))


def capture_decision(
    proposal_version_id: str,
    decision_type: str,
    reviewer: str,
    reason_code: str | None = None,
    reason_text: str | None = None,
    preferred_alternative_target_key: str | None = None,
    modified_action: str | None = None,
    modified_action_note: str | None = None,
    modified_action_min_weight: float | None = None,
    modified_action_max_weight: float | None = None,
    modified_position_min_weight: float | None = None,
    modified_position_max_weight: float | None = None,
    client_request_id: str | None = None,
) -> ApiResult:
    """POST /decision-contracts/decisions/capture. Idempotent: an identical
    repeat request (same client_request_id and payload) returns the existing
    decision rather than creating a duplicate — see WAVE2B_M5_FRONTEND_CONTRACT.md."""
    body = {
        "proposal_version_id": proposal_version_id,
        "decision_type": decision_type,
        "reviewer": reviewer,
        "reason_code": reason_code,
        "reason_text": reason_text,
        "preferred_alternative_target_key": preferred_alternative_target_key,
        "modified_action": modified_action,
        "modified_action_note": modified_action_note,
        "modified_action_min_weight": modified_action_min_weight,
        "modified_action_max_weight": modified_action_max_weight,
        "modified_position_min_weight": modified_position_min_weight,
        "modified_position_max_weight": modified_position_max_weight,
        "client_request_id": client_request_id,
    }
    return _map(_request("POST", "/decision-contracts/decisions/capture", json=body), _decision_detail)
