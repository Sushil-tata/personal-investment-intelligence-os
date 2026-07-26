from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .exceptions import ValidationError


DECIMAL_ZERO = Decimal("0")


def as_decimal(value: str | int | float | Decimal) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"Invalid decimal value: {value}") from exc
    return parsed


@dataclass(frozen=True)
class Currency:
    code: str

    def __post_init__(self) -> None:
        normalized = self.code.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValidationError(f"Invalid currency code: {self.code}")
        object.__setattr__(self, "code", normalized)


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: Currency

    @classmethod
    def from_value(cls, amount: str | int | float | Decimal, currency: str | Currency) -> "Money":
        ccy = currency if isinstance(currency, Currency) else Currency(currency)
        return cls(amount=as_decimal(amount), currency=ccy)

    def __post_init__(self) -> None:
        if self.amount.is_nan():
            raise ValidationError("Money amount cannot be NaN")


@dataclass(frozen=True)
class Quantity:
    value: Decimal

    @classmethod
    def from_value(cls, value: str | int | float | Decimal) -> "Quantity":
        return cls(value=as_decimal(value))

    def __post_init__(self) -> None:
        if self.value < DECIMAL_ZERO:
            raise ValidationError("Quantity cannot be negative")


@dataclass(frozen=True)
class Price:
    amount: Decimal
    currency: Currency

    @classmethod
    def from_value(cls, amount: str | int | float | Decimal, currency: str | Currency) -> "Price":
        ccy = currency if isinstance(currency, Currency) else Currency(currency)
        return cls(amount=as_decimal(amount), currency=ccy)

    def __post_init__(self) -> None:
        if self.amount < DECIMAL_ZERO:
            raise ValidationError("Price cannot be negative")


@dataclass(frozen=True)
class CostBasis:
    unit_cost: Money


@dataclass(frozen=True)
class SecurityIdentifier:
    ticker: str
    exchange: str | None = None
    isin: str | None = None

    def __post_init__(self) -> None:
        normalized_ticker = self.ticker.strip().upper()
        if not normalized_ticker:
            raise ValidationError("Ticker is required")
        object.__setattr__(self, "ticker", normalized_ticker)


@dataclass(frozen=True)
class CountryExposure:
    country: str
    value_reporting: Decimal
    weight_pct: Decimal


@dataclass(frozen=True)
class SectorExposure:
    sector: str
    value_reporting: Decimal
    weight_pct: Decimal


@dataclass(frozen=True)
class ThemeExposure:
    theme: str
    value_reporting: Decimal
    weight_pct: Decimal
