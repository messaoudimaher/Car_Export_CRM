"""LLM Provider Abstract Port Interface & DTO Contracts (AGENTS.md Rule 1, ADR 0002, ADR 0003)."""

from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


class LLMCompletionRequest(BaseModel):
    """Input parameters for an LLM text generation or structured extraction request."""

    prompt: str = Field(default="", description="User prompt or main text input")
    system_prompt: str | None = Field(
        default=None, description="Optional system instruction prompt"
    )
    messages: list[dict[str, str]] | None = Field(
        default=None,
        description="Optional chat message history array [{'role': 'user', 'content': '...'}]",
    )
    model: str = Field(default="gpt-4o-mini", description="Target LLM model identifier")
    temperature: float = Field(
        default=0.0, ge=0.0, le=2.0, description="Sampling temperature (0.0 for deterministic)"
    )
    max_tokens: int | None = Field(default=1000, ge=1, description="Maximum tokens to generate")
    timeout_seconds: float = Field(
        default=30.0, ge=1.0, description="HTTP request timeout in seconds"
    )


class LLMCompletionResponse(BaseModel):
    """Normalized output response DTO for LLM completion requests."""

    content: str = Field(..., description="Generated text content or raw JSON response string")
    model: str = Field(..., description="Actual model string returned by provider")
    prompt_tokens: int = Field(default=0, ge=0, description="Number of tokens in prompt input")
    completion_tokens: int = Field(
        default=0, ge=0, description="Number of tokens generated in completion"
    )
    total_tokens: int = Field(default=0, ge=0, description="Total tokens consumed")
    latency_ms: float = Field(
        default=0.0, ge=0.0, description="Total roundtrip request latency in milliseconds"
    )
    finish_reason: str = Field(
        default="stop", description="Completion termination reason (stop, length, etc.)"
    )
    raw_response: dict[str, Any] = Field(
        default_factory=dict, description="Raw provider JSON payload"
    )


class LLMProvider(ABC):
    """Abstract port interface for Large Language Model (LLM) providers."""

    @abstractmethod
    async def generate_text(
        self,
        request: LLMCompletionRequest,
    ) -> LLMCompletionResponse:
        """Generate unstructured text completion from LLM provider.

        Args:
            request: Standardized completion request DTO.

        Returns:
            LLMCompletionResponse: Normalized completion response containing text and usage metrics.
        """

    @abstractmethod
    async def generate_structured_output(
        self,
        request: LLMCompletionRequest,
        schema: type[T],
    ) -> tuple[T, LLMCompletionResponse]:
        """Generate structured JSON output validated against a Pydantic schema class.

        Args:
            request: Standardized completion request DTO.
            schema: Target Pydantic model class to validate and parse response against.

        Returns:
            tuple[T, LLMCompletionResponse]: Parsed schema instance and response metadata.
        """
