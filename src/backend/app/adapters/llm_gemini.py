"""Google Gemini Infrastructure Adapter using direct HTTP REST API (AGENTS.md Rule 1, ADR 0002)."""

import asyncio
import json
import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.errors import ServiceUnavailableException, UnauthorizedException, ValidationException
from app.ports.embedding import EmbeddingProvider, EmbeddingRequest, EmbeddingResponse
from app.ports.llm import LLMCompletionRequest, LLMCompletionResponse, LLMProvider

T = TypeVar("T", bound=BaseModel)


class GeminiAdapter(LLMProvider, EmbeddingProvider):
    """Google Gemini API implementation of LLM/Embedding ports using direct async HTTP calls."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        max_retries: int = 5,
    ) -> None:
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries

    async def _post_with_retry(
        self,
        endpoint: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        """Execute async POST request to Gemini REST API with exponential backoff on transient errors."""
        key = self.api_key or "dev_gemini_key"
        url = f"{self.base_url}/{endpoint.lstrip('/')}?key={key}"
        headers = {"Content-Type": "application/json"}

        last_exception: Exception | None = None
        current_endpoint = endpoint
        fallback_models = [
            "gemini-3.5-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-3.1-flash-lite",
        ]
        
        for attempt in range(1, self.max_retries + 1):
            url = f"{self.base_url}/{current_endpoint.lstrip('/')}?key={key}"
            try:
                async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    if response.status_code == 200:
                        return response.json()  # type: ignore[no-any-return]

                    # Non-transient client errors fail fast immediately
                    if response.status_code in (401, 403):
                        raise UnauthorizedException(
                            f"Gemini API authentication failed (HTTP {response.status_code}). Check your GEMINI_API_KEY."
                        )
                    if response.status_code in (400, 404, 422):
                        err_text = response.text[:300]
                        raise ValidationException(
                            f"Gemini API invalid request (HTTP {response.status_code}): {err_text}"
                        )

                    # Transient status codes (429 Rate Limit, 500, 502, 503, 504)
                    if response.status_code in (429, 500, 502, 503, 504):
                        # Switch to next fallback model if available
                        if "models/" in current_endpoint:
                            next_model = fallback_models[(attempt - 1) % len(fallback_models)]
                            current_endpoint = f"models/{next_model}:generateContent"
                        if attempt < self.max_retries:
                            await asyncio.sleep(0.5)
                            continue
                        response.raise_for_status()

                    response.raise_for_status()
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exception = exc
                if attempt < self.max_retries:
                    backoff = 1.0 * attempt
                    await asyncio.sleep(backoff)
                    continue
            except httpx.HTTPStatusError as exc:
                last_exception = exc
                status = exc.response.status_code
                if status in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    backoff = 12.0 * attempt if status == 429 else (0.5 * (2 ** (attempt - 1)))
                    await asyncio.sleep(backoff)
                    continue
                if status in (401, 403):
                    raise UnauthorizedException(
                        f"Gemini API authentication failed (HTTP {status})."
                    ) from exc
                if status in (400, 404, 422):
                    raise ValidationException(
                        f"Gemini API invalid request (HTTP {status})."
                    ) from exc
                raise ServiceUnavailableException(f"Gemini API HTTP error {status}") from exc

        msg = f"Gemini API request to '{endpoint}' failed: {last_exception}"
        raise ServiceUnavailableException(msg) from last_exception

    def _normalize_model_name(self, model: str) -> str:
        """Map generic or OpenAI model names to standard Gemini model paths."""
        if model.startswith("models/"):
            return model[7:]
        if model.startswith("gpt-"):
            return settings.GEMINI_MODEL
        return model

    def _format_gemini_contents(
        self,
        messages: list[dict[str, Any]] | None,
        fallback_prompt: str | None,
    ) -> list[dict[str, Any]]:
        """Format and coalesce multi-turn chat messages into valid Gemini REST API schema."""
        if not messages:
            text = fallback_prompt or ""
            return [{"role": "user", "parts": [{"text": text}]}]

        raw_turns: list[dict[str, Any]] = []
        for msg in messages:
            role = "user" if msg.get("role") in ("user", "system", "customer") else "model"
            text_val = str(msg.get("content", "")).strip()
            if not text_val:
                continue
            raw_turns.append({"role": role, "text": text_val})

        if not raw_turns:
            text = fallback_prompt or ""
            return [{"role": "user", "parts": [{"text": text}]}]

        # Coalesce consecutive messages with the same role to comply with Gemini API
        coalesced: list[dict[str, Any]] = []
        for turn in raw_turns:
            if coalesced and coalesced[-1]["role"] == turn["role"]:
                coalesced[-1]["parts"][0]["text"] += f"\n\n{turn['text']}"
            else:
                coalesced.append({"role": turn["role"], "parts": [{"text": turn["text"]}]})

        # Gemini requires that multi-turn starts with 'user'
        if coalesced and coalesced[0]["role"] != "user":
            coalesced.insert(0, {"role": "user", "parts": [{"text": "Hello"}]})

        return coalesced

    async def generate_text(
        self,
        request: LLMCompletionRequest,
    ) -> LLMCompletionResponse:
        """Generate text completion from Google Gemini API."""
        start_time = time.perf_counter()
        target_model = self._normalize_model_name(request.model)

        contents = self._format_gemini_contents(request.messages, request.prompt)

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
            },
        }

        if request.system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": request.system_prompt}]
            }

        if request.max_tokens is not None:
            payload["generationConfig"]["maxOutputTokens"] = request.max_tokens

        res_json = await self._post_with_retry(
            endpoint=f"models/{target_model}:generateContent",
            payload=payload,
            timeout_seconds=request.timeout_seconds,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        candidates = res_json.get("candidates", [])
        if not candidates:
            raise ServiceUnavailableException("Gemini API returned empty candidates list")

        candidate = candidates[0]
        content_parts = candidate.get("content", {}).get("parts", [])
        content_text = "".join(part.get("text", "") for part in content_parts)
        finish_reason = candidate.get("finishReason", "STOP").lower()

        usage_meta = res_json.get("usageMetadata", {})
        prompt_tokens = usage_meta.get("promptTokenCount", 0)
        completion_tokens = usage_meta.get("candidatesTokenCount", 0)
        total_tokens = usage_meta.get("totalTokenCount", prompt_tokens + completion_tokens)

        return LLMCompletionResponse(
            content=content_text,
            model=target_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            raw_response=res_json,
        )

    async def generate_structured_output(
        self,
        request: LLMCompletionRequest,
        schema: type[T],
    ) -> tuple[T, LLMCompletionResponse]:
        """Generate structured JSON output validated against Pydantic schema using Gemini response_mime_type."""
        start_time = time.perf_counter()
        target_model = self._normalize_model_name(request.model)

        system_instruction = request.system_prompt or "You are an accurate structured extraction assistant."
        json_prompt = (
            f"{system_instruction}\n\n"
            f"MUST return ONLY valid JSON matching this schema:\n"
            f"{json.dumps(schema.model_json_schema(), indent=2)}"
        )

        contents = self._format_gemini_contents(request.messages, request.prompt)

        payload: dict[str, Any] = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": json_prompt}]
            },
            "generationConfig": {
                "temperature": request.temperature,
                "responseMimeType": "application/json",
            },
        }

        if request.max_tokens is not None:
            payload["generationConfig"]["maxOutputTokens"] = request.max_tokens

        res_json = await self._post_with_retry(
            endpoint=f"models/{target_model}:generateContent",
            payload=payload,
            timeout_seconds=request.timeout_seconds,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        candidates = res_json.get("candidates", [])
        if not candidates:
            raise ServiceUnavailableException("Gemini API returned empty candidates list")

        candidate = candidates[0]
        content_parts = candidate.get("content", {}).get("parts", [])
        content_raw = "".join(part.get("text", "") for part in content_parts) or "{}"

        try:
            parsed_json = json.loads(content_raw)
            validated_obj = schema.model_validate(parsed_json)
        except (json.JSONDecodeError, ValidationError) as exc:
            msg = f"Failed to parse structured Gemini response into schema '{schema.__name__}': {exc}"
            raise ValidationException(msg) from exc

        usage_meta = res_json.get("usageMetadata", {})
        prompt_tokens = usage_meta.get("promptTokenCount", 0)
        completion_tokens = usage_meta.get("candidatesTokenCount", 0)
        total_tokens = usage_meta.get("totalTokenCount", prompt_tokens + completion_tokens)

        response_dto = LLMCompletionResponse(
            content=content_raw,
            model=target_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            finish_reason=candidate.get("finishReason", "STOP").lower(),
            raw_response=res_json,
        )
        return validated_obj, response_dto

    async def generate_embeddings(
        self,
        request: EmbeddingRequest,
    ) -> EmbeddingResponse:
        """Generate vector embeddings via Gemini text-embedding-004 batchEmbedContents API."""
        start_time = time.perf_counter()
        embed_model = "text-embedding-004"

        requests_payload = [
            {
                "model": f"models/{embed_model}",
                "content": {"parts": [{"text": text}]},
            }
            for text in request.texts
        ]

        payload = {"requests": requests_payload}

        res_json = await self._post_with_retry(
            endpoint=f"models/{embed_model}:batchEmbedContents",
            payload=payload,
            timeout_seconds=request.timeout_seconds,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        embeddings_raw = res_json.get("embeddings", [])
        embeddings = [item.get("values", []) for item in embeddings_raw]
        first_dim = len(embeddings[0]) if embeddings else (request.dimensions or 768)

        return EmbeddingResponse(
            embeddings=embeddings,
            model=embed_model,
            dimensions=first_dim,
            tenant_id=request.tenant_id,
            prompt_tokens=0,
            latency_ms=latency_ms,
        )
