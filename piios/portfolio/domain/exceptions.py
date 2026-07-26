class PortfolioDomainError(ValueError):
    """Base domain error for portfolio context."""


class ValidationError(PortfolioDomainError):
    """Raised when invalid domain values are provided."""


class CurrencyConversionError(PortfolioDomainError):
    """Raised when a required FX conversion cannot be resolved."""
