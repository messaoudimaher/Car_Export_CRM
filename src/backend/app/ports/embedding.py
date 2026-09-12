"""Embedding Provider Abstract Port Interface & DTO Contracts (ADR 0002, ADR 0011)."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class EmbeddingRequest(BaseModel):
    """Input parameters for vector embedding generation requests."""

    texts: list[str] = Field(
        ..., min_length=1, description="List of string chunks to generate embeddings for"
    )
    model: str = Field(
        default="text-embedding-3-small", description="Target vector embedding model identifier"
    )
    timeout_seconds: float = Field(
        default=30.0, ge=1.0, description="HTTP request timeout in seconds"
    )


class EmbeddingResponse(BaseModel):
    """Normalized output response DTO for vector embedding generation requests."""

    embeddings: list[list[float]] = Field(
        ..., description="List of 1536-dimensional floating point vector arrays"
    )
    model: str = Field(..., description="Actual model string returned by provider")
    prompt_tokens: int = Field(0, ge=0, description="Total input tokens consumed")
    latency_ms: float = Field(
        0.0, ge=0.0, description="Total roundtrip request latency in milliseconds"
    )


class EmbeddingProvider(ABC):
    """Abstract port interface for Text Embedding providers."""

    @abstractmethod
    async def generate_embeddings(
        self,
        request: EmbeddingRequest,
    ) -> EmbeddingResponse:
        """Generate high-dimensional vector embeddings for input text chunks.

        Args:
            request: Standardized embedding request DTO.

        Returns:
            EmbeddingResponse: Response containing vector arrays and token usage.
        """
