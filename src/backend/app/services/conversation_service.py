"""Conversation Domain Service managing threads, status, and messages (WS-07, TASK-0702)."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundException
from app.core.logging import logger
from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
from app.models.message import Message
from app.models.user import User
from app.repositories.tenant_base import TenantRepository


class ConversationStatus(StrEnum):
    """Supported operational conversation thread statuses."""

    PENDING_AGENT = "PendingAgent"
    ACTIVE = "Active"
    RESOLVED = "Resolved"
    ARCHIVED = "Archived"
    CLOSED = "Closed"


class MessageDirection(StrEnum):
    """Supported message flow directions."""

    INBOUND = "Inbound"
    OUTBOUND = "Outbound"


class MessageSenderType(StrEnum):
    """Supported message sender categories."""

    CUSTOMER = "Customer"
    AGENT = "Agent"
    SYSTEM = "System"
    AI_BOT = "AI_Bot"


class MessageType(StrEnum):
    """Supported message content types."""

    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    LOCATION = "location"
    TEMPLATE = "template"


class MessageDeliveryStatus(StrEnum):
    """Supported message delivery states."""

    PENDING = "Pending"
    SENT = "Sent"
    DELIVERED = "Delivered"
    READ = "Read"
    FAILED = "Failed"


class ConversationService:
    """Domain service managing multi-tenant conversation lifecycle and message timeline."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        """Initialize ConversationService bound to specific database session & tenant_id."""
        self.session = session
        self.tenant_id = (
            tenant_id if isinstance(tenant_id, uuid.UUID) else uuid.UUID(str(tenant_id))
        )
        self.conversation_repo = TenantRepository(
            session, WhatsAppConversation, tenant_id=self.tenant_id
        )
        self.message_repo = TenantRepository(session, Message, tenant_id=self.tenant_id)
        self.customer_repo = TenantRepository(session, Customer, tenant_id=self.tenant_id)
        self.user_repo = TenantRepository(session, User, tenant_id=self.tenant_id)

    async def get_conversation(self, conversation_id: uuid.UUID) -> WhatsAppConversation:
        """Fetch conversation thread by ID strictly scoped to tenant context or raise HTTP 404."""
        return await self.conversation_repo.get_or_raise(conversation_id)

    async def get_or_create_conversation(
        self, customer_id: uuid.UUID
    ) -> tuple[WhatsAppConversation, bool]:
        """Fetch existing conversation for customer or create a new conversation thread.

        Args:
            customer_id: Buyer customer UUID.

        Returns:
            tuple[WhatsAppConversation, bool]: (Conversation entity, created_flag boolean).
        """
        await self.customer_repo.get_or_raise(customer_id)

        existing = await self.conversation_repo.find_one(customer_id=customer_id)
        if existing is not None:
            return existing, False

        new_conversation = WhatsAppConversation(
            tenant_id=self.tenant_id,
            customer_id=customer_id,
            status=ConversationStatus.PENDING_AGENT.value,
            unread_count=0,
            last_message_at=datetime.now(UTC),
        )
        created = await self.conversation_repo.create(new_conversation)
        logger.info(
            "CONVERSATION_CREATED tenant_id=%s conversation_id=%s customer_id=%s",
            str(self.tenant_id),
            str(created.id),
            str(customer_id),
        )
        return created, True

    async def assign_agent(
        self,
        conversation_id: uuid.UUID,
        agent_id: uuid.UUID | None,
        assigned_by_user_id: uuid.UUID | None = None,
    ) -> WhatsAppConversation:
        """Assign or unassign a sales agent to a conversation thread (FR-INBOX-002).

        Args:
            conversation_id: Target conversation UUID.
            agent_id: Target agent User UUID or None to unassign.
            assigned_by_user_id: User UUID performing the assignment.

        Raises:
            NotFoundException: If conversation or agent does not exist within tenant scope.
        """
        conversation = await self.get_conversation(conversation_id)

        if agent_id is not None:
            agent_user = await self.user_repo.get_by_id(agent_id)
            if agent_user is None:
                raise NotFoundException(
                    f"Agent user with ID '{agent_id}' not found in this tenant."
                )

        conversation.assigned_agent_id = agent_id
        if agent_id is not None and conversation.status == ConversationStatus.PENDING_AGENT.value:
            conversation.status = ConversationStatus.ACTIVE.value

        updated = await self.conversation_repo.update(conversation)

        logger.info(
            "CONVERSATION_ASSIGNED tenant_id=%s conversation_id=%s "
            "assigned_agent_id=%s assigned_by=%s",
            str(self.tenant_id),
            str(conversation_id),
            str(agent_id) if agent_id else "unassigned",
            str(assigned_by_user_id) if assigned_by_user_id else "system",
        )
        return updated

    async def update_status(
        self,
        conversation_id: uuid.UUID,
        status: ConversationStatus | str,
    ) -> WhatsAppConversation:
        """Update operational status of a conversation thread.

        Args:
            conversation_id: Target conversation UUID.
            status: New status string or ConversationStatus enum value.
        """
        conversation = await self.get_conversation(conversation_id)
        status_value = status.value if isinstance(status, ConversationStatus) else str(status)

        conversation.status = status_value
        updated = await self.conversation_repo.update(conversation)

        logger.info(
            "CONVERSATION_STATUS_UPDATED tenant_id=%s conversation_id=%s new_status=%s",
            str(self.tenant_id),
            str(conversation_id),
            status_value,
        )
        return updated

    async def mark_as_read(self, conversation_id: uuid.UUID) -> WhatsAppConversation:
        """Reset unread count on a conversation thread to 0."""
        conversation = await self.get_conversation(conversation_id)
        if conversation.unread_count > 0:
            conversation.unread_count = 0
            updated = await self.conversation_repo.update(conversation)
            return updated
        return conversation

    async def add_message(
        self,
        conversation_id: uuid.UUID,
        direction: MessageDirection | str,
        sender_type: MessageSenderType | str,
        content: str,
        message_type: MessageType | str = MessageType.TEXT,
        provider_message_id: str | None = None,
        sender_user_id: uuid.UUID | None = None,
        media_url: str | None = None,
        delivery_status: MessageDeliveryStatus | str = MessageDeliveryStatus.SENT,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        """Append an inbound or outbound message to the conversation timeline.

        Updates thread last_message_at and increments unread_count if message is inbound.
        Enforces wamid deduplication if provider_message_id is supplied (BR-008).
        """
        conversation = await self.get_conversation(conversation_id)

        dir_value = direction.value if isinstance(direction, MessageDirection) else str(direction)
        sender_val = (
            sender_type.value if isinstance(sender_type, MessageSenderType) else str(sender_type)
        )
        msg_type_val = (
            message_type.value if isinstance(message_type, MessageType) else str(message_type)
        )
        del_status_val = (
            delivery_status.value
            if isinstance(delivery_status, MessageDeliveryStatus)
            else str(delivery_status)
        )

        if provider_message_id:
            existing_msg = await self.message_repo.find_one(provider_message_id=provider_message_id)
            if existing_msg is not None:
                logger.warning(
                    "DUPLICATE_MESSAGE_IGNORED tenant_id=%s provider_message_id=%s",
                    str(self.tenant_id),
                    provider_message_id,
                )
                return existing_msg

        if sender_user_id is not None:
            user = await self.user_repo.get_by_id(sender_user_id)
            if user is None:
                raise NotFoundException(f"User with ID '{sender_user_id}' not found.")

        now = datetime.now(UTC)
        message = Message(
            tenant_id=self.tenant_id,
            conversation_id=conversation_id,
            provider_message_id=provider_message_id,
            direction=dir_value,
            sender_type=sender_val,
            sender_user_id=sender_user_id,
            message_type=msg_type_val,
            content=content,
            media_url=media_url,
            delivery_status=del_status_val,
            metadata_payload=metadata or {},
        )
        created_msg = await self.message_repo.create(message)

        conversation.last_message_at = now
        if dir_value.lower() == "inbound":
            conversation.unread_count += 1

        await self.conversation_repo.update(conversation)

        logger.info(
            "MESSAGE_APPENDED tenant_id=%s conversation_id=%s message_id=%s direction=%s",
            str(self.tenant_id),
            str(conversation_id),
            str(created_msg.id),
            dir_value,
        )
        return created_msg

    async def get_timeline(
        self,
        conversation_id: uuid.UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Message], int]:
        """Fetch chronologically ordered message timeline for a conversation thread.

        Args:
            conversation_id: Conversation UUID strictly in tenant scope.
            offset: Offset pagination index.
            limit: Page size limit.

        Returns:
            tuple[list[Message], int]: (Messages ordered by created_at ASC, total count).
        """
        await self.get_conversation(conversation_id)

        count_stmt = (
            select(func.count(Message.id))
            .where(Message.tenant_id == self.tenant_id)
            .where(Message.conversation_id == conversation_id)
        )
        count_res = await self.session.execute(count_stmt)
        total = count_res.scalar_one() or 0

        stmt = (
            select(Message)
            .where(Message.tenant_id == self.tenant_id)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        messages = list(res.scalars().all())

        return messages, total

    async def list_conversations(
        self,
        status: str | None = None,
        assigned_agent_id: uuid.UUID | None = None,
        unassigned_only: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[WhatsAppConversation], int]:
        """Fetch list of conversation threads with status and assignment filters.

        Args:
            status: Optional status filter.
            assigned_agent_id: Optional filter for specific assigned agent.
            unassigned_only: If True, filters for conversations where assigned_agent_id IS NULL.
            offset: Page offset index.
            limit: Page size limit.

        Returns:
            tuple[list[WhatsAppConversation], int]: (List of conversations, total count).
        """
        query = select(WhatsAppConversation).where(WhatsAppConversation.tenant_id == self.tenant_id)
        count_query = select(func.count(WhatsAppConversation.id)).where(
            WhatsAppConversation.tenant_id == self.tenant_id
        )

        if status is not None:
            query = query.where(WhatsAppConversation.status == status)
            count_query = count_query.where(WhatsAppConversation.status == status)

        if unassigned_only:
            query = query.where(WhatsAppConversation.assigned_agent_id.is_(None))
            count_query = count_query.where(WhatsAppConversation.assigned_agent_id.is_(None))
        elif assigned_agent_id is not None:
            query = query.where(WhatsAppConversation.assigned_agent_id == assigned_agent_id)
            count_query = count_query.where(
                WhatsAppConversation.assigned_agent_id == assigned_agent_id
            )

        total_res = await self.session.execute(count_query)
        total = total_res.scalar_one() or 0

        query = (
            query.order_by(WhatsAppConversation.last_message_at.desc()).offset(offset).limit(limit)
        )
        res = await self.session.execute(query)
        conversations = list(res.scalars().all())

        return conversations, total
