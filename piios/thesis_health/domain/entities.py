from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ThesisHealthSnapshot:
    thesis_version_id: str
    computation_version: str
    computed_at: datetime
    evidence_freshness: float
    evidence_quality: float
    supporting_strength: float
    contradictory_strength: float
    provenance_completeness: float
    thesis_health_index: float

    def __post_init__(self) -> None:
        if not self.thesis_version_id.strip():
            raise ValueError("thesis_version_id must not be empty")
        if not self.computation_version.strip():
            raise ValueError("computation_version must not be empty")
        for field_name, value in (
            ("evidence_freshness", self.evidence_freshness),
            ("evidence_quality", self.evidence_quality),
            ("supporting_strength", self.supporting_strength),
            ("contradictory_strength", self.contradictory_strength),
            ("provenance_completeness", self.provenance_completeness),
            ("thesis_health_index", self.thesis_health_index),
        ):
            if value < 0.0 or value > 1.0:
                raise ValueError(f"{field_name} must be within [0.0, 1.0]")
