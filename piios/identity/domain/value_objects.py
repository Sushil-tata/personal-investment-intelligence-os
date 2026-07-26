from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .exceptions import EffectiveDateRangeError, IdentityValidationError


@dataclass(frozen=True)
class CompanyId:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise IdentityValidationError("company_id must be non-empty")


@dataclass(frozen=True)
class SecurityId:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise IdentityValidationError("security_id must be non-empty")


@dataclass(frozen=True)
class ListingId:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise IdentityValidationError("listing_id must be non-empty")


@dataclass(frozen=True)
class ExchangeCode:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise IdentityValidationError("exchange code must be non-empty")


@dataclass(frozen=True)
class Ticker:
    source_value: str
    canonical_value: str

    @classmethod
    def from_source(cls, value: str) -> "Ticker":
        if not value or not value.strip():
            raise IdentityValidationError("ticker must be non-empty")
        source = value.strip()
        canonical = source.upper().replace(" ", "")
        return cls(source_value=source, canonical_value=canonical)


@dataclass(frozen=True)
class CountryCode:
    value: str

    def __post_init__(self) -> None:
        val = self.value.strip().upper()
        if len(val) != 2 or not val.isalpha():
            raise IdentityValidationError("country code must be 2-letter ISO style code")


@dataclass(frozen=True)
class CurrencyCode:
    value: str

    def __post_init__(self) -> None:
        val = self.value.strip().upper()
        if len(val) != 3 or not val.isalpha():
            raise IdentityValidationError("currency code must be 3-letter ISO style code")


@dataclass(frozen=True)
class EffectiveDateRange:
    active_from: date
    active_to: date | None = None

    def __post_init__(self) -> None:
        if self.active_to is not None and self.active_to < self.active_from:
            raise EffectiveDateRangeError("active_to must be on or after active_from")

    def contains(self, target: date) -> bool:
        if target < self.active_from:
            return False
        if self.active_to is None:
            return True
        return target <= self.active_to


@dataclass(frozen=True)
class IdentifierValue:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise IdentityValidationError("identifier value must be non-empty")
