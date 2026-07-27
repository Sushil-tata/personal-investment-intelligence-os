from __future__ import annotations

from typing import Optional

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, SQLModel


class ThesisHealthSnapshotEntity(SQLModel, table=True):
    __tablename__ = "thesis_health_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "thesis_version_id",
            "computation_version",
            "computed_at",
            name="uq_thesis_health_snapshots_version_computation_time",
        ),
        Index("ix_thesis_health_snapshots_thesis_version_id", "thesis_version_id"),
        Index("ix_thesis_health_snapshots_computed_at", "computed_at"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    snapshot_id: str = Field(index=True, unique=True)
    thesis_version_id: str = Field(foreign_key="thesis_versions.version_id")
    computation_version: str
    computed_at: str
    evidence_freshness: float
    evidence_quality: float
    supporting_strength: float
    contradictory_strength: float
    provenance_completeness: float
    thesis_health_index: float
    created_at: str
