"""AuditEvent Model for Immutable Security Audit Logging (BR-016, INV-009, SECURITY.md Section 15)."""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.user import User


class AuditEvent(Base):
    """Declarative AuditEvent model representing append-only security and business action logs."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_tenant_id", "tenant_id"),
        Index("ix_audit_events_user_id", "user_id"),
        Index("ix_audit_events_action", "action"),
        Index("ix_audit_events_tenant_action", "tenant_id", "action"),
        Index("ix_audit_events_resource", "resource_type", "resource_id"),
        Index("ix_audit_events_created_at", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing parent tenant organization (nullable for system events)",
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing acting user identity (nullable for system/webhook events)",
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Categorized action string (e.g. USER_LOGIN_SUCCESS, QUOTE_APPROVED, DOCUMENT_DOWNLOADED)",
    )

    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="System",
        server_default="System",
        comment="Target resource category (e.g. Customer, Quotation, Document, User, Security)",
    )

    resource_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Target resource primary key or reference ID string",
    )

    payload_before: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Sanitized JSON state payload before action execution",
    )

    payload_after: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Sanitized JSON state payload after action execution",
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="Client IP address (IPv4/IPv6)",
    )

    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Client HTTP User-Agent header string",
    )

    correlation_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Associated HTTP request correlation ID for trace linking",
    )

    # Relationships
    tenant: Mapped["Tenant | None"] = relationship("Tenant")
    user: Mapped["User | None"] = relationship("User")

    def __init__(self, **kw: Any) -> None:
        """Initialize AuditEvent entity setting default attribute states."""
        kw.setdefault("resource_type", "System")
        super().__init__(**kw)


from sqlalchemy import event

from app.core.errors import DeveloperSecurityException


@event.listens_for(AuditEvent, "before_update")
def block_audit_event_update(mapper: Any, connection: Any, target: AuditEvent) -> None:
    """Block ORM UPDATE operations on AuditEvent instances (BR-016, INV-009)."""
    raise DeveloperSecurityException(
        "SECURITY_AUDIT_IMMUTABILITY_VIOLATION: AuditEvent records are append-only. UPDATE operations are strictly prohibited (BR-016, INV-009)."
    )


@event.listens_for(AuditEvent, "before_delete")
def block_audit_event_delete(mapper: Any, connection: Any, target: AuditEvent) -> None:
    """Block ORM DELETE operations on AuditEvent instances (BR-016, INV-009)."""
    raise DeveloperSecurityException(
        "SECURITY_AUDIT_IMMUTABILITY_VIOLATION: AuditEvent records are append-only. DELETE operations are strictly prohibited (BR-016, INV-009)."
    )
