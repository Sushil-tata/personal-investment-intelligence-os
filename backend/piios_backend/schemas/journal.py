from pydantic import BaseModel

from piios_backend.schemas.enums import Bucket


class JournalEntry(BaseModel):
    entry_id: str
    ticker: str
    notes: str
    outcome: str
    bucket: Bucket | None = None
    created_at: str
