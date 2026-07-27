from __future__ import annotations

from datetime import datetime

from piios.thesis_health.domain.entities import ThesisHealthSnapshot
from piios.thesis_health.infrastructure.sqlmodel_entities import ThesisHealthSnapshotEntity


def thesis_health_snapshot_to_row(snapshot: ThesisHealthSnapshot) -> ThesisHealthSnapshotEntity:
    return ThesisHealthSnapshotEntity(
        snapshot_id=_snapshot_id(snapshot),
        thesis_version_id=snapshot.thesis_version_id,
        computation_version=snapshot.computation_version,
        computed_at=snapshot.computed_at.isoformat(),
        evidence_freshness=snapshot.evidence_freshness,
        evidence_quality=snapshot.evidence_quality,
        supporting_strength=snapshot.supporting_strength,
        contradictory_strength=snapshot.contradictory_strength,
        provenance_completeness=snapshot.provenance_completeness,
        thesis_health_index=snapshot.thesis_health_index,
        created_at=snapshot.computed_at.isoformat(),
    )


def thesis_health_snapshot_from_row(row: ThesisHealthSnapshotEntity) -> ThesisHealthSnapshot:
    return ThesisHealthSnapshot(
        thesis_version_id=row.thesis_version_id,
        computation_version=row.computation_version,
        computed_at=datetime.fromisoformat(row.computed_at),
        evidence_freshness=row.evidence_freshness,
        evidence_quality=row.evidence_quality,
        supporting_strength=row.supporting_strength,
        contradictory_strength=row.contradictory_strength,
        provenance_completeness=row.provenance_completeness,
        thesis_health_index=row.thesis_health_index,
    )


def _snapshot_id(snapshot: ThesisHealthSnapshot) -> str:
    return f"ths:{snapshot.thesis_version_id}:{snapshot.computation_version}:{snapshot.computed_at.isoformat()}"
