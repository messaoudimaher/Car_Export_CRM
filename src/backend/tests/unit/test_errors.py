"""Unit tests for RFC 7807 Domain Exceptions."""

from app.core.errors import (
    AppException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    RateLimitException,
    ServiceUnavailableException,
    UnauthorizedException,
    ValidationException,
)


def test_app_exception_defaults() -> None:
    """Verify base AppException initializes with expected defaults."""
    exc = AppException("Base error message")
    assert exc.message == "Base error message"
    assert exc.status_code == 500
    assert exc.title == "Internal Server Error"
    assert exc.type_uri == "https://errors.carexportcrm.com/internal-error"
    assert exc.detail == "Base error message"


def test_not_found_exception() -> None:
    """Verify NotFoundException attributes (HTTP 404)."""
    exc = NotFoundException("Customer not found", details={"customer_id": "123"})
    assert exc.status_code == 404
    assert exc.title == "Resource Not Found"
    assert exc.type_uri == "https://errors.carexportcrm.com/not-found"
    assert exc.details == {"customer_id": "123"}


def test_unauthorized_exception() -> None:
    """Verify UnauthorizedException attributes (HTTP 401)."""
    exc = UnauthorizedException()
    assert exc.status_code == 401
    assert exc.title == "Authentication Required"
    assert exc.type_uri == "https://errors.carexportcrm.com/unauthorized"


def test_forbidden_exception() -> None:
    """Verify ForbiddenException attributes (HTTP 403)."""
    exc = ForbiddenException()
    assert exc.status_code == 403
    assert exc.title == "Access Forbidden"
    assert exc.type_uri == "https://errors.carexportcrm.com/forbidden"


def test_validation_exception() -> None:
    """Verify ValidationException attributes (HTTP 422)."""
    invalid = [{"name": "email", "reason": "Invalid email address format"}]
    exc = ValidationException(invalid_params=invalid)
    assert exc.status_code == 422
    assert exc.title == "Validation Error"
    assert exc.type_uri == "https://errors.carexportcrm.com/validation-error"
    assert exc.invalid_params == invalid


def test_conflict_exception() -> None:
    """Verify ConflictException attributes (HTTP 409)."""
    exc = ConflictException()
    assert exc.status_code == 409
    assert exc.title == "Resource Conflict"


def test_rate_limit_exception() -> None:
    """Verify RateLimitException attributes (HTTP 429)."""
    exc = RateLimitException()
    assert exc.status_code == 429
    assert exc.title == "Too Many Requests"


def test_service_unavailable_exception() -> None:
    """Verify ServiceUnavailableException attributes (HTTP 503)."""
    exc = ServiceUnavailableException()
    assert exc.status_code == 503
    assert exc.title == "Service Unavailable"
