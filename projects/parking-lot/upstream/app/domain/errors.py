"""Domain/application error hierarchy, mapped to HTTP once at the edge.

Each class carries its HTTP status and a stable default message (the
``detail`` string the Flutter client already relies on). The presentation
layer renders every ``DomainError`` as ``{"detail": str(exc), "code":
type(exc).__name__}``; nothing below presentation imports FastAPI.
"""

from typing import ClassVar


class DomainError(Exception):
    status_code: ClassVar[int] = 400
    message: ClassVar[str] = "Bad request"

    def __init__(self, message: str | None = None):
        super().__init__(message or self.message)


class NotFoundError(DomainError):
    status_code = 404
    message = "Not found"


class ConflictError(DomainError):
    status_code = 409
    message = "Conflict"


class DomainValidationError(DomainError):
    status_code = 422
    message = "Invalid data"


class AuthenticationError(DomainError):
    status_code = 401
    message = "Not authenticated"


class PermissionDeniedError(DomainError):
    status_code = 403
    message = "Forbidden"


class PayloadTooLargeError(DomainError):
    status_code = 413
    message = "Payload too large"


class TooManyRequestsError(DomainError):
    status_code = 429
    message = "Too many requests"

    def __init__(self, retry_after_seconds: int, message: str | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


# --- Not found -------------------------------------------------------------


class VehicleNotFoundError(NotFoundError):
    message = "Vehicle not found"


class CategoryNotFoundError(NotFoundError):
    message = "Category not found"


class TariffNotFoundError(NotFoundError):
    message = "Tariff not found"


class UserNotFoundError(NotFoundError):
    message = "User not found"


class MonthlyPassNotFoundError(NotFoundError):
    message = "Monthly pass not found"


class SessionNotFoundError(NotFoundError):
    message = "Session not found"


class MissingHourlyTariffError(NotFoundError):
    message = "Hourly tariff not configured for category"


# --- Conflicts -------------------------------------------------------------


class DuplicateOpenSessionError(ConflictError):
    message = "Vehicle already has an open session"


class DuplicatePlateError(ConflictError):
    message = "Plate already exists"


class DuplicateCategoryNameError(ConflictError):
    message = "Category already exists"


class DuplicateUsernameError(ConflictError):
    message = "Username already exists"


class SessionAlreadyClosedError(ConflictError):
    message = "Session already closed"


class IdempotencyKeyInUseError(ConflictError):
    message = "Idempotency-Key already used"


# --- Validation ------------------------------------------------------------


class VehicleNotRegisteredError(DomainValidationError):
    message = "Vehicle not registered: category_id is required"


class InvalidBillingPeriodError(DomainValidationError):
    """The stay period is empty, reversed or timezone-naive."""


class InvalidExitTimeError(InvalidBillingPeriodError):
    """client_exit_time outside (entry_time, now + allowed clock skew]."""


class InvalidReportRangeError(DomainValidationError):
    pass


class InvalidPhotoError(DomainValidationError):
    message = "Photos must be JPEG or PNG images"


class IdempotencyKeyMismatchError(DomainValidationError):
    message = "Idempotency-Key was already used for a different request"


class PhotoTooLargeError(PayloadTooLargeError):
    pass


# --- Authentication / authorization ----------------------------------------


class InvalidCredentialsError(AuthenticationError):
    message = "Invalid credentials"


class InvalidTokenError(AuthenticationError):
    message = "Invalid token"


class AdminRequiredError(PermissionDeniedError):
    message = "Admin required"


class TooManyLoginAttemptsError(TooManyRequestsError):
    message = "Too many attempts, try later"
