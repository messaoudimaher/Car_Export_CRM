"""Document Entity Model for Private Object Storage metadata (WS-10, WS-15, TASK-1501)."""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.lead import Lead
    from app.models.quotation import Quotation
    from app.models.tenant import Tenant
    from app.models.user import User


class Document(Base):
    """Declarative Document model representing private object storage document metadata."""

    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_tenant_id", "tenant_id"),
        Index("ix_documents_quotation_id", "quotation_id"),
        Index("ix_documents_lead_id", "lead_id"),
        Index("ix_documents_customer_id", "customer_id"),
        Index("ix_documents_uploader_id", "uploader_id"),
        Index("ix_documents_tenant_type", "tenant_id", "document_type"),
        Index("ix_documents_category", "category"),
        Index("ix_documents_status", "status"),
        Index("ix_documents_object_key", "object_key"),
        Index("ix_documents_created_at", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Foreign key referencing parent tenant organization",
    )

    quotation_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("quotations.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing parent quotation",
    )

    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing associated sales lead",
    )

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing customer owner",
    )

    uploader_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing user who uploaded the document",
    )

    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Quotation_PDF",
        server_default="Quotation_PDF",
        comment="Categorized document classification (e.g. Quotation_PDF, Invoice_PDF)",
    )

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="General",
        server_default="General",
        comment="Export document category (e.g. Carte_Grise, FCR_Certificate, Passport, General)",
    )

    object_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
        comment="Private object storage path (e.g. tenants/<tenant_id>/docs/<doc_id>/file.pdf)",
    )

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="User-facing file name string (e.g. carte_grise.pdf)",
    )

    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Payload binary size in bytes",
    )

    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="application/pdf",
        server_default="application/pdf",
        comment="MIME content type (e.g. application/pdf)",
    )

    sha256_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Server-side verified SHA-256 checksum hex string",
    )

    scan_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="Pending",
        server_default="Pending",
        comment="Malware and integrity scan status (Pending, Passed, Quarantined)",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="Pending",
        server_default="Pending",
        comment="Document lifecycle state (Pending, Available, Quarantined, Deleted)",
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment="Document version revision number",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="documents",
    )

    quotation: Mapped["Quotation | None"] = relationship(
        "Quotation",
        back_populates="documents",
    )

    lead: Mapped["Lead | None"] = relationship(
        "Lead",
        back_populates="documents",
    )

    customer: Mapped["Customer | None"] = relationship(
        "Customer",
        back_populates="documents",
    )

    uploader: Mapped["User | None"] = relationship(
        "User",
    )

    def __init__(self, **kw: Any) -> None:
        """Initialize Document entity setting default attribute states."""
        kw.setdefault("document_type", "Quotation_PDF")
        kw.setdefault("category", "General")
        kw.setdefault("mime_type", "application/pdf")
        kw.setdefault("scan_status", "Pending")
        kw.setdefault("status", "Pending")
        kw.setdefault("version", 1)
        super().__init__(**kw)
