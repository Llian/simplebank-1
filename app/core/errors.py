"""Domain exceptions (requirements §6).

One class per error-table row that a service currently raises. `not_found`
and the currency/ownership/insufficient-funds codes are intentionally not
defined yet — the accounts/transfers implementation will add them here using
the same base and naming.
"""


class DomainError(Exception):
    """Base for all business-rule failures. Subclasses set status_code/error_code."""

    status_code: int
    error_code: str

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class DuplicateUsernameError(DomainError):
    status_code = 409
    error_code = "duplicate_username"


class DuplicateEmailError(DomainError):
    status_code = 409
    error_code = "duplicate_email"


class InvalidCredentialsError(DomainError):
    status_code = 401
    error_code = "invalid_credentials"


class UnauthorizedError(DomainError):
    status_code = 401
    error_code = "unauthorized"
