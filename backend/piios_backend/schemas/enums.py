from enum import Enum


class Bucket(str, Enum):
    EDUCATION = "Education"
    RETIREMENT = "Retirement"
    STRATEGIC_ALPHA = "Strategic Alpha"
    TACTICAL_OPPORTUNITIES = "Tactical Opportunities"


class RecommendationStatus(str, Enum):
    DRAFT = "DRAFT"
    RESEARCHED = "RESEARCHED"
    RISK_CHECKED = "RISK_CHECKED"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"

