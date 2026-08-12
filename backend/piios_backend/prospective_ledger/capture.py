from __future__ import annotations

from datetime import datetime
import json
from typing import Any
from uuid import uuid4

from piios_backend.schemas.recommendation import PortfolioRecommendationResponse

from .models import ProspectiveDecisionRecord, canonical_hash, infer_market
from .store import ProspectiveLedgerStore


class ProspectiveLedgerCaptureService:
    def __init__(self, store: ProspectiveLedgerStore) -> None:
        self.store = store

    def capture_response(
        self,
        *,
        response: PortfolioRecommendationResponse,
        strategy_id: str,
        engine_version: str,
        git_commit_sha: str,
        config_version: str,
        universe_version: str,
    ) -> list[ProspectiveDecisionRecord]:
        self.store.init()
        rows = self._records_from_response(
            response=response,
            strategy_id=strategy_id,
            engine_version=engine_version,
            git_commit_sha=git_commit_sha,
            config_version=config_version,
            universe_version=universe_version,
        )
        self.store.append(rows)
        return rows

    def _records_from_response(
        self,
        *,
        response: PortfolioRecommendationResponse,
        strategy_id: str,
        engine_version: str,
        git_commit_sha: str,
        config_version: str,
        universe_version: str,
    ) -> list[ProspectiveDecisionRecord]:
        top_rank_by_ticker = {
            str(item.get("ticker")): item
            for item in (response.top_ranked_candidates or [])
            if item.get("ticker")
        }
        as_of_date = response.as_of_timestamp.split("T")[0] if "T" in response.as_of_timestamp else response.as_of_timestamp
        run_timestamp = datetime.utcnow().isoformat() + "Z"

        records: list[ProspectiveDecisionRecord] = []
        for rank, rec in enumerate(response.recommendations, start=1):
            ticker = rec.ticker
            top_rank = top_rank_by_ticker.get(ticker, {})
            components = {c.name.lower(): c for c in rec.components}

            quality_score = _safe_float_component(components.get("quality"))
            growth_score = _safe_float_component(components.get("growth"))
            valuation_score = _safe_float_component(components.get("valuation"))
            momentum_score = _safe_float_component(components.get("momentum"))
            risk_score = _safe_float_component(components.get("risk"))

            evidence_coverage = _extract_evidence_coverage(top_rank, rec.evidence)
            discovery_score = _safe_float(top_rank.get("discovery_score"))
            attractiveness_score = _safe_float(top_rank.get("security_attractiveness_score"))
            suitability_score = _safe_float(top_rank.get("portfolio_suitability_score"))

            market_snapshot = {
                "provider": rec.market_data_provider,
                "mode": rec.market_data_mode,
                "as_of": rec.market_data_as_of,
                "stale": rec.is_stale,
                "fallback_reason": rec.fallback_reason,
                "seeded_input": rec.seeded_input,
            }
            fundamental_snapshot = {
                "components": [item.model_dump() for item in rec.components],
                "evidence": [item.model_dump() for item in rec.evidence],
                "diagnostics": rec.diagnostics or {},
            }
            factor_payload = {
                "ticker": ticker,
                "quality_score": quality_score,
                "growth_score": growth_score,
                "valuation_score": valuation_score,
                "momentum_score": momentum_score,
                "risk_score": risk_score,
                "discovery_score": discovery_score,
                "attractiveness_score": attractiveness_score,
                "suitability_score": suitability_score,
                "combined_score": rec.score,
                "evidence_coverage": evidence_coverage,
                "confidence": rec.confidence,
                "action": rec.action,
                "ranking_position": rank,
            }

            market_hash = canonical_hash(market_snapshot)
            fundamental_hash = canonical_hash(fundamental_snapshot)
            factor_hash = canonical_hash(factor_payload)

            records.append(
                ProspectiveDecisionRecord(
                    decision_id=str(uuid4()),
                    strategy_id=strategy_id,
                    run_timestamp=run_timestamp,
                    as_of_date=as_of_date,
                    ticker=ticker,
                    market=infer_market(ticker),
                    ranking_position=rank,
                    action=rec.action,
                    proposed_allocation=rec.proposed_allocation,
                    quality_score=quality_score,
                    growth_score=growth_score,
                    valuation_score=valuation_score,
                    momentum_score=momentum_score,
                    risk_score=risk_score,
                    discovery_score=discovery_score,
                    attractiveness_score=attractiveness_score,
                    suitability_score=suitability_score,
                    combined_score=rec.score,
                    evidence_coverage=evidence_coverage,
                    confidence=rec.confidence,
                    reason_codes=sorted({item.code for item in rec.evidence}),
                    factor_trace_reference={"trace_keys": sorted((rec.diagnostics or {}).keys())},
                    engine_version=engine_version,
                    git_commit_sha=git_commit_sha,
                    config_version=config_version,
                    universe_version=universe_version,
                    market_provider=rec.market_data_provider,
                    fundamental_provider="yfinance",
                    market_source_retrieval_timestamp=rec.market_data_as_of,
                    fundamental_source_retrieval_timestamp=None,
                    market_snapshot_reference=market_snapshot,
                    fundamental_snapshot_reference=fundamental_snapshot,
                    market_snapshot_hash=market_hash,
                    fundamental_snapshot_hash=fundamental_hash,
                    factor_payload_hash=factor_hash,
                )
            )

        return records


def _safe_float_component(component: Any) -> float | None:
    if component is None:
        return None
    return _safe_float(getattr(component, "value", None))


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _extract_evidence_coverage(top_rank: dict[str, Any], evidence: list[Any]) -> float | None:
    top_coverage = _safe_float(top_rank.get("evidence_coverage"))
    if top_coverage is not None:
        return top_coverage
    for item in evidence:
        if str(getattr(item, "code", "")).upper() != "EVIDENCE_COVERAGE":
            continue
        detail = str(getattr(item, "detail", ""))
        try:
            return float(detail)
        except ValueError:
            continue
    return None
