"""FastAPI Request Dependencies & CurrentUser Authentication Injection."""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.errors import ForbiddenException, UnauthorizedException
from app.core.security import decode_access_token
from app.models.user import User, UserRole

security_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    """Authenticated user context attached to request state & dependencies."""

    user_id: UUID
    tenant_id: UUID
    role: UserRole | str
    email: str
    is_active: bool


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> CurrentUser:
    """FastAPI dependency verifying Bearer token & active user status (FR-AUTH-001, FR-AUTH-002).

    Args:
        credentials: Expected HTTP Bearer Authorization credentials.
        session: Scoped async database session.

    Raises:
        UnauthorizedException: If token is missing, expired, invalid, or user is deactivated.

    Returns:
        CurrentUser: Authenticated user context.
    """
    if not credentials or credentials.scheme.lower() != "bearer":
        raise UnauthorizedException(
            "Missing or invalid Authorization header. Bearer token required."
        )

    token = credentials.credentials
    claims = decode_access_token(token)

    try:
        user_id = UUID(claims["sub"])
        _tenant_id = UUID(claims["tenant_id"])
        _role = claims.get("role", UserRole.SALES_AGENT)
    except (KeyError, ValueError) as e:
        raise UnauthorizedException("Invalid token payload structure.") from e

    # Retrieve user from database to verify active status (FR-AUTH-002)
    user = await session.get(User, user_id)
    if not user:
        raise UnauthorizedException("User account associated with this token does not exist.")

    if not user.is_active:
        raise UnauthorizedException("User account has been deactivated. Access denied.")

    return CurrentUser(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
        email=user.email,
        is_active=user.is_active,
    )


def require_roles(*allowed_roles: UserRole | str) -> Callable[[CurrentUser], CurrentUser]:
    """Dependency factory returning a dependency that enforces RBAC authorization.

    Args:
        *allowed_roles: One or more permitted UserRoles or role strings.

    Returns:
        Callable[[CurrentUser], CurrentUser]: FastAPI dependency returning CurrentUser if permitted
            or raising ForbiddenException (HTTP 403) if unauthorized.
    """

    def role_checker(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        user_role_val = (
            current_user.role.value
            if isinstance(current_user.role, UserRole)
            else str(current_user.role)
        )
        allowed_str_list = [
            role.value if isinstance(role, UserRole) else str(role) for role in allowed_roles
        ]
        if user_role_val not in allowed_str_list:
            raise ForbiddenException(
                f"User role '{user_role_val}' is not authorized to access this resource."
            )
        return current_user

    return role_checker


def get_current_tenant_id(current_user: CurrentUser = Depends(get_current_user)) -> UUID:
    """Extract authenticated tenant_id from server-side credentials (SEC-001, SEC-002).

    Args:
        current_user: Authenticated user context.

    Returns:
        UUID: Verified tenant_id belonging to the authenticated user.
    """
    return (
        current_user.tenant_id
        if isinstance(current_user.tenant_id, UUID)
        else UUID(str(current_user.tenant_id))
    )


def validate_tenant_body_override(
    body_tenant_id: UUID | str | None = None,
    current_tenant_id: UUID = Depends(get_current_tenant_id),
) -> UUID:
    """Validate that body payloads do not attempt to override tenant context (SEC-001).

    If body_tenant_id is supplied by client, it MUST match authenticated current_tenant_id.
    If it differs, a ForbiddenException (HTTP 403) is raised to block tenant injection.

    Args:
        body_tenant_id: Optional tenant_id field provided in client payload body.
        current_tenant_id: Server-side authenticated tenant_id.

    Raises:
        ForbiddenException: If client attempts to specify a conflicting tenant_id.

    Returns:
        UUID: Verified server-side tenant_id.
    """
    if body_tenant_id is not None:
        supplied = str(body_tenant_id)
        authenticated = str(current_tenant_id)
        if supplied != authenticated:
            raise ForbiddenException(
                "Client tenant_id does not match authenticated context. Injection blocked."
            )
    return current_tenant_id

