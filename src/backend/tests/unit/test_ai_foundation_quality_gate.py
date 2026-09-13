"""Quality Gate Unit Tests for WS-11 AI Foundation Architectural Refinements."""

from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from app.adapters.llm_demo import DemoLLMAdapter
from app.adapters.llm_openai import OpenAIAdapter
from app.core.config import Settings
from app.core.errors import (
    AISchemaValidationException,
    ServiceUnavailableException,
    UnauthorizedException,
    ValidationException,
)
from app.ports.embedding import EmbeddingRequest
from app.ports.llm import LLMCompletionRequest
from app.services.ai_cost_tracker import AICostTracker
from app.services.ai_validation_service import AIValidationService, sanitize_log_text


class MockTargetSchema(BaseModel):
    name: str
    count: int


@pytest.mark.asyncio
async def test_openai_adapter_fails_fast_on_401_unauthorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify 401 Unauthorized fails fast immediately on attempt 1 without retrying."""
    call_count = 0

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(401, json={"error": {"message": "Invalid API key"}})

    transport = httpx.MockTransport(mock_handler)
    orig_client = httpx.AsyncClient

    def _client_factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return orig_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _client_factory)
    adapter = OpenAIAdapter(api_key="invalid_key", max_retries=3)

    with pytest.raises(UnauthorizedException) as exc_info:
        req = LLMCompletionRequest(prompt="Test prompt")
        await adapter.generate_text(req)

    assert call_count == 1
    assert "authentication failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_openai_adapter_fails_fast_on_400_bad_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify 400 Bad Request fails fast immediately on attempt 1 without retrying."""
    call_count = 0

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(400, json={"error": {"message": "Invalid parameter model"}})

    transport = httpx.MockTransport(mock_handler)
    orig_client = httpx.AsyncClient

    def _client_factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return orig_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _client_factory)
    adapter = OpenAIAdapter(api_key="valid_key", max_retries=3)

    with pytest.raises(ValidationException) as exc_info:
        req = LLMCompletionRequest(prompt="Test prompt")
        await adapter.generate_text(req)

    assert call_count == 1
    assert "invalid request" in str(exc_info.value)


@pytest.mark.asyncio
async def test_openai_adapter_retries_transient_503_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify transient 503 error is retried up to max_retries."""
    call_count = 0

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(503, json={"error": {"message": "Service Overloaded"}})

    transport = httpx.MockTransport(mock_handler)
    orig_client = httpx.AsyncClient

    def _client_factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return orig_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _client_factory)
    adapter = OpenAIAdapter(api_key="valid_key", max_retries=2)

    with pytest.raises(ServiceUnavailableException):
        req = LLMCompletionRequest(prompt="Test prompt")
        await adapter.generate_text(req)

    assert call_count == 2


def test_validation_service_pii_sanitization() -> None:
    """Verify customer PII (phone numbers, emails) are redacted in log previews."""
    raw_with_pii = (
        "Customer John Doe (email: john.doe@example.com, phone: +21698765432) wants a car."
    )
    sanitized = sanitize_log_text(raw_with_pii)

    assert "john.doe@example.com" not in sanitized
    assert "+21698765432" not in sanitized
    assert "[REDACTED_EMAIL]" in sanitized
    assert "[REDACTED_PHONE]" in sanitized


@pytest.mark.asyncio
async def test_validation_service_logs_sanitized_preview(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify Layer 2 validation failure log contains sanitized raw preview."""
    caplog.set_level("WARNING")
    service = AIValidationService()

    raw_pii_invalid = "Contact me at customer@domain.tn or +21622334455. Output is not JSON at all."

    with pytest.raises(AISchemaValidationException):
        await service.validate_response(raw_pii_invalid, MockTargetSchema, max_retries=0)

    rec = caplog.records[-1]
    raw_preview = getattr(rec, "raw_preview", "")
    assert "customer@domain.tn" not in raw_preview
    assert "+21622334455" not in raw_preview
    assert "[REDACTED_EMAIL]" in raw_preview
    assert "[REDACTED_PHONE]" in raw_preview


def test_cost_tracker_unregistered_model_fallback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify unlisted model flags is_fallback_pricing=True and logs warning."""
    caplog.set_level("INFO")
    tracker = AICostTracker()
    cost = tracker.track_usage(
        model_name="unregistered-custom-llm",
        prompt_tokens=1000,
        completion_tokens=500,
    )

    assert cost > 0
    # Search caplog records for ai_token_usage_telemetry log
    telemetry_rec = [r for r in caplog.records if r.message == "ai_token_usage_telemetry"][-1]
    assert getattr(telemetry_rec, "is_fallback_pricing", None) is True
    assert getattr(telemetry_rec, "is_authoritative_billing", None) is False


def test_settings_fails_fast_when_openai_key_missing_in_prod() -> None:
    """Verify Settings raises ValueError when LLM_PROVIDER=openai in prod without OPENAI_API_KEY."""
    with pytest.raises(ValueError, match="OPENAI_API_KEY is missing or invalid"):
        Settings(
            ENVIRONMENT="production",
            LLM_PROVIDER="openai",
            LLM_PROVIDER_API_KEY="",
            JWT_SECRET="prod_secret_key_satisfying_length_32_bytes_long",  # noqa: S106
            META_WEBHOOK_APP_SECRET="prod_meta_secret_key_12345",  # noqa: S106
            S3_ACCESS_KEY_ID="prod_s3_access_key_id_12345",  # noqa: S106
            S3_SECRET_ACCESS_KEY="prod_s3_secret_access_key_12345",  # noqa: S106
        )


@pytest.mark.asyncio
async def test_embedding_provider_dimensions_and_tenant_context() -> None:
    """Verify EmbeddingProvider returns requested dimensions and tenant_id metadata."""
    adapter = DemoLLMAdapter()
    req = EmbeddingRequest(
        texts=["Vehicle specification text chunk"],
        model="text-embedding-3-small",
        dimensions=768,
        tenant_id="tenant_xyz_123",
    )

    res = await adapter.generate_embeddings(req)
    assert res.dimensions == 768
    assert len(res.embeddings[0]) == 768
    assert res.tenant_id == "tenant_xyz_123"


def test_ai_foundation_has_zero_direct_db_mutations() -> None:
    """Verify AI foundation files do not import SQLAlchemy or execute DB mutations."""
    import inspect

    from app.services import ai_cost_tracker, ai_validation_service

    for module in (ai_validation_service, ai_cost_tracker):
        source = inspect.getsource(module)
        assert "sqlalchemy" not in source.lower()
        assert "async_session" not in source.lower()
        assert ".commit(" not in source.lower()
