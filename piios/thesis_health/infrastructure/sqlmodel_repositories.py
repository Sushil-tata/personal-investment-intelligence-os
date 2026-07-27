from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from piios.thesis_health.domain.entities import ThesisHealthSnapshot
from piios.thesis_health.infrastructure.repository_protocols import ThesisHealthRepositoryProtocol
from piios.thesis_health.infrastructure.sqlmodel_entities import ThesisHealthSnapshotEntity
from piios.thesis_health.infrastructure.sqlmodel_mappers import (
    thesis_health_snapshot_from_row,
    thesis_health_snapshot_to_row,
)


class SQLModelThesisHealthRepository(ThesisHealthRepositoryProtocol):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, snapshot: ThesisHealthSnapshot) -> ThesisHealthSnapshot:
        row = thesis_health_snapshot_to_row(snapshot)
        self._session.add(row)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError(
                "duplicate thesis health snapshot for thesis_version_id/computation_version/computed_at"
            ) from exc
        return snapshot

    def get_latest(self, thesis_version_id: str) -> ThesisHealthSnapshot | None:
        row = self._session.exec(
            select(ThesisHealthSnapshotEntity)
            .where(ThesisHealthSnapshotEntity.thesis_version_id == thesis_version_id)
            .order_by(
                ThesisHealthSnapshotEntity.computed_at.desc(),
                ThesisHealthSnapshotEntity.computation_version.desc(),
            )
        ).first()
        return thesis_health_snapshot_from_row(row) if row else None

    def list_history(self, thesis_version_id: str) -> list[ThesisHealthSnapshot]:
        rows = self._session.exec(
            select(ThesisHealthSnapshotEntity)
            .where(ThesisHealthSnapshotEntity.thesis_version_id == thesis_version_id)
            .order_by(
                ThesisHealthSnapshotEntity.computed_at.asc(),
                ThesisHealthSnapshotEntity.computation_version.asc(),
            )
        ).all()
        return [thesis_health_snapshot_from_row(row) for row in rows]
