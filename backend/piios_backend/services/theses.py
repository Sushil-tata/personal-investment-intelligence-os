from __future__ import annotations

import json

from fastapi import HTTPException
from sqlmodel import Session

from piios_backend.core.config import settings
from piios_backend.repositories.theses import ThesisRepository
from piios_backend.schemas.enums import RecommendationStatus
from piios_backend.schemas.thesis import InvestmentThesis, ThesisCreateRequest


class ThesisService:
    def __init__(self, session: Session) -> None:
        self.repository = ThesisRepository(session)

    def list_theses(self) -> list[InvestmentThesis]:
        return [self._to_schema(item) for item in self.repository.list()]

    def get_thesis(self, thesis_id: str) -> InvestmentThesis:
        thesis = self.repository.get(thesis_id)
        if thesis is None:
            raise HTTPException(status_code=404, detail="thesis_id not found")
        return self._to_schema(thesis)

    def create_thesis(self, request: ThesisCreateRequest) -> InvestmentThesis:
        thesis = self.repository.create(request)
        self.repository.log_audit(
            "THESIS_CREATED",
            {"thesis_id": thesis.thesis_id, "ticker": thesis.ticker, "status": thesis.status.value},
        )
        return self._to_schema(thesis)

    def update_thesis_status(self, thesis_id: str, status: RecommendationStatus) -> InvestmentThesis:
        thesis = self.repository.update_status(thesis_id, status)
        if thesis is None:
            raise HTTPException(status_code=404, detail="thesis_id not found")
        self.repository.log_audit(
            "THESIS_STATUS_CHANGED",
            {"thesis_id": thesis.thesis_id, "ticker": thesis.ticker, "status": thesis.status.value},
        )
        return self._to_schema(thesis)

    def export_csv_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for thesis in self.repository.list():
            rows.append(
                {
                    "thesis_id": thesis.thesis_id,
                    "ticker": thesis.ticker,
                    "asset_name": thesis.asset_name,
                    "theme": thesis.theme,
                    "bucket": thesis.bucket,
                    "thesis": thesis.thesis,
                    "bull_case": thesis.bull_case,
                    "bear_case": thesis.bear_case,
                    "why_now": thesis.why_now,
                    "why_not_now": thesis.why_not_now,
                    "invalidation_trigger": thesis.invalidation_trigger,
                    "valuation_notes": thesis.valuation_notes,
                    "expected_holding_period": thesis.expected_holding_period,
                    "source_documents": thesis.source_documents,
                    "confidence_score": thesis.confidence_score,
                    "status": thesis.status.value,
                    "created_at": thesis.created_at,
                    "updated_at": thesis.updated_at,
                }
            )
        return rows

    def seed_canonical_thesis(self) -> None:
        seed = ThesisCreateRequest(
            ticker="NVDA",
            asset_name="NVIDIA",
            theme="AI Infrastructure",
            bucket="Strategic Alpha",
            thesis="Core AI compute enabler with durable demand tailwinds.",
            bull_case="Scale advantage and software ecosystem support premium pricing.",
            bear_case="Valuation and cyclical semiconductor demand shocks.",
            why_now="Visibility on demand and product cycle remains favorable.",
            why_not_now="Positioning is crowded and can mean-revert quickly.",
            invalidation_trigger="Multi-quarter margin contraction and loss of data-center momentum.",
            valuation_notes="Premium multiple requires growth delivery.",
            expected_holding_period="2-5 years",
            source_documents=["rd1"],
            confidence_score=76,
        )
        self.repository.seed_if_needed(seed, thesis_id="t1")

    def _to_schema(self, thesis) -> InvestmentThesis:
        return InvestmentThesis(
            thesis_id=thesis.thesis_id,
            ticker=thesis.ticker,
            asset_name=thesis.asset_name,
            theme=thesis.theme,
            bucket=thesis.bucket,
            thesis=thesis.thesis,
            bull_case=thesis.bull_case,
            bear_case=thesis.bear_case,
            why_now=thesis.why_now,
            why_not_now=thesis.why_not_now,
            invalidation_trigger=thesis.invalidation_trigger,
            valuation_notes=thesis.valuation_notes,
            expected_holding_period=thesis.expected_holding_period,
            source_documents=json.loads(thesis.source_documents),
            confidence_score=thesis.confidence_score,
            status=thesis.status,
            created_at=thesis.created_at,
            updated_at=thesis.updated_at,
        )
