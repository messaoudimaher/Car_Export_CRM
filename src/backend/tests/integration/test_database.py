"""Database Foundation Integration & Base Model Tests."""

import uuid

import pytest

from app.core.database import check_database_health
from app.models.base import Base


def test_base_model_instantiation() -> None:
    """Verify Base declarative model instantiates with UUIDv7 primary key default."""

    class DummyModel(Base):
        __tablename__ = "dummy_test_table"

    instance = DummyModel()
    assert instance.id is not None
    assert isinstance(instance.id, uuid.UUID)
    assert instance.id.version == 7


@pytest.mark.asyncio
async def test_database_health_check_execution() -> None:
    """Verify check_database_health() runs without crashing.

    Note: Returns boolean depending on whether local PostgreSQL service is running.
    """
    result = await check_database_health()
    assert isinstance(result, bool)
