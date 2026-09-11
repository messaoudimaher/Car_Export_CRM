"""API Integration & Security tests for Server-Side Tenant Context Isolation
(SEC-001, SEC-002, BR-001).
"""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.api.deps import get_current_tenant_id, validate_tenant_body_override
from app.core.database import get_db_session
from app.core.errors import register_exception_handlers
from app.core.security import create_access_token
from app.models.user import User, UserRole


class CreateSampleResourcePayload(BaseModel):
    name: str
    tenant_id: uuid.UUID | None = None


def create_tenant_test_app(mock_session: AsyncMock) -> FastAPI:
    """Create standalone FastAPI test app to verify tenant context security dependencies."""
    app = FastAPI(title="Tenant Security Test App")
    register_exception_handlers(app)

    async def override_get_db_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    @app.get("/api/v1/tenant/context")
    async def tenant_context_route(
        tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    ) -> dict[str, str]:
        return {"tenant_id": str(tenant_id)}

    @app.post("/api/v1/tenant/resource")
    async def create_resource_route(
        payload: CreateSampleResourcePayload,
        current_tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    ) -> dict[str, str]:
        # Validate body parameter against tenant context
        effective_tenant_id = validate_tenant_body_override(
            body_tenant_id=payload.tenant_id,
            current_tenant_id=current_tenant_id,
        )
        return {"name": payload.name, "effective_tenant_id": str(effective_tenant_id)}

    return app


@pytest.mark.asyncio
async def test_get_current_tenant_id_returns_authenticated_tenant_id() -> None:
    """Test that get_current_tenant_id extracts tenant_id from server-side JWT context."""
    mock_session = AsyncMock()
    app = create_tenant_test_app(mock_session)

    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="tenant_user@example.com",
        password_hash="hashed_pwd",  # noqa: S106
        role=UserRole.SALES_AGENT,
        is_active=True,
    )
    mock_session.get.return_value = user

    token = create_access_token(
        subject=user_id,
        tenant_id=tenant_id,
        role=UserRole.SALES_AGENT,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(
            "/api/v1/tenant/context",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json() == {"tenant_id": str(tenant_id)}


@pytest.mark.asyncio
async def test_tenant_body_override_rejection_blocks_injection_attempt() -> None:
    """Test that client body payloads supplying a conflicting tenant_id are rejected (HTTP 403)."""
    mock_session = AsyncMock()
    app = create_tenant_test_app(mock_session)

    user_id = uuid.uuid4()
    legitimate_tenant_id = uuid.uuid4()
    attacker_injected_tenant_id = uuid.uuid4()

    user = User(
        id=user_id,
        tenant_id=legitimate_tenant_id,
        email="user@tenant1.com",
        password_hash="hashed_pwd",  # noqa: S106
        role=UserRole.SALES_AGENT,
        is_active=True,
    )
    mock_session.get.return_value = user

    token = create_access_token(
        subject=user_id,
        tenant_id=legitimate_tenant_id,
        role=UserRole.SALES_AGENT,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        # Client attempts to inject attacker_injected_tenant_id in request body
        response = await client.post(
            "/api/v1/tenant/resource",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Malicious Vehicle Spec",
                "tenant_id": str(attacker_injected_tenant_id),
            },
        )

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    problem = response.json()
    assert problem["title"] == "Access Forbidden"
    assert problem["status"] == 403
    assert "Injection blocked" in problem["detail"]


@pytest.mark.asyncio
async def test_tenant_body_override_matching_or_none_succeeds() -> None:
    """Test that payloads with matching tenant_id or omit tenant_id succeed cleanly."""
    mock_session = AsyncMock()
    app = create_tenant_test_app(mock_session)

    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="user@tenant1.com",
        password_hash="hashed_pwd",  # noqa: S106
        role=UserRole.SALES_AGENT,
        is_active=True,
    )
    mock_session.get.return_value = user

    token = create_access_token(
        subject=user_id,
        tenant_id=tenant_id,
        role=UserRole.SALES_AGENT,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        # Case 1: Body supplies matching tenant_id
        res1 = await client.post(
            "/api/v1/tenant/resource",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Matching Tenant Spec",
                "tenant_id": str(tenant_id),
            },
        )
        assert res1.status_code == 200
        assert res1.json()["effective_tenant_id"] == str(tenant_id)

        # Case 2: Body omits tenant_id
        res2 = await client.post(
            "/api/v1/tenant/resource",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Omitted Tenant Spec"},
        )
        assert res2.status_code == 200
        assert res2.json()["effective_tenant_id"] == str(tenant_id)
