from fastapi import APIRouter, UploadFile
from fastapi.responses import PlainTextResponse

from piios_backend.schemas.operations import CSVImportResponse
from piios_backend.schemas.portfolio import Holding
from piios_backend.services.csv_io import from_csv, to_csv
from piios_backend.services.in_memory_store import store


router = APIRouter(prefix="/holdings", tags=["holdings"])


@router.get("", response_model=list[Holding])
def get_holdings() -> list[Holding]:
    return store.holdings


@router.post("/import", response_model=CSVImportResponse)
async def import_holdings(file: UploadFile) -> CSVImportResponse:
    parsed = from_csv((await file.read()).decode("utf-8"))
    return CSVImportResponse(imported_rows=len(parsed))


@router.get("/export", response_class=PlainTextResponse)
def export_holdings() -> str:
    return to_csv([row.model_dump() for row in store.holdings])
