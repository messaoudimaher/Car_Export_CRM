"""Document Entity Model for Private Object Storage metadata (WS-10, TASK-1003)."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.quotation import Quotation
    from app.models.tenant import Tenant


class Document(Base):
    """Declarative Document model representing private object storage document metadata."""

    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_tenant_id", "tenant_id"),
        Index("ix_documents_quotation_id", "quotation_id"),
        Index("ix_documents_tenant_type", "tenant_id", "document_type"),
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

    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Quotation_PDF",
        server_default="Quotation_PDF",
        comment="Categorized document classification (e.g. Quotation_PDF, Invoice_PDF)",
    )

    object_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
        comment="Private object storage path (e.g. tenants/<tenant_id>/quotes/<quote_id>/v1.pdf)",
    )

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="User-facing file name string (e.g. QT-2026-00001.pdf)",
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

    def __init__(self, **kw: object) -> None:
        """Initialize Document entity setting default attribute states."""
        kw.setdefault("document_type", "Quotation_PDF")
        kw.setdefault("mime_type", "application/pdf")
        kw.setdefault("version", 1)
        super().__init__(**kw)
