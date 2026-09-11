"""API Integration tests for Authentication Middleware & User Deactivation Guard
(FR-AUTH-001, FR-AUTH-002).
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db_session
from app.core.errors import register_exception_handlers
from app.core.security import create_access_token
from app.models.user import User, UserRole


def create_test_auth_app(mock_session: AsyncMock) -> FastAPI:
    """Create a standalone FastAPI app instance wired with get_current_user for auth testing."""
    app = FastAPI(title="Test Auth App")
    register_exception_handlers(app)

    async def override_get_db_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    @app.get("/api/v1/protected/me")
    async def protected_me_route(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> dict[str, str]:
        return {
            "user_id": str(current_user.user_id),
            "tenant_id": str(current_user.tenant_id),
            "role": str(current_user.role),
            "email": current_user.email,
        }

    return app


@pytest.mark.asyncio
async def test_authenticated_request_active_user_success() -> None:
    """Verify active user with valid Bearer token accesses protected endpoint (HTTP 200)."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    mock_user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="active@carexportcrm.com",
        hashed_password="$argon2id$mockhash",  # noqa: S106
        full_name="Active Agent",
        role=UserRole.SALES_AGENT,
        is_active=True,
    )

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_user

    app = create_test_auth_app(mock_session)
    token = create_access_token(subject=user_id, tenant_id=tenant_id, role=UserRole.SALES_AGENT)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/protected/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(user_id)
    assert data["tenant_id"] == str(tenant_id)
    assert data["role"] == "SalesAgent"
    assert data["email"] == "active@carexportcrm.com"


@pytest.mark.asyncio
async def test_deactivated_user_token_rejection() -> None:
    """Verify deactivated user (is_active=False) is rejected with HTTP 401 (FR-AUTH-002)."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    mock_deactivated_user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="deactivated@carexportcrm.com",
        hashed_password="$argon2id$mockhash",  # noqa: S106
        full_name="Deactivated Agent",
        role=UserRole.SALES_AGENT,
        is_active=False,
    )

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_deactivated_user

    app = create_test_auth_app(mock_session)
    token = create_access_token(subject=user_id, tenant_id=tenant_id, role=UserRole.SALES_AGENT)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/protected/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401
    data = response.json()
    assert "deactivated" in data["detail"].lower()


@pytest.mark.asyncio
async def test_missing_authorization_header_rejection() -> None:
    """Verify request missing Authorization header returns HTTP 401."""
    mock_session = AsyncMock()
    app = create_test_auth_app(mock_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/protected/me")

    assert response.status_code == 401
    data = response.json()
    assert "Bearer token required" in data["detail"]


@pytest.mark.asyncio
async def test_expired_token_rejection() -> None:
    """Verify expired token returns HTTP 401 with RFC 7807 envelope."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    mock_session = AsyncMock()
    app = create_test_auth_app(mock_session)

    expired_token = create_access_token(
        subject=user_id,
        tenant_id=tenant_id,
        role=UserRole.SALES_AGENT,
        expires_delta=timedelta(seconds=-10),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/protected/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

    assert response.status_code == 401
    data = response.json()
    assert "expired" in data["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_token_signature_rejection() -> None:
    """Verify invalid or tampered Bearer token signature returns HTTP 401."""
    mock_session = AsyncMock()
    app = create_test_auth_app(mock_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/protected/me",
            headers={"Authorization": "Bearer invalid_tampered_token_string"},
        )

    assert response.status_code == 401
    data = response.json()
    assert "invalid" in data["detail"].lower()
