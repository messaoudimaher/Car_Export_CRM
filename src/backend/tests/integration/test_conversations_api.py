"""Integration tests for Inbox & Conversations REST API endpoints (TASK-0703)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient

from app.api.deps import CurrentUser, get_current_user, get_whatsapp_provider
from app.core.config import settings
from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
from app.models.message import Message
from app.models.user import User, UserRole
from app.ports.whatsapp import OutboundWhatsAppMessageResult, WhatsAppProvider


@pytest.fixture
def test_tenant_id() -> uuid.UUID:
    """Return a consistent tenant UUID for API testing."""
    return uuid.uuid4()


@pytest.fixture
def test_user_id() -> uuid.UUID:
    """Return a consistent sales agent user UUID for API testing."""
    return uuid.uuid4()


@pytest.fixture
def sales_agent_user(test_user_id: uuid.UUID, test_tenant_id: uuid.UUID) -> CurrentUser:
    """Return CurrentUser authenticated context with SalesAgent role."""
    return CurrentUser(
        user_id=test_user_id,
        tenant_id=test_tenant_id,
        role=UserRole.SALES_AGENT,
        email="agent@carexport.com",
        is_active=True,
    )


@pytest.fixture
def mock_whatsapp_provider() -> MagicMock:
    """Return a mock WhatsAppProvider port."""
    provider = MagicMock(spec=WhatsAppProvider)
    provider.send_text_message = AsyncMock(
        return_value=OutboundWhatsAppMessageResult(
            wamid="wamid.OUTBOUND123",
            recipient_e164="+21698123456",
            status="sent",
        )
    )
    return provider


@pytest.mark.asyncio
async def test_list_conversations_unauthenticated_returns_401(app: FastAPI) -> None:
    """Verify unauthenticated GET /api/v1/conversations returns HTTP 401 Unauthorized."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/conversations")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        json_resp = response.json()
        assert json_resp["status"] == status.HTTP_401_UNAUTHORIZED
        assert json_resp["title"] == "Authentication Required"


