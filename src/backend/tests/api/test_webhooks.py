"""API Integration Tests for Meta WhatsApp Webhook Handlers (BR-007, BR-008)."""

import hashlib
import hmac
import json
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.database import get_db_session
from app.main import create_app
from app.models.whatsapp_account import WhatsAppAccount


@pytest.mark.asyncio
async def test_verify_webhook_challenge_success(client: AsyncClient) -> None:
    """Verify GET webhook challenge verification returns hub.challenge text on match."""
    challenge = "test_challenge_code_998877"
    response = await client.get(
        "/api/v1/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": settings.META_WEBHOOK_VERIFY_TOKEN,
            "hub.challenge": challenge,
        },
    )
    assert response.status_code == 200
    assert response.text == challenge


@pytest.mark.asyncio
async def test_verify_webhook_challenge_invalid_token(client: AsyncClient) -> None:
    """Verify GET webhook challenge returns 403 on token mismatch."""
    response = await client.get(
        "/api/v1/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "invalid_verify_token_12345",
            "hub.challenge": "challenge_code",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_receive_whatsapp_webhook_persistence_and_deduplication() -> None:
    """Verify inbound WhatsApp message persistence and wamid deduplication (BR-008)."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    app = create_app()

    async def override_get_db_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    tenant_id = uuid.uuid4()
    account_id = uuid.uuid4()

    account = WhatsAppAccount(
        id=account_id,
        tenant_id=tenant_id,
        phone_number_id="10555444332211",
        display_phone_number="+15554443322",
    )

    # Mock DB query execution
    exec_result_mock = MagicMock()
    exec_result_mock.scalar_one_or_none.return_value = account
    exec_result_mock.scalars().first.return_value = account
    mock_session.execute.return_value = exec_result_mock

    wamid = "wamid.HBgLMTIxNjk4MTIzNDU2FQIAERgSQjEwNTU1NDQ0MzMyMjExAA=="
    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15554443322",
                                "phone_number_id": "10555444332211",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Maher Messaoudi"},
                                    "wa_id": "21698123456",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "21698123456",
                                    "id": wamid,
                                    "timestamp": "1773000000",
                                    "text": {"body": "Bonjour, je cherche une Golf 8 avec FCR."},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    secret = settings.META_WEBHOOK_APP_SECRET.encode("utf-8")
    digest = hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()
    signature_header = f"sha256={digest}"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/v1/webhooks/whatsapp",
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature_header,
            },
        )

    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    assert res_data["processed_count"] == 1
    assert res_data["details"][0]["status"] == "received"
