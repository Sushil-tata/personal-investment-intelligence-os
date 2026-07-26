from __future__ import annotations

import json

from sqlmodel import Session

from piios.thesis.application.queries import ListThesesQuery
from piios.thesis.application.services import ThesisApplicationService
from piios.thesis.infrastructure.sqlmodel_repositories import SQLModelThesisRootRepository, SQLModelThesisVersionRepository
from piios_backend.repositories.theses import ThesisRepository
from piios_backend.services.theses import ThesisService
from piios_backend.services.thesis_compatibility import project_latest_to_legacy_schema


_COMPARE_FIELDS = (
    "ticker",
    "asset_name",
    "theme",
    "bucket",
    "thesis",
    "bull_case",
    "bear_case",
    "why_now",
    "why_not_now",
    "invalidation_trigger",
    "valuation_notes",
    "expected_holding_period",
    "source_documents",
    "confidence_score",
    "status",
)


def run_thesis_shadow_diagnostics(session: Session) -> dict[str, object]:
    legacy_repo = ThesisRepository(session)
    versioned = ThesisApplicationService(
        root_repository=SQLModelThesisRootRepository(session),
        version_repository=SQLModelThesisVersionRepository(session),
    )

    legacy_map = {item.thesis_id: item for item in legacy_repo.list()}
    projected = {
        item.thesis_id: project_latest_to_legacy_schema(item)
        for item in versioned.list_theses(ListThesesQuery(include_archived=True))
    }

    # Shadow mode should compare like-for-like records; mirror missing versioned rows from legacy first.
    bridge_service = ThesisService(session)
    for thesis_id, legacy_item in legacy_map.items():
        if thesis_id not in projected:
            bridge_service._sync_missing_versioned_thesis(legacy_item)

    projected = {
        item.thesis_id: project_latest_to_legacy_schema(item)
        for item in versioned.list_theses(ListThesesQuery(include_archived=True))
    }

    mismatches: list[dict[str, object]] = []
    for thesis_id, legacy_item in legacy_map.items():
        candidate = projected.get(thesis_id)
        if candidate is None:
            mismatches.append({"thesis_id": thesis_id, "reason": "missing_in_versioned"})
            continue
        for field in _COMPARE_FIELDS:
            legacy_value = _normalize(field, getattr(legacy_item, field))
            projected_value = _normalize(field, getattr(candidate, field))
            if legacy_value != projected_value:
                mismatches.append(
                    {
                        "thesis_id": thesis_id,
                        "field": field,
                        "legacy": legacy_value,
                        "versioned": projected_value,
                    }
                )

    extras = [thesis_id for thesis_id in projected if thesis_id not in legacy_map]
    return {
        "enabled": True,
        "legacy_count": len(legacy_map),
        "versioned_count": len(projected),
        "mismatches": mismatches,
        "versioned_only_ids": extras,
    }


def _normalize(field: str, value):
    if field == "source_documents" and isinstance(value, str):
        return json.loads(value)
    if field == "status" and hasattr(value, "value"):
        return value.value
    return value
