from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from piios.thesis_health.domain.entities import ThesisHealthSnapshot


def test_thesis_health_snapshot_is_immutable() -> None:
    snapshot = ThesisHealthSnapshot(
        thesis_version_id="t1:v1",
        computation_version="wave2b-th-v1",
        computed_at=datetime.now(timezone.utc),
        evidence_freshness=0.9,
        evidence_quality=0.8,
        supporting_strength=0.7,
        contradictory_strength=0.2,
        provenance_completeness=1.0,
        thesis_health_index=0.84,
    )
    with pytest.raises(FrozenInstanceError):
        snapshot.thesis_health_index = 0.5


def test_thesis_health_snapshot_rejects_out_of_range_dimension() -> None:
    with pytest.raises(ValueError):
        ThesisHealthSnapshot(
            thesis_version_id="t1:v1",
            computation_version="wave2b-th-v1",
            computed_at=datetime.now(timezone.utc),
            evidence_freshness=1.1,
            evidence_quality=0.8,
            supporting_strength=0.7,
            contradictory_strength=0.2,
            provenance_completeness=1.0,
            thesis_health_index=0.84,
        )
