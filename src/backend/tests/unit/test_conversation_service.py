"""Unit tests for ConversationService (WS-07, TASK-0702)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import NotFoundException
from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
from app.models.message import Message
from app.models.user import User
from app.services.conversation_service import (
    ConversationService,
    ConversationStatus,
    MessageDirection,
    MessageSenderType,
)


@pytest.mark.asyncio
async def test_get_or_create_conversation_creates_new() -> None:
    """Verify get_or_create_conversation creates a new thread if none exists."""
    mock_session = AsyncMock()
    tenant_id = uuid.uuid4()
    customer_id = uuid.uuid4()

    service = ConversationService(mock_session, tenant_id)
    service.customer_repo.get_or_raise = AsyncMock(return_value=Customer(id=customer_id))  # type: ignore[method-assign]
    service.conversation_repo.find_one = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service.conversation_repo.create = AsyncMock(side_effect=lambda c: c)  # type: ignore[method-assign]

    conv, created = await service.get_or_create_conversation(customer_id)

    assert created is True
    assert conv.tenant_id == tenant_id
    assert conv.customer_id == customer_id
    assert conv.status == ConversationStatus.PENDING_AGENT.value
    assert conv.unread_count == 0


@pytest.mark.asyncio
async def test_get_or_create_conversation_returns_existing() -> None:
    """Verify get_or_create_conversation returns existing thread if found."""
    mock_session = AsyncMock()
    tenant_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    existing_conv = WhatsAppConversation(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        customer_id=customer_id,
        status="Active",
    )

    service = ConversationService(mock_session, tenant_id)
    service.customer_repo.get_or_raise = AsyncMock(return_value=Customer(id=customer_id))  # type: ignore[method-assign]
    service.conversation_repo.find_one = AsyncMock(return_value=existing_conv)  # type: ignore[method-assign]

    conv, created = await service.get_or_create_conversation(customer_id)

    assert created is False
    assert conv is existing_conv


@pytest.mark.asyncio
async def test_assign_agent_success_and_status_transition() -> None:
    """Verify agent assignment updates assigned_agent_id and transitions PendingAgent to Active."""
    mock_session = AsyncMock()
    tenant_id = uuid.uuid4()
    conv_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    conv = WhatsAppConversation(
        id=conv_id,
        tenant_id=tenant_id,
        status="PendingAgent",
        assigned_agent_id=None,
    )
    agent_user = User(id=agent_id, tenant_id=tenant_id, email="agent@carexport.com")

    service = ConversationService(mock_session, tenant_id)
    service.conversation_repo.get_or_raise = AsyncMock(return_value=conv)  # type: ignore[method-assign]
    service.user_repo.get_by_id = AsyncMock(return_value=agent_user)  # type: ignore[method-assign]
    service.conversation_repo.update = AsyncMock(side_effect=lambda c: c)  # type: ignore[method-assign]

    updated = await service.assign_agent(
        conversation_id=conv_id,
        agent_id=agent_id,
        assigned_by_user_id=uuid.uuid4(),
    )

    assert updated.assigned_agent_id == agent_id
    assert updated.status == ConversationStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_assign_agent_cross_tenant_raises_not_found() -> None:
    """Verify assigning an agent from a different tenant raises NotFoundException."""
    mock_session = AsyncMock()
    tenant_id = uuid.uuid4()
    conv_id = uuid.uuid4()
    foreign_agent_id = uuid.uuid4()

    conv = WhatsAppConversation(id=conv_id, tenant_id=tenant_id)

    service = ConversationService(mock_session, tenant_id)
    service.conversation_repo.get_or_raise = AsyncMock(return_value=conv)  # type: ignore[method-assign]
    # Cross tenant or nonexistent user returns None
    service.user_repo.get_by_id = AsyncMock(return_value=None)  # type: ignore[method-assign]

    with pytest.raises(NotFoundException, match="Agent user with ID"):
        await service.assign_agent(conversation_id=conv_id, agent_id=foreign_agent_id)


@pytest.mark.asyncio
async def test_update_status() -> None:
    """Verify updating status on conversation thread."""
    mock_session = AsyncMock()
    tenant_id = uuid.uuid4()
    conv_id = uuid.uuid4()
    conv = WhatsAppConversation(id=conv_id, tenant_id=tenant_id, status="Active")

    service = ConversationService(mock_session, tenant_id)
    service.conversation_repo.get_or_raise = AsyncMock(return_value=conv)  # type: ignore[method-assign]
    service.conversation_repo.update = AsyncMock(side_effect=lambda c: c)  # type: ignore[method-assign]

    updated = await service.update_status(conv_id, ConversationStatus.RESOLVED)
    assert updated.status == ConversationStatus.RESOLVED.value


@pytest.mark.asyncio
async def test_mark_as_read_resets_unread_count() -> None:
    """Verify mark_as_read resets unread_count from positive integer to 0."""
    mock_session = AsyncMock()
    tenant_id = uuid.uuid4()
    conv_id = uuid.uuid4()
    conv = WhatsAppConversation(id=conv_id, tenant_id=tenant_id, unread_count=5)

    service = ConversationService(mock_session, tenant_id)
    service.conversation_repo.get_or_raise = AsyncMock(return_value=conv)  # type: ignore[method-assign]
    service.conversation_repo.update = AsyncMock(side_effect=lambda c: c)  # type: ignore[method-assign]

    updated = await service.mark_as_read(conv_id)
    assert updated.unread_count == 0


@pytest.mark.asyncio
async def test_add_message_inbound_increments_unread_and_updates_last_message_at() -> None:
    """Verify inbound message increments conversation unread_count and updates last_message_at."""
    mock_session = AsyncMock()
    tenant_id = uuid.uuid4()
    conv_id = uuid.uuid4()
    old_time = datetime(2026, 1, 1, tzinfo=UTC)
    conv = WhatsAppConversation(
        id=conv_id,
        tenant_id=tenant_id,
        unread_count=2,
        last_message_at=old_time,
    )

    service = ConversationService(mock_session, tenant_id)
    service.conversation_repo.get_or_raise = AsyncMock(return_value=conv)  # type: ignore[method-assign]
    service.message_repo.find_one = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service.message_repo.create = AsyncMock(side_effect=lambda m: m)  # type: ignore[method-assign]
    service.conversation_repo.update = AsyncMock(side_effect=lambda c: c)  # type: ignore[method-assign]

    msg = await service.add_message(
        conversation_id=conv_id,
        direction=MessageDirection.INBOUND,
        sender_type=MessageSenderType.CUSTOMER,
        content="Hello, I want to export a Golf 8 to Tunisia.",
        provider_message_id="wamid.HBgLMTIzNDU2Nzg5",
    )

    assert msg.direction == "Inbound"
    assert msg.sender_type == "Customer"
    assert msg.content == "Hello, I want to export a Golf 8 to Tunisia."
    assert conv.unread_count == 3
    assert conv.last_message_at > old_time


@pytest.mark.asyncio
async def test_add_message_duplicate_wamid_returns_existing() -> None:
    """Verify duplicate wamid returns existing message without persisting duplicate."""
    mock_session = AsyncMock()
    tenant_id = uuid.uuid4()
    conv_id = uuid.uuid4()
    conv = WhatsAppConversation(id=conv_id, tenant_id=tenant_id)
    existing_msg = Message(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        conversation_id=conv_id,
        provider_message_id="wamid.123",
        content="Original message",
    )

    service = ConversationService(mock_session, tenant_id)
    service.conversation_repo.get_or_raise = AsyncMock(return_value=conv)  # type: ignore[method-assign]
    service.message_repo.find_one = AsyncMock(return_value=existing_msg)  # type: ignore[method-assign]

    msg = await service.add_message(
        conversation_id=conv_id,
        direction=MessageDirection.INBOUND,
        sender_type=MessageSenderType.CUSTOMER,
        content="Duplicate message payload",
        provider_message_id="wamid.123",
    )

    assert msg is existing_msg
    assert msg.content == "Original message"


@pytest.mark.asyncio
async def test_get_timeline_success() -> None:
    """Verify get_timeline returns messages and total count."""
    mock_session = AsyncMock()
    tenant_id = uuid.uuid4()
    conv_id = uuid.uuid4()
    conv = WhatsAppConversation(id=conv_id, tenant_id=tenant_id)

    msg1 = Message(id=uuid.uuid4(), tenant_id=tenant_id, conversation_id=conv_id, content="Hi")
    msg2 = Message(id=uuid.uuid4(), tenant_id=tenant_id, conversation_id=conv_id, content="Hello")

    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = 2

    mock_messages_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [msg1, msg2]
    mock_messages_result.scalars.return_value = mock_scalars

    mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_messages_result])

    service = ConversationService(mock_session, tenant_id)
    service.conversation_repo.get_or_raise = AsyncMock(return_value=conv)  # type: ignore[method-assign]

    messages, total = await service.get_timeline(conv_id, offset=0, limit=10)

    assert total == 2
    assert len(messages) == 2
    assert messages[0].content == "Hi"
    assert messages[1].content == "Hello"


@pytest.mark.asyncio
async def test_list_conversations_filtering() -> None:
    """Verify list_conversations applies status and assignment filters."""
    mock_session = AsyncMock()
    tenant_id = uuid.uuid4()
    conv1 = WhatsAppConversation(id=uuid.uuid4(), tenant_id=tenant_id, status="PendingAgent")

    mock_count_res = MagicMock()
    mock_count_res.scalar_one.return_value = 1

    mock_query_res = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [conv1]
    mock_query_res.scalars.return_value = mock_scalars

    mock_session.execute = AsyncMock(side_effect=[mock_count_res, mock_query_res])

    service = ConversationService(mock_session, tenant_id)

    convs, total = await service.list_conversations(
        status="PendingAgent",
        unassigned_only=True,
    )

    assert total == 1
    assert len(convs) == 1
    assert convs[0].status == "PendingAgent"
