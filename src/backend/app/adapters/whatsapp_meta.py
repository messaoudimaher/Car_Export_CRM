"""Meta WhatsApp Cloud API Production Adapter (ADR 0002, ADR 0018, BR-007)."""

import hashlib
import hmac
import time
import uuid
from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import ServiceUnavailableException, ValidationException
from app.ports.whatsapp import (
    OutboundWhatsAppMessageResult,
    WhatsAppMessage,
    WhatsAppProvider,
)
from app.utils.phone import extract_whatsapp_id, normalize_phone_number


class MetaWhatsAppProvider(WhatsAppProvider):
    """Production Meta WhatsApp Cloud API implementation of WhatsAppProvider port."""

    def __init__(
        self,
        app_secret: str | None = None,
        access_token: str | None = None,
        phone_number_id: str | None = None,
        api_version: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize MetaWhatsAppProvider with app secret, token, and HTTP client."""
        self.app_secret = app_secret or settings.META_WEBHOOK_APP_SECRET
        self.access_token = access_token or settings.META_WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = phone_number_id or settings.META_WHATSAPP_PHONE_NUMBER_ID
        self.api_version = api_version or settings.META_API_VERSION
        self._http_client = http_client

    def verify_webhook_signature(
        self,
        raw_body: bytes,
        signature_header: str | None,
    ) -> bool:
        """Verify HMAC-SHA256 signature of inbound Meta WhatsApp webhooks (BR-007).

        Header format: "sha256=<hex_digest>"
        """
        if not signature_header or not raw_body or not self.app_secret:
            return False

        signature = signature_header.strip()
        if signature.startswith("sha256="):
            signature = signature[7:]

        expected_hash = hmac.new(
            self.app_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected_hash, signature)

    def parse_webhook_payload(
        self,
        payload: dict[str, Any],
    ) -> list[WhatsAppMessage]:
        """Parse inbound Meta Cloud API JSON webhook payload into WhatsAppMessage DTOs."""
        messages: list[WhatsAppMessage] = []

        if "entry" not in payload or not isinstance(payload["entry"], list):
            return messages

        for entry in payload["entry"]:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                metadata = value.get("metadata", {})
                phone_number_id = str(metadata.get("phone_number_id", ""))
                display_phone_number = str(metadata.get("display_phone_number", ""))

                raw_messages = value.get("messages", [])
                for msg in raw_messages:
                    wamid = str(msg.get("id", f"wamid.meta.{uuid.uuid4()}"))
                    from_phone = str(msg.get("from", ""))
                    if not from_phone.startswith("+"):
                        from_phone = f"+{from_phone}"

                    try:
                        normalized_from = normalize_phone_number(from_phone, "TN")
                    except ValidationException:
                        normalized_from = from_phone

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

    async def send_text_message(
        self,
        phone_number_id: str,
        recipient_e164: str,
        text_body: str,
    ) -> OutboundWhatsAppMessageResult:
        """Dispatch outbound text message via Meta Graph API endpoint."""
        normalized_recipient = normalize_phone_number(recipient_e164, "TN")
        wa_recipient = extract_whatsapp_id(normalized_recipient)
        target_phone_id = (
            phone_number_id
            if (phone_number_id and phone_number_id != "default_phone_number_id")
            else self.phone_number_id
        )
        url = f"https://graph.facebook.com/{self.api_version}/{target_phone_id}/messages"

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": wa_recipient,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": text_body,
            },
        }

        return await self._dispatch_meta_request(url, payload, normalized_recipient)

    async def send_template_message(
        self,
        phone_number_id: str,
        recipient_e164: str,
        template_name: str,
        language_code: str = "fr",
        components: list[dict[str, Any]] | None = None,
    ) -> OutboundWhatsAppMessageResult:
        """Dispatch outbound HSM template message via Meta Graph API endpoint."""
        normalized_recipient = normalize_phone_number(recipient_e164, "TN")
        wa_recipient = extract_whatsapp_id(normalized_recipient)
        target_phone_id = (
            phone_number_id
            if (phone_number_id and phone_number_id != "default_phone_number_id")
            else self.phone_number_id
        )
        url = f"https://graph.facebook.com/{self.api_version}/{target_phone_id}/messages"

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": wa_recipient,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components or [],
            },
        }

        return await self._dispatch_meta_request(url, payload, normalized_recipient)

    async def _dispatch_meta_request(
        self,
        url: str,
        payload: dict[str, Any],
        recipient_e164: str,
    ) -> OutboundWhatsAppMessageResult:
        """Execute HTTP POST request to Meta Cloud API endpoint with Authorization Bearer header."""
        client = self._http_client or httpx.AsyncClient(timeout=10.0)
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code not in (200, 201):
                raise ServiceUnavailableException(
                    f"Meta WhatsApp API HTTP {response.status_code}: {response.text}"
                )

            resp_data = response.json()
            wamid = resp_data.get("messages", [{}])[0].get("id", f"wamid.meta.{uuid.uuid4()}")
            return OutboundWhatsAppMessageResult(
                wamid=wamid,
                recipient_e164=recipient_e164,
                status="sent",
            )
        except httpx.RequestError as err:
            raise ServiceUnavailableException(
                f"Meta WhatsApp API connection failed: {err}"
            ) from err
        finally:
            if not self._http_client:
                await client.aclose()
