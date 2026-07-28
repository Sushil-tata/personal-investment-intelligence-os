from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from piios.decision_contracts.application.decision_capture_service import (
    DecisionPersistenceError,
    InvalidDecisionPayloadError,
    RepositoryAccessError,
    UnknownProposalError,
    UnknownProposalVersionError,
)
from piios.decision_contracts.application.decision_query_service import (
    DecisionNotFoundError,
    ProposalNotFoundError,
    ProposalVersionNotFoundError,
)
from piios_backend.core.database import get_session
from piios_backend.schemas.decision_contracts import (
    ConfidenceComponentResponse,
    ConfidenceDiagnosticResponse,
    DecisionCaptureRequestModel,
    DecisionDetailResponse,
    DecisionLineageDiagnosticResponse,
    DiagnosticCheckResponse,
    GovernanceReviewBacklogResponse,
    GovernanceReviewItemResponse,
    RecommendationProposalDetailResponse,
    RecommendationProposalVersionDetailResponse,
    TraceabilityDiagnosticResponse,
)
from piios_backend.services.decision_contracts import DecisionContractsService


router = APIRouter(prefix="/decision-contracts", tags=["decision-contracts"])


def get_decision_contracts_service(session: Session = Depends(get_session)) -> DecisionContractsService:
    return DecisionContractsService(session)


@router.get("/health")
def decision_contracts_health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "advisory_only": True,
    }


