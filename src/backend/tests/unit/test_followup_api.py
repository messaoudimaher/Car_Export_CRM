"""API integration tests for Follow-Up endpoints (WS-14, TASK-1402)."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.api.v1.router import api_v1_router
from app.core.database import get_db_session
from app.models.followup import FollowUp, FollowUpStatus
from app.models.lead import Lead, LeadStatus
from app.models.user import UserRole


@pytest.fixture
def test_app() -> FastAPI:
    """Create test FastAPI application with API v1 router attached."""
    app = FastAPI(title="FollowUp Test App")
    app.include_router(api_v1_router)
    return app


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """AsyncMock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_create_followup_endpoint(
    test_app: FastAPI,
    mock_db_session: AsyncMock,
) -> None:
    """Verify POST /api/v1/followups creates a new follow-up task."""
    tenant_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    lead_id = uuid.uuid4()

    agent_user = CurrentUser(
        user_id=agent_id,
        tenant_id=tenant_id,
        role=UserRole.SALES_AGENT.value,
        email="agent@test.com",
        is_active=True,
    )

    mock_lead = Lead(id=lead_id, tenant_id=tenant_id, status=LeadStatus.NEW.value)
    lead_result = MagicMock()
    lead_result.scalar_one_or_none.return_value = mock_lead
    mock_db_session.execute = AsyncMock(return_value=lead_result)

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield mock_db_session

    test_app.dependency_overrides[get_db_session] = override_db
    test_app.dependency_overrides[get_current_user] = lambda: agent_user

    due_at = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    payload = {
        "lead_id": str(lead_id),
        "title": "Call customer regarding shipping options",
        "due_at": due_at,
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/followups",
            json=payload,
            headers={"Authorization": "Bearer mock_token"},
        )

    test_app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Call customer regarding shipping options"
    assert data["status"] == FollowUpStatus.PENDING.value


@pytest.mark.asyncio
async def test_complete_followup_endpoint(
    test_app: FastAPI,
    mock_db_session: AsyncMock,
) -> None:
    """Verify POST /api/v1/followups/{id}/complete marks task completed."""
    tenant_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    task_id = uuid.uuid4()

    agent_user = CurrentUser(
        user_id=agent_id,
        tenant_id=tenant_id,
        role=UserRole.SALES_AGENT.value,
        email="agent@test.com",
        is_active=True,
    )

    mock_task = FollowUp(
        id=task_id,
        tenant_id=tenant_id,
        lead_id=uuid.uuid4(),
        title="Check FCR document status",
        due_at=datetime.now(UTC),
        status=FollowUpStatus.PENDING.value,
    )
    task_result = MagicMock()
    task_result.scalar_one_or_none.return_value = mock_task
    mock_db_session.execute = AsyncMock(return_value=task_result)

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield mock_db_session

    test_app.dependency_overrides[get_db_session] = override_db
    test_app.dependency_overrides[get_current_user] = lambda: agent_user

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/api/v1/followups/{task_id}/complete",
            headers={"Authorization": "Bearer mock_token"},
        )

    test_app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == FollowUpStatus.COMPLETED.value
    assert data["completed_at"] is not None
