class ThesisDomainError(ValueError):
    pass


class InvalidThesisStatusTransitionError(ThesisDomainError):
    pass


class ThesisNotFoundError(ThesisDomainError):
    pass
