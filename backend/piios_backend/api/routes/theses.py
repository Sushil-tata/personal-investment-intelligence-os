from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlmodel import Session

from piios_backend.core.database import get_session
from piios_backend.schemas.thesis import InvestmentThesis, ThesisCreateRequest, ThesisStatusUpdateRequest
from piios_backend.services.csv_io import to_csv
from piios_backend.services.theses import ThesisService


router = APIRouter(prefix="/theses", tags=["theses"])


def get_thesis_service(session: Session = Depends(get_session)) -> ThesisService:
    return ThesisService(session)


@router.get("", response_model=list[InvestmentThesis])
def list_theses(service: ThesisService = Depends(get_thesis_service)) -> list[InvestmentThesis]:
    return service.list_theses()


@router.post("", response_model=InvestmentThesis)
def create_thesis(request: ThesisCreateRequest, service: ThesisService = Depends(get_thesis_service)) -> InvestmentThesis:
    return service.create_thesis(request)


@router.get("/export", response_class=PlainTextResponse)
def export_theses(service: ThesisService = Depends(get_thesis_service)) -> str:
    return to_csv(service.export_csv_rows())


@router.get("/{thesis_id}", response_model=InvestmentThesis)
def get_thesis(thesis_id: str, service: ThesisService = Depends(get_thesis_service)) -> InvestmentThesis:
    return service.get_thesis(thesis_id)


@router.patch("/{thesis_id}/status", response_model=InvestmentThesis)
def update_thesis_status(
    thesis_id: str,
    request: ThesisStatusUpdateRequest,
    service: ThesisService = Depends(get_thesis_service),
) -> InvestmentThesis:
    return service.update_thesis_status(thesis_id, request.status)
