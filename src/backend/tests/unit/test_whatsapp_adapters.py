"""Unit tests for DemoWhatsAppProvider and MetaWhatsAppProvider (ADR 0002, ADR 0018, BR-007)."""

import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.whatsapp_demo import DemoWhatsAppProvider
from app.adapters.whatsapp_meta import MetaWhatsAppProvider
from app.core.errors import ServiceUnavailableException


@pytest.mark.asyncio
async def test_demo_whatsapp_provider_send_text_message() -> None:
    """Verify DemoWhatsAppProvider records outbound text messages in memory."""
    provider = DemoWhatsAppProvider()
    result = await provider.send_text_message(
        phone_number_id="phone_id_123",
        recipient_e164="098123456",
        text_body="Bonjour, votre devis est prêt!",
    )

    assert result.status == "sent"
    assert result.recipient_e164 == "+21698123456"
    assert result.wamid.startswith("wamid.demo.")

    assert len(provider.sent_messages) == 1
    sent_item = provider.sent_messages[0]
    assert sent_item["recipient_e164"] == "+21698123456"
    assert sent_item["text_body"] == "Bonjour, votre devis est prêt!"
    assert sent_item["phone_number_id"] == "phone_id_123"


@pytest.mark.asyncio
async def test_demo_whatsapp_provider_send_template_message() -> None:
    """Verify DemoWhatsAppProvider records outbound HSM template messages."""
    provider = DemoWhatsAppProvider()
    result = await provider.send_template_message(
        phone_number_id="phone_id_123",
        recipient_e164="+33612345678",
        template_name="quote_ready_v1",
        language_code="fr",
        components=[{"type": "body", "parameters": [{"type": "text", "text": "Golf 8"}]}],
    )

    assert result.status == "sent"
    assert result.recipient_e164 == "+33612345678"
    assert result.wamid.startswith("wamid.demo.template.")

    assert len(provider.sent_messages) == 1
    sent_item = provider.sent_messages[0]
    assert sent_item["template_name"] == "quote_ready_v1"
    assert sent_item["language_code"] == "fr"


