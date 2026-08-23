class AppError(Exception):
    """Base class for all application-raised errors.

    Layers below the API (domain/application/infrastructure) must only raise
    subclasses of this — never HTTPException — so they stay framework-agnostic.
    """

    status_code: int = 500
    error_code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None):
        self.message = message or self.message
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"
    message = "Resource not found."


class ValidationError(AppError):
    status_code = 422
    error_code = "validation_error"
    message = "Invalid input."


class ConflictError(AppError):
    status_code = 409
    error_code = "conflict"
    message = "Resource already exists."


class UnauthorizedError(AppError):
    status_code = 401
    error_code = "unauthorized"
    message = "Authentication required."


class ForbiddenError(AppError):
    status_code = 403
    error_code = "forbidden"
    message = "You do not have permission to perform this action."


class RideCancelledError(ConflictError):
    """A 409 specifically because the ride was cancelled (by the rider) -
    distinguishable from the generic conflict (e.g. already accepted by
    another driver) so callers can show an accurate message instead of a
    misleading "no longer available"/"taken by someone else" one."""

    error_code = "ride_cancelled"
    message = "This ride was cancelled by the rider."
