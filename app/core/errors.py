"""Domain exceptions (requirements §6).

One class per error-table row that a service raises.
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


class ForbiddenError(DomainError):
    status_code = 403
    error_code = "forbidden"


class NotFoundError(DomainError):
    status_code = 404
    error_code = "not_found"


class DuplicateAccountError(DomainError):
    status_code = 409
    error_code = "duplicate_account"


class CurrencyMismatchError(DomainError):
    status_code = 400
    error_code = "currency_mismatch"


class InsufficientFundsError(DomainError):
    status_code = 400
    error_code = "insufficient_funds"
