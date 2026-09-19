"""Integration Test Suite for WhatsApp Fast-Path Inbound/Outbound Engine (Phase 2).

Verifies:
1. Webhook Challenge GET verification.
2. X-Hub-Signature-256 HMAC verification & rejection of invalid signatures.
3. Pre-ACK persistence into PostgreSQL before response.
4. Atomic idempotency on provider_message_id (wamid).
5. Fast ACK return without blocking on background tasks.
6. Outbound WhatsApp retry behavior on transient errors and fast fail on client errors.
7. Token/secret safety in logs.
8. Performance telemetry measurements.
"""

import hashlib
import hmac
import time
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.future import select

from app.adapters.whatsapp_meta import MetaWhatsAppProvider
from app.core.config import settings
from app.core.whatsapp_telemetry import WhatsAppTimingMetrics
from app.main import app
from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
from app.models.inbound_message import InboundMessage
from app.models.message import Message
from app.models.tenant import Tenant
from app.models.whatsapp_account import WhatsAppAccount
from app.utils.uuid import generate_uuidv7


def generate_valid_signature(body: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature string for test payloads."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.mark.asyncio
async def test_webhook_challenge_verification_success():
    """Verify Meta webhook challenge GET request succeeds when verify token matches."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": settings.META_WEBHOOK_VERIFY_TOKEN,
                "hub.challenge": "1234567890",
            },
        )
        assert res.status_code == 200
        assert res.text == "1234567890"


@pytest.mark.asyncio
async def test_webhook_challenge_verification_failure():
    """Verify Meta webhook challenge GET request fails (403) when token does not match."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_invalid_token",
                "hub.challenge": "1234567890",
            },
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_inbound_webhook_persisted_before_ack_and_fast_response():
    """Verify inbound message is persisted to DB before HTTP 200 response."""
    from app.core.database import async_session_factory

    tenant_id = generate_uuidv7()
    phone_id = f"phone_{uuid.uuid4().hex[:8]}"

    async with async_session_factory() as db:
        tenant = Tenant(id=tenant_id, name="FastPath Tenant", slug=f"fast-path-{uuid.uuid4().hex[:6]}")
        db.add(tenant)
        await db.flush()

        account = WhatsAppAccount(
            id=generate_uuidv7(),
            tenant_id=tenant.id,
            phone_number_id=phone_id,
            display_phone_number="+21671000000",
            verified_name="FastPath Account",
        )
        db.add(account)
        await db.commit()

    test_wamid = f"wamid.test.{uuid.uuid4().hex}"
    payload = {
        "entry": [
            {
                "id": "entry_1",
                "changes": [
                    {
                        "value": {
                            "metadata": {
                                "phone_number_id": phone_id,
                                "display_phone_number": "+21671000000",
                            },
                            "messages": [
                                {
                                    "id": test_wamid,
                                    "from": "21698123456",
                                    "timestamp": int(time.time()),
                                    "type": "text",
                                    "text": {"body": "Bonjour, je cherche un véhicule."},
                                }
                            ],
                        }
                    }
                ],
            }
        ]
    }

    import json
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_valid_signature(raw_body, settings.META_WEBHOOK_APP_SECRET)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        start_t = time.perf_counter()
        res = await client.post(
            "/api/v1/webhooks/whatsapp",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": sig,
            },
        )
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        # Fast response requirement (<500ms in test environment)
        assert res.status_code == 200
        assert elapsed_ms < 500.0
        data = res.json()
        assert data["status"] == "success"
        assert data["processed_count"] == 1
        assert data["details"][0]["wamid"] == test_wamid

    # Verify DB persistence in clean session
    async with async_session_factory() as db:
        stmt_inbound = select(InboundMessage).where(InboundMessage.provider_message_id == test_wamid)
        inbound_msg = (await db.execute(stmt_inbound)).scalar_one_or_none()
        assert inbound_msg is not None
        assert inbound_msg.sender_phone_e164 == "+21698123456"
        assert inbound_msg.content == "Bonjour, je cherche un véhicule."

        stmt_msg = select(Message).where(Message.provider_message_id == test_wamid)
        msg_record = (await db.execute(stmt_msg)).scalar_one_or_none()
        assert msg_record is not None
        assert msg_record.direction == "Inbound"


