"""Integration tests for WhatsAppAccount and InboundMessage models and constraints."""

import uuid

from sqlalchemy import Index, UniqueConstraint

from app.models.inbound_message import InboundMessage
from app.models.tenant import Tenant
from app.models.whatsapp_account import WhatsAppAccount


def test_whatsapp_account_model_instantiation_and_relationship() -> None:
    """Verify WhatsAppAccount model instantiation and relationship navigation."""
    tenant = Tenant(name="WhatsApp Integration Tenant", slug="wa-integration-tenant")
    account = WhatsAppAccount(
        tenant_id=tenant.id,
        phone_number_id="ph_id_99887766",
        display_phone_number="+491701234567",
        status="Active",
        tenant=tenant,
    )

    assert account.id is not None
    assert isinstance(account.id, uuid.UUID)
    assert account.id.version == 7
    assert account.phone_number_id == "ph_id_99887766"
    assert account.display_phone_number == "+491701234567"
    assert account.status == "Active"
    assert account.tenant is tenant
    assert account in tenant.whatsapp_accounts


def test_inbound_message_model_instantiation_and_relationship() -> None:
    """Verify InboundMessage model instantiation and default attribute states."""
    tenant = Tenant(name="Inbound Message Tenant", slug="inbound-msg-tenant")
    account = WhatsAppAccount(
        tenant_id=tenant.id,
        phone_number_id="ph_id_112233",
        tenant=tenant,
    )
    wamid = "wamid.HBgLMTIxNjk4MTIzNDU2FQIAERgSQjEwNTU1NDQ0MzMyMjExBB=="

    msg = InboundMessage(
        tenant_id=tenant.id,
        whatsapp_account_id=account.id,
        provider_message_id=wamid,
        sender_phone_e164="+21698123456",
        message_type="text",
        content="Testing inbound message model",
        tenant=tenant,
        whatsapp_account=account,
    )

    assert msg.id is not None
    assert isinstance(msg.id, uuid.UUID)
    assert msg.id.version == 7
    assert msg.tenant_id == tenant.id
    assert msg.whatsapp_account_id == account.id
    assert msg.provider_message_id == wamid
    assert msg.sender_phone_e164 == "+21698123456"
    assert msg.message_type == "text"
    assert msg.content == "Testing inbound message model"
    assert msg.processed_at is None
    assert msg.tenant is tenant
    assert msg.whatsapp_account is account


def test_whatsapp_tables_unique_constraints_and_indexes() -> None:
    """Verify table constraints and indexes on WhatsAppAccount and InboundMessage."""
    # WhatsAppAccount table args
    account_args = WhatsAppAccount.__table_args__
    account_unique_constraints = [arg for arg in account_args if isinstance(arg, UniqueConstraint)]
    account_indexes = [arg for arg in account_args if isinstance(arg, Index)]

    assert any(
        uq.name == "uq_whatsapp_accounts_phone_number_id" for uq in account_unique_constraints
    )
    assert any(idx.name == "ix_whatsapp_accounts_phone_number_id" for idx in account_indexes)

    # InboundMessage table args
    msg_args = InboundMessage.__table_args__
    msg_unique_constraints = [arg for arg in msg_args if isinstance(arg, UniqueConstraint)]
    msg_indexes = [arg for arg in msg_args if isinstance(arg, Index)]

    assert any(
        uq.name == "uq_inbound_messages_tenant_id_provider_message_id"
        for uq in msg_unique_constraints
    )
    assert any(idx.name == "ix_inbound_messages_provider_message_id" for idx in msg_indexes)
    assert any(idx.name == "ix_inbound_messages_sender_phone" for idx in msg_indexes)
