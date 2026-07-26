from pydantic import BaseModel, Field


class CSVImportResponse(BaseModel):
    imported_rows: int = Field(ge=0)


class ResearchDocumentResponse(BaseModel):
    title: str
    source: str
    timestamp: str
    url: str
    credibility_score: float
    extracted_entities: list[str]
    related_ticker_theme: str


class ResearchFeedResponse(BaseModel):
    items: list[ResearchDocumentResponse]
