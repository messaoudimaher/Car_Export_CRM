"""Base Declarative Model Class & Timestamp Mixin adhering to ADR 0005 (UUIDv7 primary keys)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils.uuid import generate_uuidv7


class TimestampMixin:
    """Mixin class adding created_at and updated_at UTC timestamp fields."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Record creation UTC timestamp",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Record last update UTC timestamp",
    )


class Base(DeclarativeBase, TimestampMixin):
    """Abstract base model declaring UUIDv7 primary keys and timestamps."""

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuidv7,
        comment="Time-ordered UUIDv7 primary key (ADR 0005)",
    )

    def __init__(self, **kw: object) -> None:
        """Initialize model ensuring UUIDv7 ID is set in memory per ADR 0005."""
        if "id" not in kw or kw["id"] is None:
            kw["id"] = generate_uuidv7()
        for k, v in kw.items():
            setattr(self, k, v)