@router.post("/decisions/capture", response_model=DecisionDetailResponse)
def capture_decision(
    request: DecisionCaptureRequestModel,
    service: DecisionContractsService = Depends(get_decision_contracts_service),
) -> DecisionDetailResponse:
    try:
        decision = service.capture_decision(request)
        detail = service.query_service.get_decision_lineage_diagnostic(decision.decision_id)
        decision_rows = service.query_service.list_decisions_for_proposal_version(decision.proposal_version_id)
        latest = next((row for row in decision_rows if row.decision_id == decision.decision_id), None)
        if latest is None:
            raise HTTPException(status_code=500, detail="captured decision not found in query projection")
        return _decision_detail_response(latest)
    except UnknownProposalVersionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UnknownProposalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidDecisionPayloadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (RepositoryAccessError, DecisionPersistenceError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/proposals/{proposal_id}", response_model=RecommendationProposalDetailResponse)
def get_proposal(
    proposal_id: str,
    service: DecisionContractsService = Depends(get_decision_contracts_service),
) -> RecommendationProposalDetailResponse:
    try:
        detail = service.query_service.get_recommendation_proposal_detail(proposal_id)
        return RecommendationProposalDetailResponse(
            proposal_id=detail.proposal_id,
            target_type=detail.target_type,
            target_key=detail.target_key,
            scope=detail.scope,
            status=detail.status,
            created_at=detail.created_at,
            updated_at=detail.updated_at,
        )
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/proposal-versions/{proposal_version_id}", response_model=RecommendationProposalVersionDetailResponse)
def get_proposal_version(
    proposal_version_id: str,
    service: DecisionContractsService = Depends(get_decision_contracts_service),
) -> RecommendationProposalVersionDetailResponse:
    try:
        detail = service.query_service.get_proposal_version_detail(proposal_version_id)
        return RecommendationProposalVersionDetailResponse(**detail.__dict__)
    except (ProposalVersionNotFoundError, ProposalNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/proposal-versions/{proposal_version_id}/decisions",
    response_model=tuple[DecisionDetailResponse, ...],
)
def list_decisions_for_proposal_version(
    proposal_version_id: str,
    service: DecisionContractsService = Depends(get_decision_contracts_service),
) -> tuple[DecisionDetailResponse, ...]:
    try:
        rows = service.query_service.list_decisions_for_proposal_version(proposal_version_id)
        return tuple(_decision_detail_response(row) for row in rows)
    except (ProposalVersionNotFoundError, ProposalNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/proposal-versions/{proposal_version_id}/decisions/latest",
    response_model=DecisionDetailResponse | None,
)
def get_latest_decision_for_proposal_version(
    proposal_version_id: str,
    service: DecisionContractsService = Depends(get_decision_contracts_service),
) -> DecisionDetailResponse | None:
    try:
        row = service.query_service.get_latest_decision_for_proposal_version(proposal_version_id)
        if row is None:
            return None
        return _decision_detail_response(row)
    except (ProposalVersionNotFoundError, ProposalNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/proposal-versions/{proposal_version_id}/diagnostics/traceability",
    response_model=TraceabilityDiagnosticResponse,
)
def get_traceability_diagnostic(
    proposal_version_id: str,
    service: DecisionContractsService = Depends(get_decision_contracts_service),
) -> TraceabilityDiagnosticResponse:
    diag = service.query_service.get_traceability_diagnostic(proposal_version_id)
    return TraceabilityDiagnosticResponse(
        proposal_id=diag.proposal_id,
        proposal_version_id=diag.proposal_version_id,
        overall_status=diag.overall_status,
        checks=tuple(_check_response(row) for row in diag.checks),
        diagnostic_codes=diag.diagnostic_codes,
        severity=diag.severity,
        generated_at=diag.generated_at,
    )


@router.get(
    "/proposal-versions/{proposal_version_id}/diagnostics/confidence",
    response_model=ConfidenceDiagnosticResponse,
)
def get_confidence_diagnostic(
    proposal_version_id: str,
    service: DecisionContractsService = Depends(get_decision_contracts_service),
) -> ConfidenceDiagnosticResponse:
    diag = service.query_service.get_confidence_diagnostic(proposal_version_id)
    return ConfidenceDiagnosticResponse(
        proposal_version_id=diag.proposal_version_id,
        authoritative_confidence=diag.authoritative_confidence,
        components=tuple(
            ConfidenceComponentResponse(
                name=row.name,
                value=row.value,
                status=row.status,
                source=row.source,
                explanation=row.explanation,
            )
            for row in diag.components
        ),
        limitations=diag.limitations,
        generated_at=diag.generated_at,
    )


@router.get(
    "/decisions/{decision_id}/diagnostics/lineage",
    response_model=DecisionLineageDiagnosticResponse,
)
def get_decision_lineage_diagnostic(
    decision_id: str,
    service: DecisionContractsService = Depends(get_decision_contracts_service),
) -> DecisionLineageDiagnosticResponse:
    try:
        diag = service.query_service.get_decision_lineage_diagnostic(decision_id)
        return DecisionLineageDiagnosticResponse(
            decision_id=diag.decision_id,
            proposal_id=diag.proposal_id,
            proposal_version_id=diag.proposal_version_id,
            decision_state=diag.decision_state,
            decision_meaning=diag.decision_meaning,
            overall_status=diag.overall_status,
            checks=tuple(_check_response(row) for row in diag.checks),
            diagnostic_codes=diag.diagnostic_codes,
            severity=diag.severity,
            generated_at=diag.generated_at,
        )
    except DecisionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/proposal-versions/{proposal_version_id}/governance-backlog",
    response_model=GovernanceReviewBacklogResponse,
)
def get_governance_backlog(
    proposal_version_id: str,
    service: DecisionContractsService = Depends(get_decision_contracts_service),
) -> GovernanceReviewBacklogResponse:
    try:
        backlog = service.query_service.get_governance_review_backlog(proposal_version_id)
        return GovernanceReviewBacklogResponse(
            proposal_version_id=backlog.proposal_version_id,
            items=tuple(
                GovernanceReviewItemResponse(
                    review_item_id=row.review_item_id,
                    proposal_id=row.proposal_id,
                    proposal_version_id=row.proposal_version_id,
                    decision_id=row.decision_id,
                    reason_code=row.reason_code,
                    severity=row.severity,
                    status=row.status,
                    created_at=row.created_at,
                    source_diagnostic=row.source_diagnostic,
                    summary=row.summary,
                )
                for row in backlog.items
            ),
            generated_at=backlog.generated_at,
        )
    except (ProposalVersionNotFoundError, ProposalNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _decision_detail_response(row) -> DecisionDetailResponse:
    return DecisionDetailResponse(
        decision_id=row.decision_id,
        proposal_version_id=row.proposal_version_id,
        state=row.state,
        decision_meaning=row.decision_meaning,
        reason_code=row.reason_code,
        reason_text=row.reason_text,
        decided_by=row.decided_by,
        decided_at=row.decided_at,
        preferred_alternative_target_key=row.preferred_alternative_target_key,
        modified_action=row.modified_action,
        modified_action_note=row.modified_action_note,
        modified_action_min_weight=row.modified_action_min_weight,
        modified_action_max_weight=row.modified_action_max_weight,
        modified_position_min_weight=row.modified_position_min_weight,
        modified_position_max_weight=row.modified_position_max_weight,
    )


def _check_response(row) -> DiagnosticCheckResponse:
    return DiagnosticCheckResponse(
        code=row.code,
        status=row.status,
        severity=row.severity,
        message=row.message,
        related_entity_type=row.related_entity_type,
        related_entity_id=row.related_entity_id,
        remediation_hint=row.remediation_hint,
    )
