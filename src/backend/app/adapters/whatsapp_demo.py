"""Local-First Reference Demo WhatsApp Adapter (ADR 0018).

Enables offline development and unit/integration testing without external Meta API dependencies.
"""

import time
import uuid
from typing import Any

from app.ports.whatsapp import (
    OutboundWhatsAppMessageResult,
    WhatsAppMessage,
    WhatsAppProvider,
)
from app.utils.phone import extract_whatsapp_id, normalize_phone_number


class DemoWhatsAppProvider(WhatsAppProvider):
    """Local-first reference implementation of WhatsAppProvider port."""

    def __init__(self) -> None:
        """Initialize DemoWhatsAppProvider maintaining an in-memory sent message log."""
        self.sent_messages: list[dict[str, Any]] = []

    def verify_webhook_signature(
        self,
        raw_body: bytes,
        signature_header: str | None,
    ) -> bool:
        """Verify HMAC signature (always returns True in local dev/test mode)."""
        return True

    def parse_webhook_payload(
        self,
        payload: dict[str, Any],
    ) -> list[WhatsAppMessage]:
        """Parse webhook JSON payload into normalized WhatsAppMessage objects.

        Supports standard Meta Cloud API webhook structure and direct demo payloads.
        """
        messages: list[WhatsAppMessage] = []

        # Standard Meta Cloud API webhook JSON structure parsing
        if "entry" in payload and isinstance(payload["entry"], list):
            for entry in payload["entry"]:
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    metadata = value.get("metadata", {})
                    phone_number_id = str(metadata.get("phone_number_id", "demo_phone_id"))
                    display_phone_number = str(metadata.get("display_phone_number", ""))

                    raw_messages = value.get("messages", [])
                    for msg in raw_messages:
                        wamid = str(msg.get("id", f"wamid.demo.{uuid.uuid4()}"))
                        from_phone = str(msg.get("from", ""))
                        if not from_phone.startswith("+"):
                            from_phone = f"+{from_phone}"
                        normalized_from = normalize_phone_number(from_phone, "TN")
                        wa_id = extract_whatsapp_id(normalized_from)
                        timestamp = int(msg.get("timestamp", time.time()))

                        text_body = ""
                        msg_type = str(msg.get("type", "text"))
                        if msg_type == "text" and "text" in msg:
                            text_body = str(msg["text"].get("body", ""))

                        messages.append(
                            WhatsAppMessage(
                                wamid=wamid,
                                phone_number_id=phone_number_id,
                                display_phone_number=display_phone_number,
                                from_phone_e164=normalized_from,
                                wa_id=wa_id,
                                text_body=text_body,
                                timestamp=timestamp,
                                message_type=msg_type,
                                raw_payload=payload,
                            )
                        )
            return messages

        # Simplified direct demo payload fallback for unit testing
        if "from_phone_e164" in payload or "from" in payload:
            raw_from = str(payload.get("from_phone_e164") or payload.get("from", ""))
            normalized_from = normalize_phone_number(raw_from, "TN")
            wa_id = extract_whatsapp_id(normalized_from)
            wamid = str(payload.get("wamid") or f"wamid.demo.{uuid.uuid4()}")
            phone_number_id = str(payload.get("phone_number_id", "demo_phone_id"))
            text_body = str(payload.get("text_body") or payload.get("text", ""))
            timestamp = int(payload.get("timestamp", time.time()))

            messages.append(
                WhatsAppMessage(
                    wamid=wamid,
                    phone_number_id=phone_number_id,
                    display_phone_number=str(payload.get("display_phone_number", "")),
                    from_phone_e164=normalized_from,
                    wa_id=wa_id,
                    text_body=text_body,
                    timestamp=timestamp,
                    message_type="text",
                    raw_payload=payload,
                )
            )

        return messages

    async def send_text_message(
        self,
        phone_number_id: str,
        recipient_e164: str,
        text_body: str,
    ) -> OutboundWhatsAppMessageResult:
        """Dispatch local demo text message recording dispatch in memory."""
        normalized_recipient = normalize_phone_number(recipient_e164, "TN")
        wamid = f"wamid.demo.{uuid.uuid4()}"

        record = {
            "wamid": wamid,
            "phone_number_id": phone_number_id,
            "recipient_e164": normalized_recipient,
            "text_body": text_body,
            "type": "text",
            "timestamp": int(time.time()),
        }
        self.sent_messages.append(record)

        return OutboundWhatsAppMessageResult(
            wamid=wamid,
            recipient_e164=normalized_recipient,
            status="sent",
        )

    async def send_template_message(
        self,
        phone_number_id: str,
        recipient_e164: str,
        template_name: str,
        language_code: str = "fr",
        components: list[dict[str, Any]] | None = None,
    ) -> OutboundWhatsAppMessageResult:
        """Dispatch local demo template message recording dispatch in memory."""
        normalized_recipient = normalize_phone_number(recipient_e164, "TN")
        wamid = f"wamid.demo.template.{uuid.uuid4()}"

        record = {
            "wamid": wamid,
            "phone_number_id": phone_number_id,
            "recipient_e164": normalized_recipient,
            "template_name": template_name,
            "language_code": language_code,
            "components": components or [],
            "type": "template",
            "timestamp": int(time.time()),
        }
        self.sent_messages.append(record)

        return OutboundWhatsAppMessageResult(
            wamid=wamid,
            recipient_e164=normalized_recipient,
            status="sent",
        )
