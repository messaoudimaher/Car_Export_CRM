"""OpenAI Infrastructure Adapter using direct HTTP client (AGENTS.md Rule 1, ADR 0002)."""

import asyncio
import json
import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.errors import ServiceUnavailableException, ValidationException
from app.ports.embedding import EmbeddingProvider, EmbeddingRequest, EmbeddingResponse
from app.ports.llm import LLMCompletionRequest, LLMCompletionResponse, LLMProvider

T = TypeVar("T", bound=BaseModel)


class OpenAIAdapter(LLMProvider, EmbeddingProvider):
    """OpenAI API implementation of LLM/Embedding ports using direct HTTP calls."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries

    def _get_headers(self) -> dict[str, str]:
        """Construct Authorization and Content-Type HTTP headers."""
        key = self.api_key or "dev_openai_key"
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    async def _post_with_retry(
        self,
        endpoint: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        """Execute async POST request with 3x exponential backoff retry on transient failure."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_headers()

        last_exception: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    if response.status_code == 200:
                        return response.json()  # type: ignore[no-any-return]

                    if (
                        response.status_code in (429, 500, 502, 503, 504)
                        and attempt < self.max_retries
                    ):
                        backoff = 0.5 * (2 ** (attempt - 1))
                        await asyncio.sleep(backoff)
                        continue

                    response.raise_for_status()
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_exception = exc
                if attempt < self.max_retries:
                    backoff = 0.5 * (2 ** (attempt - 1))
                    await asyncio.sleep(backoff)
                    continue

        msg = f"OpenAI API request to '{endpoint}' failed: {last_exception}"
        raise ServiceUnavailableException(msg) from last_exception

    async def generate_text(
        self,
        request: LLMCompletionRequest,
    ) -> LLMCompletionResponse:
        """Generate text completion from OpenAI Chat Completions API."""
        start_time = time.perf_counter()

        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        if request.messages:
            messages.extend(request.messages)
        else:
            messages.append({"role": "user", "content": request.prompt})

        payload: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        res_json = await self._post_with_retry(
            endpoint="chat/completions",
            payload=payload,
            timeout_seconds=request.timeout_seconds,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        choices = res_json.get("choices", [])
        if not choices:
            raise ServiceUnavailableException("OpenAI API returned empty choices list")

        choice = choices[0]
        content = choice.get("message", {}).get("content", "") or ""
        finish_reason = choice.get("finish_reason", "stop") or "stop"
        usage = res_json.get("usage", {})

        return LLMCompletionResponse(
            content=content,
            model=res_json.get("model", request.model),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            raw_response=res_json,
        )

    async def generate_structured_output(
        self,
        request: LLMCompletionRequest,
        schema: type[T],
    ) -> tuple[T, LLMCompletionResponse]:
        """Generate structured JSON output validated against Pydantic schema."""
        start_time = time.perf_counter()

        system_instruction = request.system_prompt or "You are an accurate extraction assistant."
        json_prompt = (
            f"{system_instruction}\n\n"
            f"MUST return ONLY valid JSON matching this schema structure:\n"
            f"{json.dumps(schema.model_json_schema(), indent=2)}"
        )

        messages: list[dict[str, str]] = [{"role": "system", "content": json_prompt}]
        if request.messages:
            messages.extend(request.messages)
        else:
            messages.append({"role": "user", "content": request.prompt})

        payload: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
            "response_format": {"type": "json_object"},
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        res_json = await self._post_with_retry(
            endpoint="chat/completions",
            payload=payload,
            timeout_seconds=request.timeout_seconds,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        choices = res_json.get("choices", [])
        if not choices:
            raise ServiceUnavailableException("OpenAI API returned empty choices list")

        content_raw = choices[0].get("message", {}).get("content", "") or "{}"
        try:
            parsed_json = json.loads(content_raw)
            validated_obj = schema.model_validate(parsed_json)
        except (json.JSONDecodeError, ValidationError) as exc:
            msg = f"Failed to parse structured LLM response into schema '{schema.__name__}': {exc}"
            raise ValidationException(msg) from exc

        usage = res_json.get("usage", {})
        response_dto = LLMCompletionResponse(
            content=content_raw,
            model=res_json.get("model", request.model),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_ms=latency_ms,
            finish_reason=choices[0].get("finish_reason", "stop") or "stop",
            raw_response=res_json,
        )
        return validated_obj, response_dto

    async def generate_embeddings(
        self,
        request: EmbeddingRequest,
    ) -> EmbeddingResponse:
        """Generate high-dimensional vector embeddings via OpenAI Embeddings API."""
        start_time = time.perf_counter()

        payload: dict[str, Any] = {
            "model": request.model,
            "input": request.texts,
        }

        res_json = await self._post_with_retry(
            endpoint="embeddings",
            payload=payload,
            timeout_seconds=request.timeout_seconds,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        data = res_json.get("data", [])
        embeddings = [item.get("embedding", []) for item in data]
        usage = res_json.get("usage", {})

        return EmbeddingResponse(
            embeddings=embeddings,
            model=res_json.get("model", request.model),
            prompt_tokens=usage.get("prompt_tokens", 0),
            latency_ms=latency_ms,
        )
