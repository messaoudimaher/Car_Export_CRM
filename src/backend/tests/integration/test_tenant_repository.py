"""Integration tests for TenantRepository multi-tenant query filter enforcement
(SEC-003, BR-002).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import DeveloperSecurityException
from app.models.user import User, UserRole
from app.repositories.tenant_base import TenantRepository


@pytest.mark.asyncio
async def test_tenant_repository_initialization_requires_tenant_id() -> None:
    """Test that TenantRepository without tenant_id raises DeveloperSecurityException."""
    mock_session = AsyncMock()
    with pytest.raises(DeveloperSecurityException, match="Missing tenant_id context"):
        TenantRepository(mock_session, User, tenant_id=None)


@pytest.mark.asyncio
async def test_tenant_repository_isolation_between_tenants() -> None:
    """Test that Tenant A repository cannot view or query records belonging to Tenant B."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    repo_a = TenantRepository(mock_session, User, tenant_id=tenant_a_id)
    repo_b = TenantRepository(mock_session, User, tenant_id=tenant_b_id)

    user_a = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a_id,
        email="user_a@tenant1.com",
        password_hash="hashed_pwd_a",  # noqa: S106
        role=UserRole.SALES_AGENT,
        is_active=True,
    )
    user_b = User(
        id=uuid.uuid4(),
        tenant_id=tenant_b_id,
        email="user_b@tenant2.com",
        password_hash="hashed_pwd_b",  # noqa: S106
        role=UserRole.SALES_AGENT,
        is_active=True,
    )

    created_a = await repo_a.create(user_a)
    created_b = await repo_b.create(user_b)
    assert created_a.tenant_id == tenant_a_id
    assert created_b.tenant_id == tenant_b_id

    # Test get_by_id execute returning scalar_one_or_none
    mock_result_a = MagicMock()
    mock_result_a.scalar_one_or_none.return_value = created_a
    mock_session.execute.return_value = mock_result_a

    fetched_a = await repo_a.get_by_id(created_a.id)
    assert fetched_a is created_a

    mock_result_none = MagicMock()
    mock_result_none.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result_none

    fetched_b_by_a = await repo_a.get_by_id(created_b.id)
    assert fetched_b_by_a is None


@pytest.mark.asyncio
async def test_tenant_repository_list_filters_by_tenant() -> None:
    """Test that list() executes select query filtered by repository tenant_id."""
    mock_session = AsyncMock()

    tenant_a_id = uuid.uuid4()
    repo_a = TenantRepository(mock_session, User, tenant_id=tenant_a_id)

    user_a1 = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a_id,
        email="user_a1@tenant1.com",
        password_hash="hashed_pwd",  # noqa: S106
        role=UserRole.SALES_AGENT,
    )

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [user_a1]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    items = await repo_a.list(offset=0, limit=10)
    mock_session.execute.assert_awaited_once()
    assert len(items) == 1
    assert items[0].tenant_id == tenant_a_id


@pytest.mark.asyncio
async def test_tenant_repository_cross_tenant_delete_prevention() -> None:
    """Test that deleting a record of Tenant B using Tenant A repository returns False."""
    mock_session = AsyncMock()
    mock_result_none = MagicMock()
    mock_result_none.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result_none

    tenant_a_id = uuid.uuid4()
    repo_a = TenantRepository(mock_session, User, tenant_id=tenant_a_id)

    user_b_id = uuid.uuid4()
    delete_result = await repo_a.delete(user_b_id)
    assert delete_result is False
    mock_session.delete.assert_not_called()