def test_demo_whatsapp_provider_parse_webhook_payload() -> None:
    """Verify DemoWhatsAppProvider parses Meta JSON payloads and simplified demo payloads."""
    provider = DemoWhatsAppProvider()

    # Meta format payload
    meta_payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {
                                "phone_number_id": "phone_123",
                                "display_phone_number": "+21671000000",
                            },
                            "messages": [
                                {
                                    "id": "wamid.inbound.100",
                                    "from": "21698123456",
                                    "timestamp": 1726090000,
                                    "type": "text",
                                    "text": {"body": "Je cherche une Peugeot 208"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    parsed = provider.parse_webhook_payload(meta_payload)
    assert len(parsed) == 1
    msg = parsed[0]
    assert msg.wamid == "wamid.inbound.100"
    assert msg.phone_number_id == "phone_123"
    assert msg.from_phone_e164 == "+21698123456"
    assert msg.wa_id == "21698123456"
    assert msg.text_body == "Je cherche une Peugeot 208"

    # Simplified demo payload
    demo_payload = {
        "from": "098123456",
        "text": "Hello, interested in exporting to Tunisia",
    }
    parsed_demo = provider.parse_webhook_payload(demo_payload)
    assert len(parsed_demo) == 1
    assert parsed_demo[0].from_phone_e164 == "+21698123456"
    assert parsed_demo[0].text_body == "Hello, interested in exporting to Tunisia"


def test_meta_whatsapp_provider_verify_signature_valid_and_invalid() -> None:
    """Verify MetaWhatsAppProvider HMAC-SHA256 signature verification (BR-007)."""
    app_secret = "test_meta_app_secret_123456789"  # noqa: S105, S106
    provider = MetaWhatsAppProvider(app_secret=app_secret)

    body_bytes = b'{"object":"whatsapp_business_account","entry":[]}'
    computed_sig = hmac.new(app_secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

    # Valid signature with sha256= prefix
    valid_header = f"sha256={computed_sig}"
    assert provider.verify_webhook_signature(body_bytes, valid_header) is True

    # Valid signature without prefix
    assert provider.verify_webhook_signature(body_bytes, computed_sig) is True

    # Tampered signature
    assert provider.verify_webhook_signature(body_bytes, "sha256=invalid_hash_value") is False

    # Missing signature or body
    assert provider.verify_webhook_signature(body_bytes, None) is False
    assert provider.verify_webhook_signature(b"", valid_header) is False


def test_meta_whatsapp_provider_parse_webhook_payload() -> None:
    """Verify MetaWhatsAppProvider extracts inbound messages from Meta Cloud API webhook payload."""
    provider = MetaWhatsAppProvider(app_secret="test_secret")  # noqa: S105, S106
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {
                                "phone_number_id": "meta_phone_999",
                                "display_phone_number": "+21671111111",
                            },
                            "messages": [
                                {
                                    "id": "wamid.HBgLMjE2OTgxMjM0NTYVAg==",
                                    "from": "21698123456",
                                    "timestamp": 1726095000,
                                    "type": "text",
                                    "text": {"body": "Quel est le prix pour la Golf?"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    messages = provider.parse_webhook_payload(payload)
    assert len(messages) == 1
    msg = messages[0]
    assert msg.wamid == "wamid.HBgLMjE2OTgxMjM0NTYVAg=="
    assert msg.phone_number_id == "meta_phone_999"
    assert msg.from_phone_e164 == "+21698123456"
    assert msg.wa_id == "21698123456"
    assert msg.text_body == "Quel est le prix pour la Golf?"


@pytest.mark.asyncio
async def test_meta_whatsapp_provider_send_text_message_success() -> None:
    """Verify MetaWhatsAppProvider formats outbound HTTP POST request to Meta Cloud API endpoint."""
    mock_http_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "messaging_product": "whatsapp",
        "contacts": [{"input": "+21698123456", "wa_id": "21698123456"}],
        "messages": [{"id": "wamid.HBgLMjE2OTgxMjM0NTYVAg=="}],
    }
    mock_http_client.post.return_value = mock_response

    provider = MetaWhatsAppProvider(
        app_secret="test_secret",  # noqa: S105, S106
        http_client=mock_http_client,
    )

    result = await provider.send_text_message(
        phone_number_id="109876543210",
        recipient_e164="098123456",
        text_body="Votre devis FCR a été généré.",
    )

    assert result.status == "sent"
    assert result.recipient_e164 == "+21698123456"
    assert result.wamid == "wamid.HBgLMjE2OTgxMjM0NTYVAg=="

    mock_http_client.post.assert_awaited_once()
    call_args = mock_http_client.post.call_args
    assert "https://graph.facebook.com/v19.0/109876543210/messages" in call_args[0]
    payload = call_args[1]["json"]
    assert payload["messaging_product"] == "whatsapp"
    assert payload["to"] == "+21698123456"
    assert payload["type"] == "text"
    assert payload["text"]["body"] == "Votre devis FCR a été généré."


@pytest.mark.asyncio
async def test_meta_whatsapp_provider_http_error_raises_service_unavailable() -> None:
    """Verify MetaWhatsAppProvider raises ServiceUnavailableException on HTTP error."""
    mock_http_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Meta Server Error"
    mock_http_client.post.return_value = mock_response

    provider = MetaWhatsAppProvider(
        app_secret="test_secret",  # noqa: S105, S106
        http_client=mock_http_client,
    )

    with pytest.raises(ServiceUnavailableException, match="Meta WhatsApp API HTTP 500"):
        await provider.send_text_message(
            phone_number_id="109876543210",
            recipient_e164="+21698123456",
            text_body="Test error message",
        )
