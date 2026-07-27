class ThesisDomainError(ValueError):
    pass


class InvalidThesisStatusTransitionError(ThesisDomainError):
    pass


class ThesisNotFoundError(ThesisDomainError):
    pass


class ThesisVersionNotFoundError(ThesisDomainError):
    pass


class ClaimNotFoundError(ThesisDomainError):
    pass


class ClaimVersionBindingError(ThesisDomainError):
    pass


class ClaimInterpretationConflictError(ThesisDomainError):
    pass
