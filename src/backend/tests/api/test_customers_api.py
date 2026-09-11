"""API Integration tests for Customer REST Endpoints (ADR 0008, ADR 0009)."""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db_session
from app.core.security import create_access_token
from app.main import create_app
from app.models.customer import Customer
from app.models.user import User, UserRole


def create_customer_test_app(mock_session: AsyncMock) -> FastAPI:
    """Create FastAPI application bound to mock DB session for Customer API tests."""
    app = create_app()

    async def override_get_db_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    return app


@pytest.mark.asyncio
async def test_create_customer_endpoint_success() -> None:
    """Verify POST /api/v1/customers creates customer and returns standard envelope."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    app = create_customer_test_app(mock_session)

    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="agent@export.de",
        password_hash="pwd_hash",  # noqa: S106
        role=UserRole.SALES_AGENT,
        is_active=True,
    )
    mock_session.get.return_value = user

    # Mock execute for find_one (returns None -> no existing customer)
    exec_result_mock = MagicMock()
    exec_result_mock.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = exec_result_mock

    token = create_access_token(
        subject=user_id,
        tenant_id=tenant_id,
        role=UserRole.SALES_AGENT,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/v1/customers",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "phone": "098123456",
                "full_name": "Sami Ayari",
                "email": "sami@domain.tn",
                "preferred_language": "fr",
                "fcr_eligible": True,
            },
        )

    assert response.status_code == 201
    json_data = response.json()
    assert json_data["success"] is True
    data = json_data["data"]
    assert data["phone_e164"] == "+21698123456"
    assert data["whatsapp_id"] == "21698123456"
    assert data["full_name"] == "Sami Ayari"
    assert data["email"] == "sami@domain.tn"
    assert data["fcr_eligible"] is True


@pytest.mark.asyncio
async def test_list_customers_unrecognized_query_param_rejected() -> None:
    """Verify GET /api/v1/customers rejects non-whitelisted query params with HTTP 400."""
    mock_session = AsyncMock()
    app = create_customer_test_app(mock_session)

    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="agent@export.de",
        password_hash="pwd_hash",  # noqa: S106
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
            "/api/v1/customers?unsupported_filter=123",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    problem = response.json()
    assert problem["status"] == 422
    assert "Unrecognized" in problem["detail"]


@pytest.mark.asyncio
async def test_get_customer_by_id_endpoint_success() -> None:
    """Verify GET /api/v1/customers/{id} returns customer details."""
    mock_session = AsyncMock()
    app = create_customer_test_app(mock_session)

    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    customer_id = uuid.uuid4()

    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="agent@export.de",
        password_hash="pwd_hash",  # noqa: S106
        role=UserRole.SALES_AGENT,
        is_active=True,
    )
    existing_customer = Customer(
        id=customer_id,
        tenant_id=tenant_id,
        phone_e164="+21698123456",
        whatsapp_id="21698123456",
        full_name="Youssef Ben Salem",
    )

    mock_session.get.return_value = user

    exec_result_mock = MagicMock()
    exec_result_mock.scalar_one_or_none.return_value = existing_customer
    mock_session.execute.return_value = exec_result_mock

    token = create_access_token(
        subject=user_id,
        tenant_id=tenant_id,
        role=UserRole.SALES_AGENT,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(
            f"/api/v1/customers/{customer_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    assert json_data["data"]["id"] == str(customer_id)
    assert json_data["data"]["full_name"] == "Youssef Ben Salem"


@pytest.mark.asyncio
async def test_patch_customer_endpoint_success() -> None:
    """Verify PATCH /api/v1/customers/{id} updates customer attributes."""
    mock_session = AsyncMock()
    app = create_customer_test_app(mock_session)

    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    customer_id = uuid.uuid4()

    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="agent@export.de",
        password_hash="pwd_hash",  # noqa: S106
        role=UserRole.SALES_AGENT,
        is_active=True,
    )
    existing_customer = Customer(
        id=customer_id,
        tenant_id=tenant_id,
        phone_e164="+21698123456",
        whatsapp_id="21698123456",
        full_name="Youssef Ben Salem",
        fcr_eligible=False,
    )

    mock_session.get.return_value = user

    exec_result_mock = MagicMock()
    exec_result_mock.scalar_one_or_none.return_value = existing_customer
    mock_session.execute.return_value = exec_result_mock
    mock_session.merge.side_effect = lambda c: c

    token = create_access_token(
        subject=user_id,
        tenant_id=tenant_id,
        role=UserRole.SALES_AGENT,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.patch(
            f"/api/v1/customers/{customer_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "fcr_eligible": True,
                "notes": "FCR tax privilege document submitted.",
            },
        )

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    assert json_data["data"]["fcr_eligible"] is True
    assert json_data["data"]["notes"] == "FCR tax privilege document submitted."
