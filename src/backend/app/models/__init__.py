"""Models package re-exporting Base declarative models and entity classes."""

from app.models.base import Base, TimestampMixin
from app.models.customer import Customer
from app.models.inbound_message import InboundMessage
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.whatsapp_account import WhatsAppAccount

__all__ = [
    "Base",
    "TimestampMixin",
    "Customer",
    "InboundMessage",
    "Tenant",
    "User",
    "UserRole",
    "WhatsAppAccount",
]
