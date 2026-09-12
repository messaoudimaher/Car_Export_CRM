"""Demo / Mock LLM Infrastructure Adapter for zero-API-key local execution (ADR 0002)."""

import json
from typing import TypeVar

from pydantic import BaseModel

from app.ports.embedding import EmbeddingProvider, EmbeddingRequest, EmbeddingResponse
from app.ports.llm import LLMCompletionRequest, LLMCompletionResponse, LLMProvider

T = TypeVar("T", bound=BaseModel)


class DemoLLMAdapter(LLMProvider, EmbeddingProvider):
    """Mock LLM and Embedding provider adapter returning deterministic test responses."""

    def __init__(self, mock_response_content: str | None = None) -> None:
        self.mock_response_content = mock_response_content

    async def generate_text(
        self,
        request: LLMCompletionRequest,
    ) -> LLMCompletionResponse:
        """Return mock text completion."""
        content = (
            self.mock_response_content
            or f"Demo LLM Response for prompt: '{request.prompt[:50]}...'"
        )
        return LLMCompletionResponse(
            content=content,
            model=request.model,
            prompt_tokens=15,
            completion_tokens=25,
            total_tokens=40,
            latency_ms=10.0,
            finish_reason="stop",
            raw_response={"demo": True, "prompt": request.prompt},
        )

    async def generate_structured_output(
        self,
        request: LLMCompletionRequest,
        schema: type[T],
    ) -> tuple[T, LLMCompletionResponse]:
        """Generate mock structured output object matching target Pydantic schema."""
        if self.mock_response_content:
            raw_json = self.mock_response_content
        else:
            # Build mock dictionary satisfying schema fields
            mock_dict: dict[str, object] = {}
            for field_name, field_info in schema.model_fields.items():
                annotation = str(field_info.annotation)
                if "int" in annotation:
                    mock_dict[field_name] = 2023
                elif "float" in annotation or "Decimal" in annotation:
                    mock_dict[field_name] = 25000.00
                elif "bool" in annotation:
                    mock_dict[field_name] = True
                elif "list" in annotation:
                    mock_dict[field_name] = []
                else:
                    mock_dict[field_name] = f"demo_{field_name}"
            raw_json = json.dumps(mock_dict)

        validated_obj = schema.model_validate_json(raw_json)
        response_dto = LLMCompletionResponse(
            content=raw_json,
            model=request.model,
            prompt_tokens=20,
            completion_tokens=30,
            total_tokens=50,
            latency_ms=12.0,
            finish_reason="stop",
            raw_response={"demo": True},
        )
        return validated_obj, response_dto

    async def generate_embeddings(
        self,
        request: EmbeddingRequest,
    ) -> EmbeddingResponse:
        """Generate mock 1536-dimensional float vector embeddings."""
        mock_vector = [0.01] * 1536
        embeddings = [mock_vector for _ in request.texts]

        return EmbeddingResponse(
            embeddings=embeddings,
            model=request.model,
            prompt_tokens=len(request.texts) * 10,
            latency_ms=5.0,
        )
