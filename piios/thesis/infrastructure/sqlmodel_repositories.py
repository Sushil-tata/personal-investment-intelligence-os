from __future__ import annotations

import json
from datetime import datetime

from sqlmodel import Session, select

from piios.thesis.domain.entities import ThesisRoot, ThesisVersion
from piios.thesis.domain.enums import ThesisStatus
from piios.thesis.infrastructure.repository_protocols import ThesisRootRepositoryProtocol, ThesisVersionRepositoryProtocol
from piios_backend.models.entities import ThesisRootEntity, ThesisVersionEntity


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


class SQLModelThesisRootRepository(ThesisRootRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def next_thesis_id(self) -> str:
        rows = self._session.exec(select(ThesisRootEntity.thesis_id)).all()
        max_seen = 0
        for thesis_id in rows:
            if thesis_id.startswith("t") and thesis_id[1:].isdigit():
                max_seen = max(max_seen, int(thesis_id[1:]))
        return f"t{max_seen + 1}"

    def create(self, root: ThesisRoot) -> ThesisRoot:
        row = ThesisRootEntity(
            thesis_id=root.thesis_id,
            ticker=root.ticker,
            lifecycle_status=root.lifecycle_status.value,
            current_version_number=root.current_version_number,
            created_at=root.created_at.isoformat(),
            updated_at=root.updated_at.isoformat(),
            closed_reason=root.closed_reason,
            closed_at=root.closed_at.isoformat() if root.closed_at else None,
        )
        self._session.add(row)
        self._session.commit()
        return root

    def get(self, thesis_id: str) -> ThesisRoot | None:
        row = self._session.exec(select(ThesisRootEntity).where(ThesisRootEntity.thesis_id == thesis_id)).first()
        return _root_from_row(row) if row else None

    def list(self) -> list[ThesisRoot]:
        rows = self._session.exec(select(ThesisRootEntity)).all()
        return [_root_from_row(row) for row in rows]

    def update(self, root: ThesisRoot) -> ThesisRoot:
        row = self._session.exec(select(ThesisRootEntity).where(ThesisRootEntity.thesis_id == root.thesis_id)).first()
        if row is None:
            raise ValueError(f"thesis_id not found: {root.thesis_id}")
        row.lifecycle_status = root.lifecycle_status.value
        row.current_version_number = root.current_version_number
        row.updated_at = root.updated_at.isoformat()
        row.closed_reason = root.closed_reason
        row.closed_at = root.closed_at.isoformat() if root.closed_at else None
        self._session.add(row)
        self._session.commit()
        return root


class SQLModelThesisVersionRepository(ThesisVersionRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, version: ThesisVersion) -> ThesisVersion:
        row = ThesisVersionEntity(
            version_id=version.version_id,
            thesis_id=version.thesis_id,
            version_number=version.version_number,
            asset_name=version.asset_name,
            theme=version.theme,
            bucket=version.bucket,
            thesis=version.thesis,
            bull_case=version.bull_case,
            bear_case=version.bear_case,
            why_now=version.why_now,
            why_not_now=version.why_not_now,
            invalidation_trigger=version.invalidation_trigger,
            valuation_notes=version.valuation_notes,
            expected_holding_period=version.expected_holding_period,
            source_documents=json.dumps(list(version.source_documents)),
            confidence_score=version.confidence_score,
            status=version.status.value,
            created_at=version.created_at.isoformat(),
        )
        self._session.add(row)
        self._session.commit()
        return version

    def get_by_version_id(self, version_id: str) -> ThesisVersion | None:
        row = self._session.exec(select(ThesisVersionEntity).where(ThesisVersionEntity.version_id == version_id)).first()
        return _version_from_row(row) if row else None

    def get_latest(self, thesis_id: str) -> ThesisVersion | None:
        row = self._session.exec(
            select(ThesisVersionEntity)
            .where(ThesisVersionEntity.thesis_id == thesis_id)
            .order_by(ThesisVersionEntity.version_number.desc())
        ).first()
        return _version_from_row(row) if row else None

    def list_for_thesis(self, thesis_id: str) -> list[ThesisVersion]:
        rows = self._session.exec(
            select(ThesisVersionEntity)
            .where(ThesisVersionEntity.thesis_id == thesis_id)
            .order_by(ThesisVersionEntity.version_number.asc())
        ).all()
        return [_version_from_row(row) for row in rows]


def _root_from_row(row: ThesisRootEntity) -> ThesisRoot:
    return ThesisRoot(
        thesis_id=row.thesis_id,
        ticker=row.ticker,
        lifecycle_status=ThesisStatus(row.lifecycle_status),
        current_version_number=row.current_version_number,
        created_at=_parse_dt(row.created_at),
        updated_at=_parse_dt(row.updated_at),
        closed_reason=row.closed_reason,
        closed_at=_parse_dt(row.closed_at) if row.closed_at else None,
    )


def _version_from_row(row: ThesisVersionEntity) -> ThesisVersion:
    return ThesisVersion(
        version_id=row.version_id,
        thesis_id=row.thesis_id,
        version_number=row.version_number,
        asset_name=row.asset_name,
        theme=row.theme,
        bucket=row.bucket,
        thesis=row.thesis,
        bull_case=row.bull_case,
        bear_case=row.bear_case,
        why_now=row.why_now,
        why_not_now=row.why_not_now,
        invalidation_trigger=row.invalidation_trigger,
        valuation_notes=row.valuation_notes,
        expected_holding_period=row.expected_holding_period,
        source_documents=tuple(json.loads(row.source_documents)),
        confidence_score=row.confidence_score,
        status=ThesisStatus(row.status),
        created_at=_parse_dt(row.created_at),
    )