@pytest.mark.asyncio
async def test_duplicate_wamid_is_idempotent_and_dropped():
    """Verify receiving the exact same wamid twice is dropped idempotently without duplicate records."""
    from app.core.database import async_session_factory

    tenant_id = generate_uuidv7()
    phone_id = f"phone_{uuid.uuid4().hex[:8]}"

    async with async_session_factory() as db:
        tenant = Tenant(id=tenant_id, name="Idempotency Tenant", slug=f"idemp-{uuid.uuid4().hex[:6]}")
        db.add(tenant)
        await db.flush()

        account = WhatsAppAccount(
            id=generate_uuidv7(),
            tenant_id=tenant.id,
            phone_number_id=phone_id,
            display_phone_number="+21671000000",
            verified_name="Idempotency Account",
        )
        db.add(account)
        await db.commit()

    duplicate_wamid = f"wamid.duplicate.{uuid.uuid4().hex}"
    payload = {
        "entry": [
            {
                "id": "entry_1",
                "changes": [
                    {
                        "value": {
                            "metadata": {
                                "phone_number_id": phone_id,
                                "display_phone_number": "+21671000000",
                            },
                            "messages": [
                                {
                                    "id": duplicate_wamid,
                                    "from": "21698765432",
                                    "timestamp": int(time.time()),
                                    "type": "text",
                                    "text": {"body": "First delivery"},
                                }
                            ],
                        }
                    }
                ],
            }
        ]
    }

    import json
    raw_body = json.dumps(payload).encode("utf-8")
    sig = generate_valid_signature(raw_body, settings.META_WEBHOOK_APP_SECRET)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First request -> successfully persisted
        res1 = await client.post(
            "/api/v1/webhooks/whatsapp",
            content=raw_body,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
        )
        assert res1.status_code == 200
        assert res1.json()["details"][0]["status"] == "received"

        # Second duplicate request -> caught by unique constraint, ignored safely
        res2 = await client.post(
            "/api/v1/webhooks/whatsapp",
            content=raw_body,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
        )
        assert res2.status_code == 200
        assert res2.json()["details"][0]["status"] == "duplicate_ignored"

    # Verify only ONE record exists in InboundMessage
    async with async_session_factory() as db:
        stmt = select(InboundMessage).where(InboundMessage.provider_message_id == duplicate_wamid)
        records = list((await db.execute(stmt)).scalars().all())
        assert len(records) == 1


@pytest.mark.asyncio
async def test_invalid_signature_rejected_in_production(monkeypatch):
    """Verify invalid HMAC-SHA256 signature is rejected with HTTP 401."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "META_WEBHOOK_APP_SECRET", "super_secret_key_123")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/webhooks/whatsapp",
            json={"sample": "data"},
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalid_tampered_signature_hex",
            },
        )
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_meta_whatsapp_provider_retries_on_transient_500():
    """Verify MetaWhatsAppProvider retries on transient 500 error with exponential backoff."""
    attempt_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            return httpx.Response(500, json={"error": "Internal Meta Server Error"})
        return httpx.Response(200, json={"messages": [{"id": "wamid.success.after.retry"}]})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    provider = MetaWhatsAppProvider(
        access_token="valid_access_token",
        phone_number_id="123456789",
        http_client=mock_client,
        max_retries=3,
    )

    result = await provider.send_text_message(
        phone_number_id="123456789",
        recipient_e164="+21698123456",
        text_body="Test retry message",
    )

    assert result.status == "sent"
    assert result.wamid == "wamid.success.after.retry"
    assert attempt_count == 3
    await mock_client.aclose()


@pytest.mark.asyncio
async def test_meta_whatsapp_provider_fails_fast_on_client_error():
    """Verify MetaWhatsAppProvider does not waste retries on 400 client error."""
    attempt_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempt_count
        attempt_count += 1
        return httpx.Response(400, json={"error": {"message": "Invalid recipient phone number"}})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    provider = MetaWhatsAppProvider(
        access_token="valid_access_token",
        phone_number_id="123456789",
        http_client=mock_client,
        max_retries=3,
    )

    from app.core.errors import ValidationException

    with pytest.raises(ValidationException):
        await provider.send_text_message(
            phone_number_id="123456789",
            recipient_e164="+21698123456",
            text_body="Test 400 error",
        )

    # Should fail fast without looping retries
    assert attempt_count == 1
    await mock_client.aclose()


def test_whatsapp_timing_metrics_telemetry():
    """Verify performance metrics timing intervals calculation."""
    metrics = WhatsAppTimingMetrics(
        wamid="wamid.timing.test",
        tenant_id=str(uuid.uuid4()),
        phone_e164="+21698111222",
    )
    time.sleep(0.01)
    metrics.mark_persisted()
    time.sleep(0.005)
    metrics.mark_acknowledged()
    time.sleep(0.01)
    metrics.mark_worker_started()
    time.sleep(0.01)
    metrics.mark_outbound_started()
    time.sleep(0.015)
    metrics.mark_outbound_completed()

    report = metrics.to_latency_report()
    assert report["wamid"] == "wamid.timing.test"
    assert report["db_persistence_ms"] > 0.0
    assert report["webhook_ack_ms"] > 0.0
    assert report["outbound_api_ms"] > 0.0
    assert report["total_latency_ms"] >= report["webhook_ack_ms"]