@pytest.mark.asyncio
async def test_list_conversations_success_and_envelope(
    app: FastAPI, sales_agent_user: CurrentUser, test_tenant_id: uuid.UUID
) -> None:
    """Verify GET /api/v1/conversations returns list envelope with metadata."""
    app.dependency_overrides[get_current_user] = lambda: sales_agent_user

    mock_conv1 = WhatsAppConversation(
        id=uuid.uuid4(),
        tenant_id=test_tenant_id,
        customer_id=uuid.uuid4(),
        status="PendingAgent",
        unread_count=3,
        last_message_at=datetime.now(UTC),
    )

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.merge = AsyncMock(side_effect=lambda e: e)

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_conv1]

    mock_execute_res = MagicMock()
    mock_execute_res.scalars.return_value = mock_scalars

    mock_db.scalar = AsyncMock(return_value=1)
    mock_db.execute = AsyncMock(return_value=mock_execute_res)

    from app.core.database import get_db_session

    app.dependency_overrides[get_db_session] = lambda: mock_db

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get("/api/v1/conversations")
            assert response.status_code == status.HTTP_200_OK
            payload = response.json()
            assert payload["success"] is True
            assert len(payload["data"]) == 1
            assert payload["data"][0]["id"] == str(mock_conv1.id)
            assert payload["data"][0]["status"] == "PendingAgent"
            assert payload["meta"]["limit"] == 25
            assert payload["meta"]["total"] == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_conversation_by_id(
    app: FastAPI, sales_agent_user: CurrentUser, test_tenant_id: uuid.UUID
) -> None:
    """Verify GET /api/v1/conversations/{id} returns conversation details."""
    conv_id = uuid.uuid4()
    mock_conv = WhatsAppConversation(
        id=conv_id,
        tenant_id=test_tenant_id,
        customer_id=uuid.uuid4(),
        status="Active",
        unread_count=0,
        last_message_at=datetime.now(UTC),
    )

    app.dependency_overrides[get_current_user] = lambda: sales_agent_user

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.merge = AsyncMock(side_effect=lambda e: e)

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_conv]
    mock_exec_res = MagicMock()
    mock_exec_res.scalar_one_or_none.return_value = mock_conv
    mock_db.execute = AsyncMock(return_value=mock_exec_res)

    from app.core.database import get_db_session

    app.dependency_overrides[get_db_session] = lambda: mock_db

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get(f"/api/v1/conversations/{conv_id}")
            assert response.status_code == status.HTTP_200_OK
            payload = response.json()
            assert payload["success"] is True
            assert payload["data"]["id"] == str(conv_id)
            assert payload["data"]["status"] == "Active"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_assign_conversation_agent(
    app: FastAPI, sales_agent_user: CurrentUser, test_tenant_id: uuid.UUID
) -> None:
    """Verify POST /api/v1/conversations/{id}/assign updates assigned agent."""
    conv_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    mock_conv = WhatsAppConversation(
        id=conv_id,
        tenant_id=test_tenant_id,
        customer_id=uuid.uuid4(),
        status="PendingAgent",
        assigned_agent_id=None,
    )
    mock_agent_user = User(id=agent_id, tenant_id=test_tenant_id, email="agent@carexport.com")

    app.dependency_overrides[get_current_user] = lambda: sales_agent_user

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.merge = AsyncMock(side_effect=lambda e: e)

    res_conv = MagicMock()
    res_conv.scalar_one_or_none.return_value = mock_conv

    res_agent = MagicMock()
    res_agent.scalar_one_or_none.return_value = mock_agent_user

    # side_effect: get_conversation (conv), get_user (agent), update_conversation (conv)
    mock_db.execute = AsyncMock(side_effect=[res_conv, res_agent, res_conv])

    from app.core.database import get_db_session

    app.dependency_overrides[get_db_session] = lambda: mock_db

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(
                f"/api/v1/conversations/{conv_id}/assign",
                json={"agent_id": str(agent_id)},
            )
            assert response.status_code == status.HTTP_200_OK
            payload = response.json()
            assert payload["success"] is True
            assert payload["data"]["assigned_agent_id"] == str(agent_id)
            assert payload["data"]["status"] == "Active"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_messages_timeline(
    app: FastAPI, sales_agent_user: CurrentUser, test_tenant_id: uuid.UUID
) -> None:
    """Verify GET /api/v1/conversations/{id}/messages returns chat history envelope."""
    conv_id = uuid.uuid4()
    mock_conv = WhatsAppConversation(id=conv_id, tenant_id=test_tenant_id)
    msg1 = Message(
        id=uuid.uuid4(),
        tenant_id=test_tenant_id,
        conversation_id=conv_id,
        direction="Inbound",
        sender_type="Customer",
        content="Bonjour, je cherche une Golf 8",
    )

    app.dependency_overrides[get_current_user] = lambda: sales_agent_user

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.merge = AsyncMock(side_effect=lambda e: e)

    mock_exec_res = MagicMock()
    mock_exec_res.scalar_one_or_none.return_value = mock_conv

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [msg1]
    mock_messages_res = MagicMock()
    mock_messages_res.scalars.return_value = mock_scalars

    mock_db.scalar = AsyncMock(return_value=1)
    mock_db.execute = AsyncMock(side_effect=[mock_exec_res, mock_messages_res])

    from app.core.database import get_db_session

    app.dependency_overrides[get_db_session] = lambda: mock_db

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get(f"/api/v1/conversations/{conv_id}/messages")
            assert response.status_code == status.HTTP_200_OK
            payload = response.json()
            assert payload["success"] is True
            assert len(payload["data"]) == 1
            assert payload["data"][0]["content"] == "Bonjour, je cherche une Golf 8"
            assert payload["meta"]["total"] == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_outbound_whatsapp_message(
    app: FastAPI,
    sales_agent_user: CurrentUser,
    test_tenant_id: uuid.UUID,
    mock_whatsapp_provider: MagicMock,
) -> None:
    """Verify POST /api/v1/conversations/{id}/messages dispatches outbound message."""
    conv_id = uuid.uuid4()
    cust_id = uuid.uuid4()
    mock_conv = WhatsAppConversation(id=conv_id, tenant_id=test_tenant_id, customer_id=cust_id)
    mock_cust = Customer(id=cust_id, tenant_id=test_tenant_id, phone_e164="+21698123456")
    mock_sender_user = User(
        id=sales_agent_user.user_id,
        tenant_id=test_tenant_id,
        email="agent@carexport.com",
    )

    app.dependency_overrides[get_current_user] = lambda: sales_agent_user
    app.dependency_overrides[get_whatsapp_provider] = lambda: mock_whatsapp_provider

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.merge = AsyncMock(side_effect=lambda e: e)
    mock_db.add = MagicMock()
    mock_db.get = AsyncMock(return_value=mock_cust)

    async def mock_execute(stmt: object, *args: object, **kwargs: object) -> MagicMock:
        stmt_str = str(stmt)
        res = MagicMock()
        if "users" in stmt_str:
            res.scalar_one_or_none.return_value = mock_sender_user
            res.scalars.return_value.all.return_value = [mock_sender_user]
        elif "whatsapp_accounts" in stmt_str:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.first.return_value = None
            res.scalars.return_value.all.return_value = []
        elif "messages" in stmt_str:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
        else:
            res.scalar_one_or_none.return_value = mock_conv
            res.scalars.return_value.all.return_value = [mock_conv]
        return res

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    from app.core.database import get_db_session

    app.dependency_overrides[get_db_session] = lambda: mock_db

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(
                f"/api/v1/conversations/{conv_id}/messages",
                headers={"Idempotency-Key": str(uuid.uuid4())},
                json={"content": "Voici les détails du véhicule", "message_type": "text"},
            )
            assert response.status_code == status.HTTP_201_CREATED
            payload = response.json()
            assert payload["success"] is True
            assert payload["data"]["direction"] == "Outbound"
            assert payload["data"]["sender_type"] == "Agent"
            assert payload["data"]["content"] == "Voici les détails du véhicule"
            mock_whatsapp_provider.send_text_message.assert_awaited_once_with(
                phone_number_id=settings.META_WHATSAPP_PHONE_NUMBER_ID,
                recipient_e164="+21698123456",
                text_body="Voici les détails du véhicule",
            )
    finally:
        app.dependency_overrides.clear()
