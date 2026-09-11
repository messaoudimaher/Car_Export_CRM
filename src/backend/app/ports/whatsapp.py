"""WhatsApp Provider Abstract Port Interface & DTO Contracts (ADR 0002, ADR 0018)."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class WhatsAppMessage(BaseModel):
    """Normalized DTO for inbound WhatsApp chat messages."""

    wamid: str = Field(..., description="Provider unique message identifier (Meta wamid)")
    phone_number_id: str = Field(..., description="Meta Cloud API Phone Number ID")
    display_phone_number: str = Field("", description="Business account display phone number")
    from_phone_e164: str = Field(..., description="Customer normalized sender E.164 phone number")
    wa_id: str = Field(..., description="Customer raw WhatsApp identifier (wa_id)")
    text_body: str = Field(..., description="Message text content")
    timestamp: int = Field(..., description="Message creation epoch timestamp")
    message_type: str = Field("text", description="Message content type (text, image, document)")
    raw_payload: dict[str, Any] = Field(
        default_factory=dict, description="Original raw provider webhook payload"
    )


class OutboundWhatsAppMessageResult(BaseModel):
    """Result DTO for outbound WhatsApp message dispatch."""

    wamid: str = Field(..., description="Assigned provider message identifier")
    recipient_e164: str = Field(..., description="Recipient normalized E.164 phone number")
    status: str = Field("sent", description="Dispatch status (sent, queued, failed)")


class WhatsAppProvider(ABC):
    """Abstract port interface for WhatsApp Business Service Providers (BSP)."""

    @abstractmethod
    def verify_webhook_signature(
        self,
        raw_body: bytes,
        signature_header: str | None,
    ) -> bool:
        """Verify HMAC signature of inbound webhook HTTP request.

        Args:
            raw_body: Raw request body bytes.
            signature_header: Incoming HTTP signature header (e.g. X-Hub-Signature-256).

        Returns:
            bool: True if signature is valid, False otherwise.
        """

    @abstractmethod
    def parse_webhook_payload(
        self,
        payload: dict[str, Any],
    ) -> list[WhatsAppMessage]:
        """Parse raw webhook JSON payload into normalized WhatsAppMessage list.

        Args:
            payload: Webhook JSON dictionary.

        Returns:
            list[WhatsAppMessage]: Extracted normalized messages.
        """

    @abstractmethod
    async def send_text_message(
        self,
        phone_number_id: str,
        recipient_e164: str,
        text_body: str,
    ) -> OutboundWhatsAppMessageResult:
        """Dispatch outbound text message to a WhatsApp recipient.

        Args:
            phone_number_id: Sender business WhatsApp account phone_number_id.
            recipient_e164: Recipient E.164 formatted phone number.
            text_body: Text message body.

        Returns:
            OutboundWhatsAppMessageResult: Dispatch result containing provider wamid.
        """

    @abstractmethod
    async def send_template_message(
        self,
        phone_number_id: str,
        recipient_e164: str,
        template_name: str,
        language_code: str = "fr",
        components: list[dict[str, Any]] | None = None,
    ) -> OutboundWhatsAppMessageResult:
        """Dispatch outbound HSM template message to a WhatsApp recipient.

        Args:
            phone_number_id: Sender business WhatsApp account phone_number_id.
            recipient_e164: Recipient E.164 formatted phone number.
            template_name: Approved Meta template name.
            language_code: Template language ISO code (e.g. "fr", "ar", "en").
            components: Template parameters / body variables.

        Returns:
            OutboundWhatsAppMessageResult: Dispatch result containing provider wamid.
        """
