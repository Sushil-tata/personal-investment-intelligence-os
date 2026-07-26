from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from piios.thesis.application.commands import CreateThesisCommand, CreateThesisVersionCommand, UpdateThesisStatusCommand
from piios.thesis.application.dto import ThesisDTO, ThesisVersionDTO
from piios.thesis.application.queries import GetThesisQuery, ListThesesQuery
from piios.thesis.domain.entities import ThesisRoot, ThesisVersion
from piios.thesis.domain.enums import ThesisStatus
from piios.thesis.domain.exceptions import ThesisNotFoundError
from piios.thesis.domain.value_objects import ThesisVersionNumber, ensure_valid_status_transition
from piios.thesis.infrastructure.repository_protocols import ThesisRootRepositoryProtocol, ThesisVersionRepositoryProtocol


class ThesisApplicationService:
    def __init__(
        self,
        root_repository: ThesisRootRepositoryProtocol,
        version_repository: ThesisVersionRepositoryProtocol,
    ) -> None:
        self._roots = root_repository
        self._versions = version_repository

    def create_thesis(self, command: CreateThesisCommand) -> ThesisDTO:
        now = _now()
        thesis_id = self._roots.next_thesis_id()
        root = ThesisRoot(
            thesis_id=thesis_id,
            ticker=command.ticker,
            lifecycle_status=ThesisStatus.DRAFT,
            current_version_number=1,
            created_at=now,
            updated_at=now,
        )
        version = ThesisVersion(
            version_id=_version_id(thesis_id, 1),
            thesis_id=thesis_id,
            version_number=1,
            asset_name=command.asset_name,
            theme=command.theme,
            bucket=command.bucket,
            thesis=command.thesis,
            bull_case=command.bull_case,
            bear_case=command.bear_case,
            why_now=command.why_now,
            why_not_now=command.why_not_now,
            invalidation_trigger=command.invalidation_trigger,
            valuation_notes=command.valuation_notes,
            expected_holding_period=command.expected_holding_period,
            source_documents=tuple(command.source_documents),
            confidence_score=command.confidence_score,
            status=ThesisStatus.DRAFT,
            created_at=now,
        )
        self._roots.create(root)
        self._versions.create(version)
        return _to_dto(root, version)

    def create_new_version(self, command: CreateThesisVersionCommand) -> ThesisDTO:
        root = self._require_root(command.thesis_id)
        latest = self._require_latest(command.thesis_id)
        now = _now()
        next_version = ThesisVersionNumber(latest.version_number).next().value
        version = ThesisVersion(
            version_id=_version_id(command.thesis_id, next_version),
            thesis_id=command.thesis_id,
            version_number=next_version,
            asset_name=command.asset_name,
            theme=command.theme,
            bucket=command.bucket,
            thesis=command.thesis,
            bull_case=command.bull_case,
            bear_case=command.bear_case,
            why_now=command.why_now,
            why_not_now=command.why_not_now,
            invalidation_trigger=command.invalidation_trigger,
            valuation_notes=command.valuation_notes,
            expected_holding_period=command.expected_holding_period,
            source_documents=tuple(command.source_documents),
            confidence_score=command.confidence_score,
            status=root.lifecycle_status,
            created_at=now,
        )
        updated_root = replace(root, current_version_number=next_version, updated_at=now)
        self._versions.create(version)
        self._roots.update(updated_root)
        return _to_dto(updated_root, version)

    def update_status(self, command: UpdateThesisStatusCommand) -> ThesisDTO:
        root = self._require_root(command.thesis_id)
        latest = self._require_latest(command.thesis_id)
        ensure_valid_status_transition(root.lifecycle_status, command.status)

        now = _now()
        next_version = ThesisVersionNumber(latest.version_number).next().value
        status_version = ThesisVersion(
            version_id=_version_id(command.thesis_id, next_version),
            thesis_id=command.thesis_id,
            version_number=next_version,
            asset_name=latest.asset_name,
            theme=latest.theme,
            bucket=latest.bucket,
            thesis=latest.thesis,
            bull_case=latest.bull_case,
            bear_case=latest.bear_case,
            why_now=latest.why_now,
            why_not_now=latest.why_not_now,
            invalidation_trigger=latest.invalidation_trigger,
            valuation_notes=latest.valuation_notes,
            expected_holding_period=latest.expected_holding_period,
            source_documents=latest.source_documents,
            confidence_score=latest.confidence_score,
            status=command.status,
            created_at=now,
        )
        updated_root = replace(
            root,
            lifecycle_status=command.status,
            current_version_number=next_version,
            updated_at=now,
            closed_reason="status_archived" if command.status == ThesisStatus.ARCHIVED else None,
            closed_at=now if command.status == ThesisStatus.ARCHIVED else None,
        )
        self._versions.create(status_version)
        self._roots.update(updated_root)
        return _to_dto(updated_root, status_version)

    def list_theses(self, query: ListThesesQuery | None = None) -> list[ThesisDTO]:
        include_archived = query.include_archived if query else True
        items: list[ThesisDTO] = []
        for root in self._roots.list():
            if not include_archived and root.lifecycle_status == ThesisStatus.ARCHIVED:
                continue
            latest = self._require_latest(root.thesis_id)
            items.append(_to_dto(root, latest))
        items.sort(key=lambda item: item.updated_at, reverse=True)
        return items

    def get_thesis(self, query: GetThesisQuery) -> ThesisDTO:
        root = self._require_root(query.thesis_id)
        latest = self._require_latest(query.thesis_id)
        return _to_dto(root, latest)

    def list_versions(self, thesis_id: str) -> list[ThesisVersionDTO]:
        self._require_root(thesis_id)
        versions = self._versions.list_for_thesis(thesis_id)
        return [
            ThesisVersionDTO(
                version_id=version.version_id,
                thesis_id=version.thesis_id,
                version_number=version.version_number,
                status=version.status,
                created_at=version.created_at.isoformat(),
            )
            for version in versions
        ]

    def _require_root(self, thesis_id: str) -> ThesisRoot:
        root = self._roots.get(thesis_id)
        if root is None:
            raise ThesisNotFoundError(f"thesis_id not found: {thesis_id}")
        return root

    def _require_latest(self, thesis_id: str) -> ThesisVersion:
        latest = self._versions.get_latest(thesis_id)
        if latest is None:
            raise ThesisNotFoundError(f"no versions found for thesis_id: {thesis_id}")
        return latest


def _to_dto(root: ThesisRoot, version: ThesisVersion) -> ThesisDTO:
    return ThesisDTO(
        thesis_id=root.thesis_id,
        ticker=root.ticker,
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
        source_documents=list(version.source_documents),
        confidence_score=version.confidence_score,
        status=root.lifecycle_status,
        created_at=root.created_at.isoformat(),
        updated_at=root.updated_at.isoformat(),
        current_version_number=root.current_version_number,
        closed_reason=root.closed_reason,
        closed_at=root.closed_at.isoformat() if root.closed_at else None,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _version_id(thesis_id: str, version_number: int) -> str:
    return f"{thesis_id}:v{version_number}"
