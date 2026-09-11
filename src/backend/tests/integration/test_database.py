"""Database Foundation Integration & Base Model Tests."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import settings
from app.core.database import async_engine, check_database_health, get_db_session
from app.models.base import Base


def test_base_model_instantiation() -> None:
    """Verify Base declarative model instantiates with UUIDv7 primary key default."""

    class DummyModel(Base):
        __tablename__ = "dummy_test_table"

    instance = DummyModel()
    assert instance.id is not None
    assert isinstance(instance.id, uuid.UUID)
    assert instance.id.version == 7


def test_async_engine_pool_configuration() -> None:
    """Verify async engine pool parameters align with ADR 0005 settings."""
    pool = async_engine.pool
    assert getattr(pool, "size", lambda: 0)() == settings.DATABASE_POOL_SIZE
    assert getattr(pool, "_max_overflow", None) == settings.DATABASE_MAX_OVERFLOW
    assert getattr(pool, "_recycle", None) == 1800
    assert getattr(pool, "_pre_ping", None) is True


@pytest.mark.asyncio
async def test_get_db_session_success_lifecycle() -> None:
    """Verify get_db_session yields an AsyncSession and commits on exit."""
    session_gen = get_db_session()
    session = await anext(session_gen)
    assert isinstance(session, AsyncSession)

    # Mock session commit to verify it gets called when generator completes cleanly
    session.commit = AsyncMock()  # type: ignore[method-assign]

    with pytest.raises(StopAsyncIteration):
        await anext(session_gen)

    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_session_rollback_on_exception() -> None:
    """Verify get_db_session rolls back when an exception occurs inside consumer code."""
    session_gen = get_db_session()
    session = await anext(session_gen)
    assert isinstance(session, AsyncSession)

    session.rollback = AsyncMock()  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="Database operation failure"):
        await session_gen.athrow(RuntimeError("Database operation failure"))

    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_database_health_check_execution() -> None:
    """Verify check_database_health() runs without crashing.

    Note: Returns boolean depending on whether local PostgreSQL service is running.
    """
    result = await check_database_health()
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_database_health_check_exception_handling() -> None:
    """Verify check_database_health() returns False on database connection error."""
    with patch.object(
        AsyncEngine,
        "connect",
        side_effect=Exception("DB Connection Refused"),
    ):
        result = await check_database_health()
        assert result is False
