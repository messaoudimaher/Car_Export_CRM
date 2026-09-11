"""API Integration tests for Role-Based Access Control (RBAC) Permission Guard (require_roles)."""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import CurrentUser, require_roles
from app.core.database import get_db_session
from app.core.errors import register_exception_handlers
from app.core.security import create_access_token
from app.models.user import User, UserRole


def create_rbac_test_app(mock_session: AsyncMock) -> FastAPI:
    """Create a standalone FastAPI app instance wired with RBAC dependencies for testing."""
    app = FastAPI(title="RBAC Test App")
    register_exception_handlers(app)

    async def override_get_db_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    @app.get("/api/v1/admin/dashboard")
    async def admin_dashboard_route(
        current_user: CurrentUser = Depends(
            require_roles(UserRole.TENANT_ADMIN, UserRole.SUPER_ADMIN)
        ),
    ) -> dict[str, str]:
        return {
            "user_id": str(current_user.user_id),
            "role": str(
                current_user.role.value
                if isinstance(current_user.role, UserRole)
                else current_user.role
            ),
        }

    @app.get("/api/v1/logistics/shipments")
    async def logistics_shipments_route(
        current_user: CurrentUser = Depends(
            require_roles(UserRole.LOGISTICS_AGENT, UserRole.TENANT_ADMIN)
        ),
    ) -> dict[str, str]:
        return {"access": "granted"}

    return app


@pytest.mark.asyncio
async def test_require_roles_allows_authorized_role() -> None:
    """Test that a user with an authorized role is granted access (200 OK)."""
    mock_session = AsyncMock()
    app = create_rbac_test_app(mock_session)

    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    admin_user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="admin@example.com",
        password_hash="hashed_pwd",  # noqa: S106
        role=UserRole.TENANT_ADMIN,
        is_active=True,
    )
    mock_session.get.return_value = admin_user

    token = create_access_token(
        subject=user_id,
        tenant_id=tenant_id,
        role=UserRole.TENANT_ADMIN,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(
            "/api/v1/admin/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(user_id)
    assert data["role"] == "TenantAdmin"


@pytest.mark.asyncio
async def test_require_roles_rejects_unauthorized_role() -> None:
    """Test that a user with an unauthorized role is rejected with 403 Forbidden RFC 7807."""
    mock_session = AsyncMock()
    app = create_rbac_test_app(mock_session)

    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    sales_user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="sales@example.com",
        password_hash="hashed_pwd",  # noqa: S106
        role=UserRole.SALES_AGENT,
        is_active=True,
    )
    mock_session.get.return_value = sales_user

    token = create_access_token(
        subject=user_id,
        tenant_id=tenant_id,
        role=UserRole.SALES_AGENT,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(
            "/api/v1/admin/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    problem = response.json()
    assert problem["title"] == "Access Forbidden"
    assert problem["status"] == 403
    assert "SalesAgent" in problem["detail"]


@pytest.mark.asyncio
async def test_require_roles_allows_multiple_roles() -> None:
    """Test that require_roles permits any role listed in allowed_roles."""
    mock_session = AsyncMock()
    app = create_rbac_test_app(mock_session)

    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    logistics_user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="logistics@example.com",
        password_hash="hashed_pwd",  # noqa: S106
        role=UserRole.LOGISTICS_AGENT,
        is_active=True,
    )
    mock_session.get.return_value = logistics_user

    token = create_access_token(
        subject=user_id,
        tenant_id=tenant_id,
        role=UserRole.LOGISTICS_AGENT,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(
            "/api/v1/logistics/shipments",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json() == {"access": "granted"}
