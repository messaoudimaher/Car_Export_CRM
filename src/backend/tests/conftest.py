"""Pytest Configuration & Shared Fixtures (TASK-1901).

Provides isolated test DB sessions, mock Redis, mock WhatsApp adapters,
mock LLM providers, tenant/user authentication contexts, and AsyncClient fixtures.
"""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm_demo import DemoLLMAdapter
from app.adapters.whatsapp_demo import DemoWhatsAppProvider
from app.core.security import create_access_token
from app.main import create_app
from app.models.tenant import Tenant
from app.models.user import User, UserRole


@pytest.fixture(autouse=True)
async def dispose_engine_on_teardown() -> AsyncGenerator[None, None]:
    """Dispose the engine connections after each test to prevent event loop connection leakage."""
    yield
    from app.core.database import async_engine
    await async_engine.dispose()


@pytest.fixture
def app() -> FastAPI:
    """Return an instance of the FastAPI application."""
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Return an unauthenticated AsyncClient bound to the FastAPI ASGI application."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated database session for integration tests."""
    from app.core.database import async_session_factory
    async with async_session_factory() as session:
        yield session


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Return a mocked async database session for unit testing."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.get = AsyncMock()
    return session


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Return a mocked Redis client for caching and task queue testing."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.ping = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def mock_whatsapp_provider() -> DemoWhatsAppProvider:
    """Return a mock/demo WhatsApp provider instance."""
    return DemoWhatsAppProvider()


@pytest.fixture
def mock_llm_provider() -> DemoLLMAdapter:
    """Return a mock/demo LLM provider instance."""
    return DemoLLMAdapter()


@pytest.fixture
def tenant_a_id() -> uuid.UUID:
    """Return a deterministic UUID for Tenant A."""
    return uuid.UUID("11111111-1111-7111-8111-111111111111")


@pytest.fixture
def tenant_b_id() -> uuid.UUID:
    """Return a deterministic UUID for Tenant B."""
    return uuid.UUID("22222222-2222-7222-8222-222222222222")


@pytest.fixture
def tenant_a(tenant_a_id: uuid.UUID) -> Tenant:
    """Return a Tenant model instance for Tenant A."""
    return Tenant(
        id=tenant_a_id,
        name="Auto Export Europe SARL",
        slug="auto-export-europe",
        is_active=True,
    )


@pytest.fixture
def user_a(tenant_a_id: uuid.UUID) -> User:
    """Return an active User model instance under Tenant A."""
    return User(
        id=uuid.UUID("a1111111-1111-7111-8111-111111111111"),
        tenant_id=tenant_a_id,
        email="agent_a@autoexport.com",
        hashed_password="$argon2id$v=19$m=65536,t=3,p=4$dummyhash",
        full_name="Sales Agent A",
        role=UserRole.SALES_AGENT,
        is_active=True,
    )


@pytest.fixture
def user_b(tenant_b_id: uuid.UUID) -> User:
    """Return an active User model instance under Tenant B."""
    return User(
        id=uuid.UUID("b2222222-2222-7222-8222-222222222222"),
        tenant_id=tenant_b_id,
        email="agent_b@competitor.com",
        hashed_password="$argon2id$v=19$m=65536,t=3,p=4$dummyhash",
        full_name="Sales Agent B",
        role=UserRole.SALES_AGENT,
        is_active=True,
    )


@pytest.fixture
def token_tenant_a(user_a: User) -> str:
    """Return a valid JWT access token for User A under Tenant A context."""
    return create_access_token(
        subject=str(user_a.id),
        tenant_id=str(user_a.tenant_id),
        role=user_a.role.value,
    )


@pytest.fixture
def token_tenant_b(user_b: User) -> str:
    """Return a valid JWT access token for User B under Tenant B context."""
    return create_access_token(
        subject=str(user_b.id),
        tenant_id=str(user_b.tenant_id),
        role=user_b.role.value,
    )


@pytest.fixture
def auth_headers_tenant_a(token_tenant_a: str) -> dict[str, str]:
    """Return HTTP Authorization headers for Tenant A user."""
    return {"Authorization": f"Bearer {token_tenant_a}"}


@pytest.fixture
def auth_headers_tenant_b(token_tenant_b: str) -> dict[str, str]:
    """Return HTTP Authorization headers for Tenant B user."""
    return {"Authorization": f"Bearer {token_tenant_b}"}
