"""Unit tests for Google Gemini Adapter (ADR 0002, LLMProvider port)."""

from unittest.mock import AsyncMock, patch
import httpx
import pytest
from pydantic import BaseModel

from app.adapters.llm_gemini import GeminiAdapter
from app.core.errors import ServiceUnavailableException, UnauthorizedException, ValidationException
from app.ports.embedding import EmbeddingRequest
from app.ports.llm import LLMCompletionRequest


class SampleExtractionSchema(BaseModel):
    make: str
    model: str
    year: int
    fcr_eligible: bool


def test_gemini_adapter_instantiation() -> None:
    """Verify GeminiAdapter initializes with custom or default API key."""
    adapter = GeminiAdapter(api_key="AIzaSyDummyKeyForTesting")
    assert adapter.api_key == "AIzaSyDummyKeyForTesting"
    assert "googleapis.com" in adapter.base_url


def test_normalize_model_name() -> None:
    """Verify model name mapping from generic/OpenAI names to Gemini names."""
    adapter = GeminiAdapter(api_key="AIzaSyDummyKey")
    assert adapter._normalize_model_name("gemini-1.5-flash") == "gemini-1.5-flash"
    assert adapter._normalize_model_name("models/gemini-2.0-flash") == "gemini-2.0-flash"
    from app.core.config import settings
    assert adapter._normalize_model_name("gpt-4o-mini") == settings.GEMINI_MODEL


@pytest.mark.asyncio
async def test_gemini_generate_text_mocked_success() -> None:
    """Verify generate_text parses Gemini response JSON correctly."""
    adapter = GeminiAdapter(api_key="test_key")
    fake_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Bonjour! Nous pouvons vous proposer une Peugeot 3008."}]
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 25,
            "candidatesTokenCount": 18,
            "totalTokenCount": 43,
        },
    }

    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_response

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        req = LLMCompletionRequest(
            prompt="Proposer une voiture",
            model="gemini-1.5-flash",
            temperature=0.3,
            system_prompt="Tu es un conseiller commercial car export.",
        )
        res = await adapter.generate_text(req)

        assert "Peugeot 3008" in res.content
        assert res.prompt_tokens == 25
        assert res.completion_tokens == 18
        assert res.finish_reason == "stop"


@pytest.mark.asyncio
async def test_gemini_generate_structured_output_mocked_success() -> None:
    """Verify generate_structured_output parses and validates against Pydantic schema."""
    adapter = GeminiAdapter(api_key="test_key")
    fake_json_text = '{"make": "Volkswagen", "model": "Golf 8", "year": 2022, "fcr_eligible": true}'
    fake_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": fake_json_text}]
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 50,
            "candidatesTokenCount": 30,
            "totalTokenCount": 80,
        },
    }

    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_response

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        req = LLMCompletionRequest(
            prompt="Extract: VW Golf 8 2022 FCR",
            model="gemini-1.5-flash",
        )
        validated, res = await adapter.generate_structured_output(req, SampleExtractionSchema)

        assert isinstance(validated, SampleExtractionSchema)
        assert validated.make == "Volkswagen"
        assert validated.model == "Golf 8"
        assert validated.year == 2022
        assert validated.fcr_eligible is True
        assert res.total_tokens == 80


@pytest.mark.asyncio
async def test_gemini_generate_embeddings_mocked_success() -> None:
    """Verify generate_embeddings calls batchEmbedContents correctly."""
    adapter = GeminiAdapter(api_key="test_key")
    fake_response = {
        "embeddings": [
            {"values": [0.123, 0.456, -0.789]},
            {"values": [0.001, -0.002, 0.003]},
        ]
    }

    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_response

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        req = EmbeddingRequest(
            texts=["Peugeot 3008 Allure", "Renault Megane E-Tech"],
            dimensions=3,
        )
        res = await adapter.generate_embeddings(req)

        assert len(res.embeddings) == 2
        assert res.dimensions == 3
        assert res.embeddings[0] == [0.123, 0.456, -0.789]


@pytest.mark.asyncio
async def test_gemini_unauthorized_error_raises_exception() -> None:
    """Verify HTTP 401/403 raises UnauthorizedException."""
    adapter = GeminiAdapter(api_key="invalid_key", max_retries=1)

    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 401

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        req = LLMCompletionRequest(prompt="Hello")
        with pytest.raises(UnauthorizedException):
            await adapter.generate_text(req)
