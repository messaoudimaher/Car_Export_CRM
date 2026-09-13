"""Pydantic DTO Schemas for Knowledge Embeddings and RAG document ingestion (WS-13, ADR 0011)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeChunkCreate(BaseModel):
    """Input payload schema for persisting a single tenant knowledge chunk and vector embedding."""

    tenant_id: uuid.UUID = Field(..., description="Tenant organization UUID")
    document_id: uuid.UUID | None = Field(default=None, description="Optional parent document UUID")
    document_name: str = Field(..., description="User-facing document name or title")
    chunk_index: int = Field(
        default=0, ge=0, description="Zero-based sequential chunk position index"
    )
    chunk_content: str = Field(..., description="Extracted text chunk body")
    embedding: list[float] | None = Field(
        default=None, description="1536-dimensional float vector embedding array"
    )
    metadata_jsonb: dict[str, Any] = Field(
        default_factory=dict, description="Extensible chunk metadata JSON"
    )


class KnowledgeChunkRead(BaseModel):
    """Response schema for returning a knowledge chunk record."""

    id: uuid.UUID = Field(..., description="Unique UUIDv7 identifier")
    tenant_id: uuid.UUID = Field(..., description="Tenant organization UUID")
    document_id: uuid.UUID | None = Field(default=None, description="Optional parent document UUID")
    document_name: str = Field(..., description="Source document name")
    chunk_index: int = Field(..., description="Zero-based chunk position index")
    chunk_content: str = Field(..., description="Text chunk content body")
    metadata_jsonb: dict[str, Any] = Field(..., description="Chunk metadata JSON")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record update timestamp")

    model_config = ConfigDict(from_attributes=True)


class KnowledgeDocumentIngestRequest(BaseModel):
    """Request payload schema for chunking and ingesting a tenant knowledge document."""

    document_name: str = Field(..., description="User-facing document title or file name")
    document_text: str = Field(..., description="Full text payload of knowledge document")
    document_id: uuid.UUID | None = Field(default=None, description="Optional document UUID")
    chunk_size: int = Field(
        default=600, ge=100, le=4000, description="Target character length per chunk"
    )
    chunk_overlap: int = Field(
        default=100, ge=0, le=1000, description="Overlapping character count between chunks"
    )


class KnowledgeDocumentIngestResult(BaseModel):
    """Response summary schema returned after ingesting a knowledge document."""

    document_name: str = Field(..., description="Source document title")
    total_chunks: int = Field(..., description="Total number of chunks produced")
    chunk_ids: list[uuid.UUID] = Field(..., description="UUIDs of generated chunk records")


class KnowledgeSearchResult(BaseModel):
    """Result item DTO returned from vector similarity search in RAG engine."""

    id: uuid.UUID = Field(..., description="Knowledge chunk record UUID")
    tenant_id: uuid.UUID = Field(..., description="Tenant organization UUID")
    document_id: uuid.UUID | None = Field(default=None, description="Source document UUID")
    document_name: str = Field(..., description="Source document name")
    chunk_index: int = Field(..., description="Sequential chunk index")
    chunk_content: str = Field(..., description="Retrieved chunk text body")
    similarity_score: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")
    metadata_jsonb: dict[str, Any] = Field(
        default_factory=dict, description="Extensible chunk metadata JSON"
    )

    model_config = ConfigDict(from_attributes=True)


class KnowledgeSearchRequest(BaseModel):
    """Query payload schema for RAG vector search."""

    query_text: str = Field(..., min_length=1, description="Natural language search query text")
    top_k: int = Field(default=5, ge=1, le=50, description="Maximum number of chunks to return")
    min_similarity: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Minimum cosine similarity threshold filter"
    )
