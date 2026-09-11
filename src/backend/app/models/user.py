"""User Entity Model & RBAC UserRole enum adhering to ADR 0005 & SECURITY.md."""

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.conversation import WhatsAppConversation
    from app.models.lead import Lead
    from app.models.tenant import Tenant


class UserRole(StrEnum):
    """Role-Based Access Control (RBAC) user roles catalog."""

    SUPER_ADMIN = "SuperAdmin"
    TENANT_ADMIN = "TenantAdmin"
    SALES_AGENT = "SalesAgent"
    LOGISTICS_AGENT = "LogisticsAgent"


class User(Base):
    """Declarative User model representing an authenticated user account."""

    __tablename__ = "users"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key referencing parent tenant organization",
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Unique user email address used as login identity",
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Argon2id hashed user password string",
    )

    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="User full display name",
    )

    role: Mapped[UserRole] = mapped_column(
        String(50),
        nullable=False,
        default=UserRole.SALES_AGENT,
        comment="RBAC role string (SuperAdmin, TenantAdmin, SalesAgent, LogisticsAgent)",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Active account status flag",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="users",
    )

    assigned_conversations: Mapped[list["WhatsAppConversation"]] = relationship(
        "WhatsAppConversation",
        back_populates="assigned_agent",
    )

    assigned_leads: Mapped[list["Lead"]] = relationship(
        "Lead",
        back_populates="assigned_agent",
    )

    def __init__(self, **kw: object) -> None:
        """Initialize User entity setting default in-memory attribute states."""
        kw.setdefault("is_active", True)
        kw.setdefault("role", UserRole.SALES_AGENT)
        super().__init__(**kw)
