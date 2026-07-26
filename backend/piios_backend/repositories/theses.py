from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from piios_backend.models.entities import AuditLog, InvestmentThesisEntity
from piios_backend.schemas.enums import RecommendationStatus
from piios_backend.schemas.thesis import ThesisCreateRequest


class ThesisRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> list[InvestmentThesisEntity]:
        statement = select(InvestmentThesisEntity).order_by(InvestmentThesisEntity.created_at.desc())
        return list(self.session.exec(statement).all())

    def get(self, thesis_id: str) -> InvestmentThesisEntity | None:
        statement = select(InvestmentThesisEntity).where(InvestmentThesisEntity.thesis_id == thesis_id)
        return self.session.exec(statement).first()

    def exists(self, thesis_id: str) -> bool:
        statement = select(func.count()).select_from(InvestmentThesisEntity).where(InvestmentThesisEntity.thesis_id == thesis_id)
        return bool(self.session.exec(statement).one())

    def next_thesis_id(self) -> str:
        count_statement = select(func.count()).select_from(InvestmentThesisEntity)
        count = int(self.session.exec(count_statement).one())
        return f"t{count + 1}"

    def create(self, request: ThesisCreateRequest, thesis_id: str | None = None) -> InvestmentThesisEntity:
        entity = InvestmentThesisEntity(
            thesis_id=thesis_id or self.next_thesis_id(),
            ticker=request.ticker,
            asset_name=request.asset_name,
            theme=request.theme,
            bucket=request.bucket.value,
            thesis=request.thesis,
            bull_case=request.bull_case,
            bear_case=request.bear_case,
            why_now=request.why_now,
            why_not_now=request.why_not_now,
            invalidation_trigger=request.invalidation_trigger,
            valuation_notes=request.valuation_notes,
            expected_holding_period=request.expected_holding_period,
            source_documents=json.dumps(request.source_documents),
            confidence_score=request.confidence_score,
            status=RecommendationStatus.DRAFT,
            created_at=self._now(),
            updated_at=self._now(),
        )
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def update_status(self, thesis_id: str, status: RecommendationStatus) -> InvestmentThesisEntity | None:
        thesis = self.get(thesis_id)
        if thesis is None:
            return None
        thesis.status = status
        thesis.updated_at = self._now()
        self.session.add(thesis)
        self.session.commit()
        self.session.refresh(thesis)
        return thesis

    def seed_if_needed(self, request: ThesisCreateRequest, thesis_id: str) -> InvestmentThesisEntity:
        existing = self.get(thesis_id)
        if existing is not None:
            return existing
        return self.create(request, thesis_id=thesis_id)

    def log_audit(self, event_type: str, details: dict[str, object]) -> None:
        self.session.add(
            AuditLog(
                event_type=event_type,
                details=json.dumps(details, sort_keys=True),
                timestamp=self._now(),
            )
        )
        self.session.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
