from enum import Enum


class ThesisStatus(str, Enum):
    DRAFT = "DRAFT"
    RESEARCHED = "RESEARCHED"
    RISK_CHECKED = "RISK_CHECKED"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"
