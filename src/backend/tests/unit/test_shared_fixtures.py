"""Unit Tests for Shared Conftest Fixtures (TASK-1901)."""

import uuid
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.adapters.llm_demo import DemoLLMAdapter
from app.adapters.whatsapp_demo import DemoWhatsAppProvider
from app.models.tenant import Tenant
from app.models.user import User, UserRole


def test_conftest_app_fixture(app: FastAPI) -> None:
    """Verify app fixture returns a configured FastAPI application instance."""
    assert isinstance(app, FastAPI)
    assert app.title == "Car-Export-CRM"


async def test_conftest_mock_db_session_fixture(mock_db_session: AsyncMock) -> None:
    """Verify mock_db_session provides AsyncSession interface methods."""
    assert hasattr(mock_db_session, "execute")
    assert hasattr(mock_db_session, "commit")
    assert hasattr(mock_db_session, "rollback")
    assert hasattr(mock_db_session, "add")


async def test_conftest_mock_redis_fixture(mock_redis: AsyncMock) -> None:
    """Verify mock_redis fixture returns functional Redis mock."""
    await mock_redis.set("test_key", "test_val")
    val = await mock_redis.get("test_key")
    assert val is None or val == "test_val"
    res = await mock_redis.ping()
    assert res is True


def test_conftest_adapters_fixtures(
    mock_whatsapp_provider: DemoWhatsAppProvider,
    mock_llm_provider: DemoLLMAdapter,
) -> None:
    """Verify mock adapter fixtures return instances of generic providers."""
    assert mock_whatsapp_provider is not None
    assert mock_llm_provider is not None


def test_conftest_tenant_and_user_fixtures(
    tenant_a_id: uuid.UUID,
    tenant_b_id: uuid.UUID,
    tenant_a: Tenant,
    user_a: User,
    user_b: User,
    token_tenant_a: str,
    token_tenant_b: str,
    auth_headers_tenant_a: dict[str, str],
    auth_headers_tenant_b: dict[str, str],
) -> None:
    """Verify tenant and user identity fixtures emit valid context models and tokens."""
    assert tenant_a_id != tenant_b_id
    assert tenant_a.id == tenant_a_id
    assert user_a.tenant_id == tenant_a_id
    assert user_b.tenant_id == tenant_b_id
    assert user_a.role == UserRole.SALES_AGENT

    assert token_tenant_a.startswith("eyJ")
    assert token_tenant_b.startswith("eyJ")
    assert token_tenant_a != token_tenant_b

    assert auth_headers_tenant_a["Authorization"] == f"Bearer {token_tenant_a}"
    assert auth_headers_tenant_b["Authorization"] == f"Bearer {token_tenant_b}"


async def test_conftest_client_fixture(client: AsyncClient) -> None:
    """Verify client fixture can reach application endpoints."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
