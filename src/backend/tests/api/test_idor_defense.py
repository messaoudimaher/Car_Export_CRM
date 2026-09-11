"""API Integration & Security tests for IDOR Defense & 404 Response Masking (SEC-010, AC-01)."""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_tenant_id
from app.core.database import get_db_session
from app.core.errors import register_exception_handlers
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.repositories.tenant_base import TenantRepository


def create_idor_test_app(mock_session: AsyncMock) -> FastAPI:
    """Create standalone FastAPI test app to verify IDOR 404 response masking."""
    app = FastAPI(title="IDOR Defense Test App")
    register_exception_handlers(app)

    async def override_get_db_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    @app.get("/api/v1/users/{user_id}")
    async def get_user_by_id_route(
        user_id: uuid.UUID,
        tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    ) -> dict[str, str]:
        repo = TenantRepository(mock_session, User, tenant_id=tenant_id)
        target_user = await repo.get_or_raise(user_id)
        return {"id": str(target_user.id), "email": target_user.email}

    return app


@pytest.mark.asyncio
async def test_cross_tenant_resource_fetch_returns_404_not_found() -> None:
    """Test that requesting a resource ID belonging to Tenant B returns 404 Not Found (SEC-010)."""
    mock_session = AsyncMock()
    app = create_idor_test_app(mock_session)

    user_a_id = uuid.uuid4()
    tenant_a_id = uuid.uuid4()

    user_b_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    user_a = User(
        id=user_a_id,
        tenant_id=tenant_a_id,
        email="user_a@tenant1.com",
        password_hash="hashed_pwd",  # noqa: S106
        role=UserRole.SALES_AGENT,
        is_active=True,
    )
    user_b = User(
        id=user_b_id,
        tenant_id=tenant_b_id,
        email="user_b@tenant2.com",
        password_hash="hashed_pwd",  # noqa: S106
        role=UserRole.SALES_AGENT,
        is_active=True,
    )

    # Database mock returns user_a for authentication lookup
    mock_session.get.return_value = user_a

    # For get_by_id (Tenant A scope), return None (since user_b belongs to Tenant B)
    # For global fallback check, return user_b
    class MockResultGetByIdNone:
        def scalar_one_or_none(self) -> User | None:
            return None

    class MockResultGlobalUserB:
        def scalar_one_or_none(self) -> User | None:
            return user_b

    mock_session.execute.side_effect = [MockResultGetByIdNone(), MockResultGlobalUserB()]

    token_a = create_access_token(
        subject=user_a_id,
        tenant_id=tenant_a_id,
        role=UserRole.SALES_AGENT,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        # User A attempts to access User B's resource ID
        response = await client.get(
            f"/api/v1/users/{user_b_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )

    # Must return 404 Not Found (RFC 7807 problem details) rather than 403 Forbidden
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    problem = response.json()
    assert problem["title"] == "Resource Not Found"
    assert problem["status"] == 404
