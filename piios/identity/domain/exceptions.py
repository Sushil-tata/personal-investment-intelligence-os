class IdentityValidationError(ValueError):
    pass


class EffectiveDateRangeError(IdentityValidationError):
    pass


class DuplicateActiveIdentifierError(IdentityValidationError):
    pass


class OverlappingTickerHistoryError(IdentityValidationError):
    pass


class InvalidRelationshipError(IdentityValidationError):
    pass


class InvalidTransitionError(IdentityValidationError):
    pass


class HardDeleteProhibitedError(IdentityValidationError):
    pass
