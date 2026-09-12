"""Document Pydantic response schemas & access payload contracts (WS-10, TASK-1003)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    """Pydantic schema representing document metadata details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Time-ordered UUIDv7 document identifier")
    tenant_id: UUID = Field(description="Parent tenant organization identifier")
    quotation_id: UUID | None = Field(
        default=None, description="Associated quotation identifier if applicable"
    )
    document_type: str = Field(description="Categorized document type (e.g. Quotation_PDF)")
    object_key: str = Field(description="Private object storage path key")
    file_name: str = Field(description="User-facing filename string")
    file_size_bytes: int = Field(description="Payload binary size in bytes")
    mime_type: str = Field(description="MIME content type")
    version: int = Field(description="Document version number")
    created_at: datetime = Field(description="Creation UTC timestamp")
    updated_at: datetime = Field(description="Last update UTC timestamp")


class DocumentAccessResponse(BaseModel):
    """Pydantic schema for authorized document access response containing presigned URL."""

    document: DocumentResponse = Field(description="Document metadata")
    access_url: str = Field(description="Short-lived authorized access URL")
    expires_in_seconds: int = Field(description="Access URL expiration lifetime in seconds")


class DocumentEnvelope(BaseModel):
    """Single Document envelope."""

    data: DocumentResponse


class DocumentAccessEnvelope(BaseModel):
    """Document access envelope."""

    data: DocumentAccessResponse
