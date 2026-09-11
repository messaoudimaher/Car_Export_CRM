"""API Integration Tests for Webhook Signature Verification Middleware (BR-007)."""

import hashlib
import hmac

import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_webhook_signature_valid(client: AsyncClient) -> None:
    """Verify valid HMAC-SHA256 signature passes verification."""
    payload = b'{"object":"whatsapp_business_account","entry":[]}'
    secret = settings.META_WEBHOOK_APP_SECRET.encode("utf-8")
    expected_digest = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    signature_header = f"sha256={expected_digest}"

    response = await client.post(
        "/api/v1/webhooks/whatsapp",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature_header,
        },
    )
    # Verification passed (may return 404 or 200 depending on route registration, but not 401)
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_webhook_signature_invalid(client: AsyncClient) -> None:
    """Verify invalid HMAC-SHA256 signature returns 401 Unauthorized."""
    payload = b'{"object":"whatsapp_business_account","entry":[]}'
    signature_header = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

    response = await client.post(
        "/api/v1/webhooks/whatsapp",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature_header,
        },
    )
    assert response.status_code == 401
    detail = response.json().get("detail", "")
    assert "Invalid or missing X-Hub-Signature-256" in detail or "signature" in detail.lower()


@pytest.mark.asyncio
async def test_webhook_signature_missing(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify missing signature header returns 401 when dev bypass is disabled."""
    monkeypatch.setattr(settings, "META_WEBHOOK_APP_SECRET", "prod_secret_key_12345")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    payload = b'{"object":"whatsapp_business_account","entry":[]}'
    response = await client.post(
        "/api/v1/webhooks/whatsapp",
        content=payload,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_signature_demo_bypass(client: AsyncClient) -> None:
    """Verify demo_valid_signature header passes verification."""
    payload = b'{"object":"whatsapp_business_account","entry":[]}'
    response = await client.post(
        "/api/v1/webhooks/whatsapp",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=demo_valid_signature",
        },
    )
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_webhook_signature_bypasses_non_webhook_routes(client: AsyncClient) -> None:
    """Verify non-webhook endpoints ignore signature checks."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
