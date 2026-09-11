"""Generic Async Base Repository providing CRUD & Optimistic Concurrency Control (ADR 0010)."""

from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConcurrencyException, NotFoundException
from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic async database repository for SQLAlchemy declarative models."""

    def __init__(self, session: AsyncSession, model_cls: type[ModelT]) -> None:
        self.session = session
        self.model_cls = model_cls

    async def get_by_id(self, id_: Any) -> ModelT | None:
        """Fetch a single record by its primary key ID."""
        return await self.session.get(self.model_cls, id_)

    async def list(self, offset: int = 0, limit: int = 100) -> list[ModelT]:
        """Fetch a paginated list of records."""
        stmt = select(self.model_cls).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, entity: ModelT) -> ModelT:
        """Persist a new entity record to the database session."""
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update(self, entity: ModelT, expected_version: int | None = None) -> ModelT:
        """Update an existing entity record with optional optimistic concurrency version validation.

        Args:
            entity: The model instance containing updated fields.
            expected_version: Expected record version prior to modification (ADR 0010).

        Raises:
            ConcurrencyException: If expected_version mismatches current database record version.
            NotFoundException: If entity record is not found in database.

        Returns:
            ModelT: Updated entity instance.
        """
        entity_id = getattr(entity, "id", None)
        current_version = getattr(entity, "version", None)
        version_to_check = expected_version if expected_version is not None else current_version

        if version_to_check is not None and entity_id is not None:
            db_entity = await self.get_by_id(entity_id)
            if db_entity is None:
                raise NotFoundException(f"Record of type {self.model_cls.__name__} not found.")

            db_version = getattr(db_entity, "version", None)
            if db_version is not None and db_version != version_to_check:
                raise ConcurrencyException(
                    f"Resource update conflict: Expected version {version_to_check}, "
                    f"but current database version is {db_version}."
                )

            if current_version is not None:
                setattr(entity, "version", current_version + 1)  # noqa: B010

        merged = await self.session.merge(entity)
        await self.session.flush()
        await self.session.refresh(merged)
        return merged

    async def delete(self, id_: Any) -> bool:
        """Delete a record by primary key ID.

        Returns:
            bool: True if entity was found and deleted, False otherwise.
        """
        entity = await self.get_by_id(id_)
        if entity is None:
            return False
        await self.session.delete(entity)
        await self.session.flush()
        return True
