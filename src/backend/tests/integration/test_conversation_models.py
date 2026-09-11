"""Integration & unit tests for WhatsAppConversation and Message declarative models."""

import uuid

from sqlalchemy import Index, UniqueConstraint

from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
from app.models.message import Message
from app.models.tenant import Tenant
from app.models.user import User, UserRole


def test_whatsapp_conversation_model_instantiation_and_defaults() -> None:
    """Verify WhatsAppConversation model instantiates with UUIDv7 ID and defaults."""
    tenant_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    conv = WhatsAppConversation(
        tenant_id=tenant_id,
        customer_id=customer_id,
        assigned_agent_id=agent_id,
    )

    assert conv.id is not None
    assert isinstance(conv.id, uuid.UUID)
    assert conv.id.version == 7
    assert conv.tenant_id == tenant_id
    assert conv.customer_id == customer_id
    assert conv.assigned_agent_id == agent_id
    assert conv.status == "PendingAgent"
    assert conv.unread_count == 0
    assert conv.last_message_at is not None


def test_message_model_instantiation_and_defaults() -> None:
    """Verify Message model instantiates with UUIDv7 ID and default attribute states."""
    tenant_id = uuid.uuid4()
    conv_id = uuid.uuid4()
    wamid = "wamid.HBgLMTIxNjk4MTIzNDU2FQIAERgSQjEwNTU1NDQ0MzMyMjExBB=="

    msg = Message(
        tenant_id=tenant_id,
        conversation_id=conv_id,
        provider_message_id=wamid,
        direction="Inbound",
        sender_type="Customer",
        content="Testing conversation message model instantiation",
    )

    assert msg.id is not None
    assert isinstance(msg.id, uuid.UUID)
    assert msg.id.version == 7
    assert msg.tenant_id == tenant_id
    assert msg.conversation_id == conv_id
    assert msg.provider_message_id == wamid
    assert msg.direction == "Inbound"
    assert msg.sender_type == "Customer"
    assert msg.sender_user_id is None
    assert msg.message_type == "text"
    assert msg.content == "Testing conversation message model instantiation"
    assert msg.media_url is None
    assert msg.delivery_status == "Sent"
    assert msg.metadata_payload == {}


def test_conversation_and_message_relationship_navigation() -> None:
    """Verify relationship navigation between Tenant, Customer, User, Conversation, and Message."""
    tenant = Tenant(name="Delta Export GmbH", slug="delta-export")
    user = User(
        tenant_id=tenant.id,
        email="agent@delta.de",
        hashed_password="hash",  # noqa: S106
        full_name="Agent Max",
        role=UserRole.SALES_AGENT,
        tenant=tenant,
    )
    customer = Customer(
        tenant_id=tenant.id,
        phone_e164="+21698123456",
        full_name="Sami Khedira",
        tenant=tenant,
    )
    conv = WhatsAppConversation(
        tenant_id=tenant.id,
        customer_id=customer.id,
        assigned_agent_id=user.id,
        tenant=tenant,
        customer=customer,
        assigned_agent=user,
    )
    msg = Message(
        tenant_id=tenant.id,
        conversation_id=conv.id,
        direction="Inbound",
        sender_type="Customer",
        content="Hello, I want to export a BMW X5",
        tenant=tenant,
        conversation=conv,
    )

    assert conv.tenant is tenant
    assert conv.customer is customer
    assert conv.assigned_agent is user
    assert conv in tenant.conversations
    assert conv in customer.conversations
    assert conv in user.assigned_conversations
    assert msg in conv.messages
    assert msg.conversation is conv
    assert msg.tenant is tenant


def test_conversation_and_message_table_constraints_and_indexes() -> None:
    """Verify table constraints and indexes on WhatsAppConversation and Message."""
    # WhatsAppConversation table args
    conv_args = WhatsAppConversation.__table_args__
    conv_unique_constraints = [arg for arg in conv_args if isinstance(arg, UniqueConstraint)]
    conv_indexes = [arg for arg in conv_args if isinstance(arg, Index)]

    assert any(
        uq.name == "uq_whatsapp_conversations_tenant_id_customer_id"
        for uq in conv_unique_constraints
    )
    assert any(idx.name == "ix_whatsapp_conversations_tenant_id" for idx in conv_indexes)
    assert any(idx.name == "ix_whatsapp_conversations_customer_id" for idx in conv_indexes)
    assert any(idx.name == "ix_whatsapp_conversations_status" for idx in conv_indexes)

    # Message table args
    msg_args = Message.__table_args__
    msg_unique_constraints = [arg for arg in msg_args if isinstance(arg, UniqueConstraint)]
    msg_indexes = [arg for arg in msg_args if isinstance(arg, Index)]

    assert any(
        uq.name == "uq_messages_tenant_id_provider_message_id" for uq in msg_unique_constraints
    )
    assert any(idx.name == "ix_messages_tenant_id" for idx in msg_indexes)
    assert any(idx.name == "ix_messages_conversation_id" for idx in msg_indexes)
    assert any(idx.name == "ix_messages_created_at" for idx in msg_indexes)
