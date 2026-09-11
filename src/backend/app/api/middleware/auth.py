"""Authentication & Context Binding Middleware (SEC-001)."""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import set_tenant_id, set_user_id
from app.core.security import decode_access_token


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware extracting JWT Bearer token claims and populating request state & context."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1]
            try:
                claims = decode_access_token(token)
                user_id = claims.get("sub")
                tenant_id = claims.get("tenant_id")
                if user_id:
                    set_user_id(str(user_id))
                    request.state.user_id = str(user_id)
                if tenant_id:
                    set_tenant_id(str(tenant_id))
                    request.state.tenant_id = str(tenant_id)
            except Exception:  # noqa: S110
                # Invalid tokens are caught cleanly by get_current_user dependency
                pass

        return await call_next(request)
