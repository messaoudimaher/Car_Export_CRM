"""Unit & Integration tests for BaseRepository & Optimistic Concurrency Control (ADR 0010)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.errors import ConcurrencyException, NotFoundException
from app.models.base import Base
from app.repositories.base import BaseRepository


class DummyVersionedModel(Base):
    """Declarative test model with optimistic concurrency version column."""

    __tablename__ = "dummy_versioned_test_table"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)


@pytest.mark.asyncio
async def test_base_repository_create() -> None:
    """Verify BaseRepository create adds entity to session and flushes."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    repo = BaseRepository(mock_session, DummyVersionedModel)

    item = DummyVersionedModel(name="New Item", version=1)
    created = await repo.create(item)

    mock_session.add.assert_called_once_with(item)
    mock_session.flush.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(item)
    assert created.name == "New Item"


@pytest.mark.asyncio
async def test_base_repository_get_by_id() -> None:
    """Verify BaseRepository get_by_id calls session.get."""
    mock_session = AsyncMock()
    expected_item = DummyVersionedModel(name="Existing Item", version=1)
    mock_session.get.return_value = expected_item

    repo = BaseRepository(mock_session, DummyVersionedModel)
    result = await repo.get_by_id(expected_item.id)

    mock_session.get.assert_awaited_once_with(DummyVersionedModel, expected_item.id)
    assert result is expected_item


@pytest.mark.asyncio
async def test_base_repository_list() -> None:
    """Verify BaseRepository list executes paginated select query."""
    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [
        DummyVersionedModel(name="Item 1"),
        DummyVersionedModel(name="Item 2"),
    ]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    repo = BaseRepository(mock_session, DummyVersionedModel)
    items = await repo.list(offset=0, limit=10)

    mock_session.execute.assert_awaited_once()
    assert len(items) == 2


@pytest.mark.asyncio
async def test_base_repository_update_success_with_concurrency_check() -> None:
    """Verify BaseRepository update increments version when expected_version matches."""
    mock_session = AsyncMock()
    existing_db_item = DummyVersionedModel(name="Original", version=1)
    mock_session.get.return_value = existing_db_item
    mock_session.merge.side_effect = lambda entity: entity

    repo = BaseRepository(mock_session, DummyVersionedModel)

    updating_item = DummyVersionedModel(id=existing_db_item.id, name="Updated", version=1)
    updated = await repo.update(updating_item, expected_version=1)

    assert updated.name == "Updated"
    assert updated.version == 2
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_base_repository_update_concurrency_conflict() -> None:
    """Verify BaseRepository update raises ConcurrencyException when expected_version mismatches."""
    mock_session = AsyncMock()
    existing_db_item = DummyVersionedModel(name="Modified By Other", version=2)
    mock_session.get.return_value = existing_db_item

    repo = BaseRepository(mock_session, DummyVersionedModel)

    stale_item = DummyVersionedModel(id=existing_db_item.id, name="Stale Update", version=1)

    with pytest.raises(ConcurrencyException) as exc_info:
        await repo.update(stale_item, expected_version=1)

    assert "Resource update conflict" in str(exc_info.value)
    assert exc_info.value.status_code == 412


@pytest.mark.asyncio
async def test_base_repository_update_not_found() -> None:
    """Verify BaseRepository update raises NotFoundException when updating non-existent ID."""
    mock_session = AsyncMock()
    mock_session.get.return_value = None

    repo = BaseRepository(mock_session, DummyVersionedModel)
    ghost_item = DummyVersionedModel(name="Ghost", version=1)

    with pytest.raises(NotFoundException):
        await repo.update(ghost_item, expected_version=1)


@pytest.mark.asyncio
async def test_base_repository_delete() -> None:
    """Verify BaseRepository delete removes existing record."""
    mock_session = AsyncMock()
    item_to_delete = DummyVersionedModel(name="To Delete", version=1)
    mock_session.get.return_value = item_to_delete

    repo = BaseRepository(mock_session, DummyVersionedModel)
    result = await repo.delete(item_to_delete.id)

    assert result is True
    mock_session.delete.assert_awaited_once_with(item_to_delete)
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_base_repository_delete_not_found() -> None:
    """Verify BaseRepository delete returns False when item is not found."""
    mock_session = AsyncMock()
    mock_session.get.return_value = None

    repo = BaseRepository(mock_session, DummyVersionedModel)
    result = await repo.delete("non-existent-id")

    assert result is False
    mock_session.delete.assert_not_called()
