from __future__ import annotations

from piios.thesis.application.commands import CreateThesisCommand
from piios.thesis.application.dto import ThesisDTO
from piios.thesis.domain.enums import ThesisStatus
from piios_backend.schemas.thesis import InvestmentThesis, ThesisCreateRequest


def create_command_from_request(request: ThesisCreateRequest, thesis_id: str | None = None) -> CreateThesisCommand:
    return CreateThesisCommand(
        thesis_id=thesis_id,
        ticker=request.ticker,
        asset_name=request.asset_name,
        theme=request.theme,
        bucket=request.bucket.value,
        thesis=request.thesis,
        bull_case=request.bull_case,
        bear_case=request.bear_case,
        why_now=request.why_now,
        why_not_now=request.why_not_now,
        invalidation_trigger=request.invalidation_trigger,
        valuation_notes=request.valuation_notes,
        expected_holding_period=request.expected_holding_period,
        source_documents=list(request.source_documents),
        confidence_score=request.confidence_score,
    )


def project_latest_to_legacy_schema(item: ThesisDTO) -> InvestmentThesis:
    return InvestmentThesis(
        thesis_id=item.thesis_id,
        ticker=item.ticker,
        asset_name=item.asset_name,
        theme=item.theme,
        bucket=item.bucket,
        thesis=item.thesis,
        bull_case=item.bull_case,
        bear_case=item.bear_case,
        why_now=item.why_now,
        why_not_now=item.why_not_now,
        invalidation_trigger=item.invalidation_trigger,
        valuation_notes=item.valuation_notes,
        expected_holding_period=item.expected_holding_period,
        source_documents=item.source_documents,
        confidence_score=item.confidence_score,
        status=item.status.value,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def thesis_status_from_legacy(status: str) -> ThesisStatus:
    return ThesisStatus(status)
