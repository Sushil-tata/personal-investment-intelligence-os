from __future__ import annotations

import json

from fastapi import HTTPException
from sqlmodel import Session

from piios.thesis.application.commands import UpdateThesisStatusCommand
from piios.thesis.application.queries import GetThesisQuery, ListThesesQuery
from piios.thesis.application.services import ThesisApplicationService
from piios.thesis.domain.enums import ThesisStatus
from piios.thesis.domain.exceptions import ThesisNotFoundError
from piios.thesis.infrastructure.sqlmodel_repositories import SQLModelThesisRootRepository, SQLModelThesisVersionRepository
from piios_backend.repositories.theses import ThesisRepository
from piios_backend.schemas.enums import RecommendationStatus
from piios_backend.schemas.thesis import InvestmentThesis, ThesisCreateRequest
from piios_backend.services.thesis_compatibility import (
    create_command_from_request,
    project_latest_to_legacy_schema,
    thesis_status_from_legacy,
)


class ThesisService:
    def __init__(self, session: Session) -> None:
        self.repository = ThesisRepository(session)
        self.versioned = ThesisApplicationService(
            root_repository=SQLModelThesisRootRepository(session),
            version_repository=SQLModelThesisVersionRepository(session),
        )

    def list_theses(self) -> list[InvestmentThesis]:
        items = self.versioned.list_theses(ListThesesQuery(include_archived=True))
        return [project_latest_to_legacy_schema(item) for item in items]

    def get_thesis(self, thesis_id: str) -> InvestmentThesis:
        try:
            item = self.versioned.get_thesis(GetThesisQuery(thesis_id=thesis_id))
        except ThesisNotFoundError:
            legacy = self.repository.get(thesis_id)
            if legacy is None:
                raise HTTPException(status_code=404, detail="thesis_id not found")
            self._sync_missing_versioned_thesis(legacy)
            item = self.versioned.get_thesis(GetThesisQuery(thesis_id=thesis_id))
        return project_latest_to_legacy_schema(item)

    def create_thesis(self, request: ThesisCreateRequest) -> InvestmentThesis:
        legacy = self.repository.create(request)
        command = create_command_from_request(request, thesis_id=legacy.thesis_id)
        created = self.versioned.create_thesis(command)
        self.repository.log_audit(
            "THESIS_CREATED",
            {"thesis_id": legacy.thesis_id, "ticker": legacy.ticker, "status": created.status.value},
        )
        return project_latest_to_legacy_schema(created)

    def update_thesis_status(self, thesis_id: str, status: RecommendationStatus) -> InvestmentThesis:
        legacy = self.repository.update_status(thesis_id, status)
        if legacy is None:
            raise HTTPException(status_code=404, detail="thesis_id not found")

        target_status = thesis_status_from_legacy(status.value)
        try:
            updated = self._advance_status_to_target(thesis_id, target_status)
        except ThesisNotFoundError:
            self._sync_missing_versioned_thesis(legacy)
            updated = self._advance_status_to_target(thesis_id, target_status)

        self.repository.log_audit(
            "THESIS_STATUS_CHANGED",
            {"thesis_id": thesis_id, "ticker": legacy.ticker, "status": updated.status.value},
        )
        return project_latest_to_legacy_schema(updated)

    def export_csv_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for thesis in self.list_theses():
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
        legacy = self.repository.seed_if_needed(seed, thesis_id="t1")
        self._sync_missing_versioned_thesis(legacy)

    def _sync_missing_versioned_thesis(self, legacy_thesis) -> None:
        try:
            self.versioned.get_thesis(GetThesisQuery(thesis_id=legacy_thesis.thesis_id))
            return
        except ThesisNotFoundError:
            pass

        request = ThesisCreateRequest(
            ticker=legacy_thesis.ticker,
            asset_name=legacy_thesis.asset_name,
            theme=legacy_thesis.theme,
            bucket=legacy_thesis.bucket,
            thesis=legacy_thesis.thesis,
            bull_case=legacy_thesis.bull_case,
            bear_case=legacy_thesis.bear_case,
            why_now=legacy_thesis.why_now,
            why_not_now=legacy_thesis.why_not_now,
            invalidation_trigger=legacy_thesis.invalidation_trigger,
            valuation_notes=legacy_thesis.valuation_notes,
            expected_holding_period=legacy_thesis.expected_holding_period,
            source_documents=json.loads(legacy_thesis.source_documents),
            confidence_score=legacy_thesis.confidence_score,
        )
        created = self.versioned.create_thesis(create_command_from_request(request, thesis_id=legacy_thesis.thesis_id))

        legacy_status = thesis_status_from_legacy(legacy_thesis.status.value)
        self._advance_status_to_target(legacy_thesis.thesis_id, legacy_status)

    def _advance_status_to_target(self, thesis_id: str, target: ThesisStatus):
        status_order = [
            ThesisStatus.DRAFT,
            ThesisStatus.RESEARCHED,
            ThesisStatus.RISK_CHECKED,
            ThesisStatus.PENDING_REVIEW,
            ThesisStatus.APPROVED,
            ThesisStatus.ARCHIVED,
        ]
        current = self.versioned.get_thesis(GetThesisQuery(thesis_id=thesis_id)).status
        current_idx = status_order.index(current)
        target_idx = status_order.index(target)
        if target_idx < current_idx:
            raise HTTPException(status_code=400, detail="cannot move thesis status backward")

        latest = self.versioned.get_thesis(GetThesisQuery(thesis_id=thesis_id))
        if current_idx == target_idx:
            return latest

        for step in status_order[current_idx + 1 : target_idx + 1]:
            latest = self.versioned.update_status(UpdateThesisStatusCommand(thesis_id=thesis_id, status=step))
        return latest
