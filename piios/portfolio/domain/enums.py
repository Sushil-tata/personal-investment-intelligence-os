from __future__ import annotations

from enum import Enum


class PortfolioBucket(str, Enum):
    EDUCATION = "Education"
    RETIREMENT = "Retirement"
    STRATEGIC_ALPHA = "Strategic Alpha"
    TACTICAL_OPPORTUNITIES = "Tactical Opportunities"
    SAFETY = "Safety"
    UNKNOWN = "Unknown"


class ExposureBasis(str, Enum):
    TOTAL_NET_WORTH = "total_net_worth"
    LIQUID_INVESTABLE = "liquid_investable"
    LISTED_EQUITY = "listed_equity"


class CountryMode(str, Enum):
    LISTING = "listing"
    ECONOMIC = "economic"


class DataIssueSeverity(str, Enum):
    WARNING = "warning"
    ERROR = "error"
