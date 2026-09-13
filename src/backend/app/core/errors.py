"""RFC 7807 Problem Details Domain Exceptions & Error Handlers (ADR 0008)."""

from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_correlation_id, logger

PROBLEM_JSON_MEDIA_TYPE = "application/problem+json"


class AppException(Exception):
    """Base domain exception for RFC 7807 problem details errors."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        title: str = "Internal Server Error",
        type_uri: str = "https://errors.carexportcrm.com/internal-error",
        detail: str | None = None,
        details: dict[str, Any] | None = None,
        invalid_params: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.title = title
        self.type_uri = type_uri
        self.detail = detail or message
        self.details = details or {}
        self.invalid_params = invalid_params


class NotFoundException(AppException):
    """Resource not found exception (HTTP 404)."""

    def __init__(
        self,
        message: str = "The requested resource was not found.",
        detail: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            title="Resource Not Found",
            type_uri="https://errors.carexportcrm.com/not-found",
            detail=detail,
            details=details,
        )


class UnauthorizedException(AppException):
    """Authentication required exception (HTTP 401)."""

    def __init__(
        self,
        message: str = "Authentication credentials are missing or invalid.",
        detail: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Authentication Required",
            type_uri="https://errors.carexportcrm.com/unauthorized",
            detail=detail,
            details=details,
        )


class ForbiddenException(AppException):
    """Access forbidden exception (HTTP 403)."""

    def __init__(
        self,
        message: str = "You do not have permission to perform this action.",
        detail: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            title="Access Forbidden",
            type_uri="https://errors.carexportcrm.com/forbidden",
            detail=detail,
            details=details,
        )


class SSRFProtectionException(ForbiddenException):
    """Exception raised when an outbound fetch request violates SSRF security boundaries (FR-SSRF-001)."""

    def __init__(
        self,
        message: str = "Outbound request blocked by SSRF security policy.",
        detail: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            detail=detail or message,
            details=details,
        )
        self.type_uri = "https://errors.carexportcrm.com/ssrf-protection-error"
        self.title = "SSRF Protection Error"


class ValidationException(AppException):
    """Request validation exception (HTTP 422)."""

    def __init__(
        self,
        message: str = "One or more fields failed validation checks.",
        detail: str | None = None,
        invalid_params: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Validation Error",
            type_uri="https://errors.carexportcrm.com/validation-error",
            detail=detail,
            invalid_params=invalid_params,
        )


class AISchemaValidationException(ValidationException):
    """Exception raised when raw LLM output fails Layer 2 Pydantic schema validation (ADR 0012)."""

    def __init__(
        self,
        message: str = "AI output failed Layer 2 schema validation.",
        detail: str | None = None,
        invalid_params: list[dict[str, Any]] | None = None,
        raw_output: str | None = None,
        attempts: int = 1,
    ) -> None:
        super().__init__(
            message=message,
            detail=detail or message,
            invalid_params=invalid_params,
        )
        self.type_uri = "https://errors.carexportcrm.com/ai-schema-validation-error"
        self.title = "AI Schema Validation Error"
        self.raw_output = raw_output
        self.attempts = attempts


class ConflictException(AppException):
    """Resource state conflict exception (HTTP 409)."""

    def __init__(
        self,
        message: str = "A conflict occurred with the current state of the resource.",
        detail: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            title="Resource Conflict",
            type_uri="https://errors.carexportcrm.com/conflict",
            detail=detail,
            details=details,
        )


class ConcurrencyException(AppException):
    """Optimistic concurrency control conflict exception (HTTP 412)."""

    def __init__(
        self,
        message: str = "Resource version conflict. Record modified by another request.",
        detail: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            title="Precondition Failed",
            type_uri="https://errors.carexportcrm.com/concurrency-conflict",
            detail=detail,
            details=details,
        )


class RateLimitException(AppException):
    """Rate limit exceeded exception (HTTP 429)."""

    def __init__(
        self,
        message: str = "Request rate limit exceeded. Please slow down.",
        detail: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            title="Too Many Requests",
            type_uri="https://errors.carexportcrm.com/rate-limit",
            detail=detail,
            details=details,
        )


class ServiceUnavailableException(AppException):
    """Service unavailable exception (HTTP 503)."""

    def __init__(
        self,
        message: str = "Service is temporarily unavailable. Please try again later.",
        detail: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            title="Service Unavailable",
            type_uri="https://errors.carexportcrm.com/service-unavailable",
            detail=detail,
            details=details,
        )


class DeveloperSecurityException(AppException):
    """Internal developer security boundary violation exception (HTTP 500)."""

    def __init__(
        self,
        message: str = "A security invariant was violated due to missing security context.",
        detail: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Security Context Invariant Error",
            type_uri="https://errors.carexportcrm.com/security-context-error",
            detail=detail,
            details=details,
        )


def create_problem_response(
    status_code: int,
    title: str,
    type_uri: str,
    detail: str,
    instance: str,
    correlation_id: str | None = None,
    invalid_params: list[dict[str, Any]] | None = None,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build an RFC 7807 application/problem+json response envelope."""
    corr_id = correlation_id or get_correlation_id() or "unknown"
    response_headers = headers or {}
    response_headers["X-Correlation-ID"] = corr_id

    content: dict[str, Any] = {
        "type": type_uri,
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
        "correlation_id": corr_id,
    }

    if invalid_params:
        content["invalid_params"] = invalid_params

    if details:
        content["details"] = details

    return JSONResponse(
        status_code=status_code,
        media_type=PROBLEM_JSON_MEDIA_TYPE,
        content=content,
        headers=response_headers,
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle domain AppException instances and format RFC 7807 envelopes."""
    logger.warning(
        "app_domain_exception",
        extra={
            "status_code": exc.status_code,
            "title": exc.title,
            "path": request.url.path,
            "detail": exc.detail,
        },
    )
    return create_problem_response(
        status_code=exc.status_code,
        title=exc.title,
        type_uri=exc.type_uri,
        detail=exc.detail,
        instance=request.url.path,
        invalid_params=exc.invalid_params,
        details=exc.details,
    )


async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle FastAPI/Pydantic request validation errors (HTTP 422)."""
    invalid_params: list[dict[str, Any]] = []
    for err in exc.errors():
        loc = ".".join(str(loc_item) for loc_item in err.get("loc", []))
        invalid_params.append(
            {
                "name": loc,
                "reason": err.get("msg", "Invalid field value"),
            }
        )

    logger.warning(
        "request_validation_error",
        extra={
            "path": request.url.path,
            "param_count": len(invalid_params),
        },
    )
    return create_problem_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="Validation Error",
        type_uri="https://errors.carexportcrm.com/validation-error",
        detail="One or more request validation checks failed.",
        instance=request.url.path,
        invalid_params=invalid_params,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle standard Starlette/FastAPI HTTPExceptions."""
    detail_str = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    type_uri = f"https://errors.carexportcrm.com/http-{exc.status_code}"

    logger.warning(
        "http_exception",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
            "detail": detail_str,
        },
    )
    return create_problem_response(
        status_code=exc.status_code,
        title=f"HTTP Error {exc.status_code}",
        type_uri=type_uri,
        detail=detail_str,
        instance=request.url.path,
        headers=dict(exc.headers) if exc.headers else None,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unhandled exceptions (HTTP 500), masking stack traces."""
    logger.error(
        "unhandled_server_error",
        extra={
            "path": request.url.path,
            "error_class": exc.__class__.__name__,
            "error": str(exc),
        },
        exc_info=exc,
    )
    return create_problem_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        title="Internal Server Error",
        type_uri="https://errors.carexportcrm.com/internal-error",
        detail="An unexpected server error occurred. Please contact support.",
        instance=request.url.path,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all RFC 7807 exception handlers on the FastAPI app instance."""
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
