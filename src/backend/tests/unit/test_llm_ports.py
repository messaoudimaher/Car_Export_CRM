"""Unit tests for LLM and Embedding ports & adapters (TASK-1101, ADR 0002)."""

import sys
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from app.adapters.llm_demo import DemoLLMAdapter
from app.adapters.llm_openai import OpenAIAdapter
from app.core.errors import ValidationException
from app.ports.embedding import EmbeddingRequest
from app.ports.llm import LLMCompletionRequest


class SampleExtractionSchema(BaseModel):
    """Sample Pydantic schema for testing structured LLM extraction."""

    make: str
    model: str
    year: int
    fcr_eligible: bool


@pytest.mark.asyncio
async def test_demo_llm_adapter_text_generation() -> None:
    """Verify DemoLLMAdapter text completion generation."""
    adapter = DemoLLMAdapter()
    req = LLMCompletionRequest(prompt="Bonjour, je cherche une voiture export.")
    res = await adapter.generate_text(req)

    assert res.content.startswith("Demo LLM Response")
    assert res.prompt_tokens == 15
    assert res.completion_tokens == 25
    assert res.total_tokens == 40
    assert res.finish_reason == "stop"


@pytest.mark.asyncio
async def test_demo_llm_adapter_structured_output() -> None:
    """Verify DemoLLMAdapter structured Pydantic schema extraction."""
    adapter = DemoLLMAdapter()
    req = LLMCompletionRequest(prompt="BMW X5 2023 FCR")
    data, res = await adapter.generate_structured_output(req, SampleExtractionSchema)

    assert isinstance(data, SampleExtractionSchema)
    assert data.make == "demo_make"
    assert data.year == 2023
    assert data.fcr_eligible is True
    assert res.total_tokens == 50


@pytest.mark.asyncio
async def test_demo_llm_adapter_embeddings() -> None:
    """Verify DemoLLMAdapter generates 1536-dimensional float vector embeddings."""
    adapter = DemoLLMAdapter()
    req = EmbeddingRequest(texts=["Volkswagen Golf 8", "BMW Série 3"])
    res = await adapter.generate_embeddings(req)

    assert len(res.embeddings) == 2
    assert len(res.embeddings[0]) == 1536
    assert res.embeddings[0][0] == 0.01


@pytest.mark.asyncio
async def test_openai_adapter_text_generation_success() -> None:
    """Verify OpenAIAdapter executes direct HTTP POST call for chat completion."""
    adapter = OpenAIAdapter(api_key="test_key_123")

    mock_json = {
        "model": "gpt-4o-mini",
        "choices": [
            {
                "message": {"content": "Bonjour, comment puis-je vous aider?"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
    }

    with patch.object(adapter, "_post_with_retry", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_json

        req = LLMCompletionRequest(prompt="Bonjour")
        res = await adapter.generate_text(req)

        assert res.content == "Bonjour, comment puis-je vous aider?"
        assert res.total_tokens == 20
        assert res.model == "gpt-4o-mini"
        mock_post.assert_awaited_once()


@pytest.mark.asyncio
async def test_openai_adapter_structured_output_success() -> None:
    """Verify OpenAIAdapter parses JSON schema output into Pydantic model."""
    adapter = OpenAIAdapter(api_key="test_key_123")

    mock_json = {
        "model": "gpt-4o-mini",
        "choices": [
            {
                "message": {
                    "content": '{"make": "Audi", "model": "A4", "year": 2022, "fcr_eligible": true}'
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 30, "completion_tokens": 15, "total_tokens": 45},
    }

    with patch.object(adapter, "_post_with_retry", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_json

        req = LLMCompletionRequest(prompt="Audi A4 2022 FCR")
        data, res = await adapter.generate_structured_output(req, SampleExtractionSchema)

        assert data.make == "Audi"
        assert data.model == "A4"
        assert data.year == 2022
        assert data.fcr_eligible is True
        assert res.total_tokens == 45


@pytest.mark.asyncio
async def test_openai_adapter_structured_output_invalid_json_raises_validation_exception() -> None:
    """Verify OpenAIAdapter raises ValidationException when LLM returns invalid JSON."""
    adapter = OpenAIAdapter(api_key="test_key_123")

    mock_json = {
        "model": "gpt-4o-mini",
        "choices": [{"message": {"content": "Not a valid JSON string"}, "finish_reason": "stop"}],
        "usage": {},
    }

    with patch.object(adapter, "_post_with_retry", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_json

        req = LLMCompletionRequest(prompt="Invalid output")
        with pytest.raises(ValidationException, match="Failed to parse structured LLM response"):
            await adapter.generate_structured_output(req, SampleExtractionSchema)


@pytest.mark.asyncio
async def test_openai_adapter_embeddings_success() -> None:
    """Verify OpenAIAdapter generates embeddings via HTTP POST."""
    adapter = OpenAIAdapter(api_key="test_key_123")

    mock_json = {
        "model": "text-embedding-3-small",
        "data": [{"embedding": [0.1, 0.2, 0.3]}],
        "usage": {"prompt_tokens": 5},
    }

    with patch.object(adapter, "_post_with_retry", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_json

        req = EmbeddingRequest(texts=["Audi A4"])
        res = await adapter.generate_embeddings(req)

        assert len(res.embeddings) == 1
        assert res.embeddings[0] == [0.1, 0.2, 0.3]
        assert res.prompt_tokens == 5


def test_openai_sdk_not_imported_in_codebase() -> None:
    """Verify AGENTS.md Rule 1: 'openai' Python SDK is not imported in sys.modules."""
    assert "openai" not in sys.modules
