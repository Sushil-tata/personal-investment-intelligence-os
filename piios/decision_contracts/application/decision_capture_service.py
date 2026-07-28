from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json

from piios.decision_contracts.domain.decision import InvestmentDecision
from piios.decision_contracts.domain.enums import DecisionState, RecommendationAction
from piios.decision_contracts.domain.value_objects import ActionProposal, PositionSizeRange
from piios.decision_contracts.infrastructure.repository_protocols import (
    InvestmentDecisionRepositoryProtocol,
    RecommendationProposalRepositoryProtocol,
    RecommendationProposalVersionRepositoryProtocol,
)


class DecisionCaptureError(Exception):
    pass


class UnknownProposalVersionError(DecisionCaptureError):
    pass


class UnknownProposalError(DecisionCaptureError):
    pass


class InvalidDecisionPayloadError(DecisionCaptureError):
    pass


class RepositoryAccessError(DecisionCaptureError):
    pass


class DecisionPersistenceError(DecisionCaptureError):
    pass


class DecisionType(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    MODIFIED = "MODIFIED"
    OVERRIDDEN = "OVERRIDDEN"
    DEFERRED = "DEFERRED"
    REQUEST_RESEARCH = "REQUEST_RESEARCH"


@dataclass(frozen=True)
class DecisionCaptureRequest:
    proposal_version_id: str
    decision_type: DecisionType
    reviewer: str
    reason_code: str | None = None
    reason_text: str | None = None
    preferred_alternative_target_key: str | None = None
    modified_action: RecommendationAction | None = None
    modified_action_note: str | None = None
    modified_action_min_weight: float | None = None
    modified_action_max_weight: float | None = None
    modified_position_min_weight: float | None = None
    modified_position_max_weight: float | None = None
    client_request_id: str | None = None
    decided_at: datetime | None = None


class DecisionCaptureService:
    """Capture immutable human decisions for an existing recommendation proposal version.

    Idempotency strategy:
    - Build a deterministic fingerprint from logical request fields.
    - Derive decision_id from proposal_version_id + fingerprint hash.
    - If a decision with that deterministic decision_id already exists, return it.
    - If payload differs, hash differs, so a new immutable decision record is created.
    """

    def __init__(
        self,
        proposal_repository: RecommendationProposalRepositoryProtocol,
        version_repository: RecommendationProposalVersionRepositoryProtocol,
        decision_repository: InvestmentDecisionRepositoryProtocol,
    ) -> None:
        self._proposal_repository = proposal_repository
        self._version_repository = version_repository
        self._decision_repository = decision_repository

    def capture(self, request: DecisionCaptureRequest) -> InvestmentDecision:
        self._validate_request_shape(request)

        proposal_version = self._safe_repo_call(
            "version_repository.get",
            lambda: self._version_repository.get(request.proposal_version_id),
        )
        if proposal_version is None:
            raise UnknownProposalVersionError(f"unknown proposal_version_id: {request.proposal_version_id}")

        proposal = self._safe_repo_call(
            "proposal_repository.get",
            lambda: self._proposal_repository.get(proposal_version.proposal_id),
        )
        if proposal is None:
            raise UnknownProposalError(
                "proposal missing for proposal_version_id="
                f"{request.proposal_version_id}: {proposal_version.proposal_id}"
            )

        state = _decision_state_from_type(request.decision_type)
        reason_code = _resolve_reason_code(request)
        modified_action = _build_modified_action(request)
        modified_position = _build_modified_position_size(request)

        fingerprint = _idempotency_fingerprint(
            proposal_version_id=request.proposal_version_id,
            decision_type=request.decision_type,
            reviewer=request.reviewer,
            reason_code=reason_code,
            reason_text=request.reason_text,
            preferred_alternative_target_key=request.preferred_alternative_target_key,
            modified_action=modified_action,
            modified_position=modified_position,
            client_request_id=request.client_request_id,
        )
        decision_id = _decision_id_from_fingerprint(request.proposal_version_id, fingerprint)

        existing = self._safe_repo_call(
            "decision_repository.get",
            lambda: self._decision_repository.get(decision_id),
        )
        if existing is not None:
            return existing

        decision = InvestmentDecision(
            decision_id=decision_id,
            proposal_version_id=request.proposal_version_id,
            state=state,
            reason_code=reason_code,
            reason_text=request.reason_text,
            decided_by=request.reviewer,
            preferred_alternative_target_key=request.preferred_alternative_target_key,
            modified_action=modified_action,
            modified_position_size=modified_position,
            decided_at=request.decided_at or datetime.now(timezone.utc),
        )

        try:
            return self._decision_repository.create(decision)
        except Exception as exc:  # pragma: no cover - exercised by tests via fake repo
            resolved = self._safe_repo_call(
                "decision_repository.get",
                lambda: self._decision_repository.get(decision_id),
            )
            if resolved is not None:
                return resolved
            raise DecisionPersistenceError(f"failed to persist decision_id={decision_id}") from exc

    @staticmethod
    def _validate_request_shape(request: DecisionCaptureRequest) -> None:
        if not request.proposal_version_id.strip():
            raise InvalidDecisionPayloadError("proposal_version_id must not be empty")
        if not request.reviewer.strip():
            raise InvalidDecisionPayloadError("reviewer must not be empty")
        if request.client_request_id is not None and not request.client_request_id.strip():
            raise InvalidDecisionPayloadError("client_request_id cannot be blank")

        if request.modified_action in (RecommendationAction.NO_ACTION, RecommendationAction.REMOVE_FROM_WATCHLIST):
            raise InvalidDecisionPayloadError("modified_action is not allowed for decision capture")

    @staticmethod
    def _safe_repo_call(label: str, call):
        try:
            return call()
        except DecisionCaptureError:
            raise
        except Exception as exc:
            raise RepositoryAccessError(f"repository failure at {label}") from exc


def _decision_state_from_type(decision_type: DecisionType) -> DecisionState:
    mapping = {
        DecisionType.ACCEPT: DecisionState.ACCEPTED,
        DecisionType.REJECT: DecisionState.REJECTED,
        DecisionType.MODIFIED: DecisionState.MODIFIED,
        DecisionType.OVERRIDDEN: DecisionState.OVERRIDDEN,
        DecisionType.DEFERRED: DecisionState.DEFERRED,
        DecisionType.REQUEST_RESEARCH: DecisionState.DEFERRED,
    }
    return mapping[decision_type]


def _resolve_reason_code(request: DecisionCaptureRequest) -> str:
    if request.decision_type == DecisionType.REQUEST_RESEARCH:
        return (request.reason_code or "REQUEST_RESEARCH").strip() or "REQUEST_RESEARCH"

    if request.reason_code is None or not request.reason_code.strip():
        raise InvalidDecisionPayloadError("reason_code must not be empty")
    return request.reason_code.strip()


def _build_modified_action(request: DecisionCaptureRequest) -> ActionProposal | None:
    if request.modified_action is None:
        if (
            request.modified_action_note is not None
            or request.modified_action_min_weight is not None
            or request.modified_action_max_weight is not None
        ):
            raise InvalidDecisionPayloadError(
                "modified_action_note and modified_action weights require modified_action"
            )
        return None

    position_size = None
    if request.modified_action_min_weight is not None or request.modified_action_max_weight is not None:
        if request.modified_action_min_weight is None or request.modified_action_max_weight is None:
            raise InvalidDecisionPayloadError("modified_action min/max weights must be provided together")
        position_size = PositionSizeRange(
            min_weight=request.modified_action_min_weight,
            max_weight=request.modified_action_max_weight,
        )

    return ActionProposal(
        action=request.modified_action,
        position_size_range=position_size,
        note=request.modified_action_note,
    )


def _build_modified_position_size(request: DecisionCaptureRequest) -> PositionSizeRange | None:
    if request.modified_position_min_weight is None and request.modified_position_max_weight is None:
        return None
    if request.modified_position_min_weight is None or request.modified_position_max_weight is None:
        raise InvalidDecisionPayloadError("modified_position min/max weights must be provided together")
    return PositionSizeRange(
        min_weight=request.modified_position_min_weight,
        max_weight=request.modified_position_max_weight,
    )


def _decision_id_from_fingerprint(proposal_version_id: str, fingerprint: str) -> str:
    return f"decision:{proposal_version_id}:{fingerprint[:24]}"


def _idempotency_fingerprint(
    proposal_version_id: str,
    decision_type: DecisionType,
    reviewer: str,
    reason_code: str,
    reason_text: str | None,
    preferred_alternative_target_key: str | None,
    modified_action: ActionProposal | None,
    modified_position: PositionSizeRange | None,
    client_request_id: str | None,
) -> str:
    modified_action_payload = None
    if modified_action is not None:
        modified_action_payload = {
            "action": modified_action.action.value,
            "note": modified_action.note,
            "position_size_range": (
                {
                    "min_weight": modified_action.position_size_range.min_weight,
                    "max_weight": modified_action.position_size_range.max_weight,
                }
                if modified_action.position_size_range is not None
                else None
            ),
        }

    payload = {
        "proposal_version_id": proposal_version_id,
        "decision_type": decision_type.value,
        "reviewer": reviewer.strip(),
        "reason_code": reason_code,
        "reason_text": reason_text,
        "preferred_alternative_target_key": preferred_alternative_target_key,
        "modified_action": modified_action_payload,
        "modified_position_size": (
            {
                "min_weight": modified_position.min_weight,
                "max_weight": modified_position.max_weight,
            }
            if modified_position is not None
            else None
        ),
        "client_request_id": client_request_id,
    }

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
