"""Document Pydantic DTO schemas & access payload contracts (WS-10, TASK-1003, WS-15, TASK-1501)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentUploadInitRequest(BaseModel):
    """Input payload schema for initializing document upload."""

    file_name: str = Field(
        ..., min_length=1, max_length=255, description="File name (e.g. carte_grise.pdf)"
    )
    mime_type: str = Field(..., min_length=3, max_length=100, description="MIME content type")
    file_size_bytes: int = Field(
        ..., gt=0, le=10_485_760, description="File size in bytes (max 10MB)"
    )
    category: str = Field(
        default="General",
        description="Document category: Carte_Grise, FCR_Certificate, Passport, General",
    )
    lead_id: UUID | None = Field(default=None, description="Optional associated sales lead UUID")
    customer_id: UUID | None = Field(default=None, description="Optional customer UUID")


class DocumentUploadInitResponse(BaseModel):
    """Response schema containing upload URL and pre-signed authorization info."""

    document_id: UUID = Field(..., description="Generated Document UUIDv7 record identifier")
    object_key: str = Field(..., description="Server-side generated tenant-scoped object key")
    upload_url: str = Field(..., description="Pre-signed upload URL or direct target URL")
    upload_fields: dict[str, str] = Field(
        default_factory=dict, description="Additional POST upload fields if applicable"
    )
    expires_in_seconds: int = Field(
        default=900, description="Pre-signed upload authorization lifetime (seconds)"
    )


class DocumentUploadCompleteRequest(BaseModel):
    """Input payload schema for completing upload verification."""

    sha256_hash: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        description="Optional client-provided SHA-256 hex checksum to verify against server-side",
    )


class DocumentResponse(BaseModel):
    """Pydantic schema representing full document metadata details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Time-ordered UUIDv7 document identifier")
    tenant_id: UUID = Field(description="Parent tenant organization identifier")
    quotation_id: UUID | None = Field(
        default=None, description="Associated quotation identifier if applicable"
    )
    lead_id: UUID | None = Field(
        default=None, description="Associated sales lead identifier if applicable"
    )
    customer_id: UUID | None = Field(
        default=None, description="Associated customer identifier if applicable"
    )
    uploader_id: UUID | None = Field(default=None, description="User who uploaded the document")
    document_type: str = Field(
        description="Categorized document type (e.g. Quotation_PDF, Customer_Export_Doc)"
    )
    category: str = Field(
        description="Document category (Carte_Grise, FCR_Certificate, Passport, General)"
    )
    object_key: str = Field(description="Private object storage path key")
    file_name: str = Field(description="User-facing filename string")
    file_size_bytes: int = Field(description="Payload binary size in bytes")
    mime_type: str = Field(description="MIME content type")
    sha256_hash: str | None = Field(
        default=None, description="Server-side verified SHA-256 checksum hex string"
    )
    scan_status: str = Field(description="Scan status (Pending, Passed, Quarantined)")
    status: str = Field(description="Lifecycle status (Pending, Available, Quarantined, Deleted)")
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
