"""Models package re-exporting Base declarative models and entity classes."""

from app.models.ai_suggestion import AISuggestion, AISuggestionStatus
from app.models.ai_understanding import (
    AIUnderstanding,
    AIUnderstandingIntent,
    AIUnderstandingStatus,
)
from app.models.base import Base, TimestampMixin
from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
from app.models.document import Document
from app.models.inbound_message import InboundMessage
from app.models.lead import Lead, LeadPriority, LeadStatus, LostReason
from app.models.message import Message
from app.models.quotation import (
    Quotation,
    QuotationApprovalStatus,
    QuotationItem,
    QuotationStatus,
)
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.vehicle import VATRegime, Vehicle, VehicleStatus
from app.models.vehicle_request import VehicleRequest
from app.models.whatsapp_account import WhatsAppAccount

__all__ = [
    "AISuggestion",
    "AISuggestionStatus",
    "AIUnderstanding",
    "AIUnderstandingIntent",
    "AIUnderstandingStatus",
    "Base",
    "Customer",
    "Document",
    "InboundMessage",
    "Lead",
    "LeadPriority",
    "LeadStatus",
    "LostReason",
    "Message",
    "Quotation",
    "QuotationApprovalStatus",
    "QuotationItem",
    "QuotationStatus",
    "Tenant",
    "TimestampMixin",
    "User",
    "UserRole",
    "VATRegime",
    "Vehicle",
    "VehicleRequest",
    "VehicleStatus",
    "WhatsAppAccount",
    "WhatsAppConversation",
]
