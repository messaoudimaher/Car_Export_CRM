"""Tenant-Scoped Repository Base Class enforcing multi-tenancy (SEC-003, BR-002, ADR 0006)."""

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConcurrencyException, DeveloperSecurityException, NotFoundException
from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class TenantRepository(Generic[ModelT]):
    """Generic tenant-isolated repository enforcing mandatory tenant_id query boundaries."""

    def __init__(
        self, session: AsyncSession, model_cls: type[ModelT], tenant_id: UUID | None
    ) -> None:
        if tenant_id is None:
            raise DeveloperSecurityException(
                "TenantRepository initialization failed: Missing tenant_id context."
            )
        self.session = session
        self.model_cls = model_cls
        self.tenant_id = tenant_id if isinstance(tenant_id, UUID) else UUID(str(tenant_id))

    async def get_by_id(self, id_: Any) -> ModelT | None:
        """Fetch a single record by primary key ID strictly scoped to current tenant context."""
        stmt = (
            select(self.model_cls)
            .where(getattr(self.model_cls, "id") == id_)  # noqa: B009
            .where(getattr(self.model_cls, "tenant_id") == self.tenant_id)  # noqa: B009
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(self, offset: int = 0, limit: int = 100) -> list[ModelT]:
        """Fetch a paginated list of records strictly scoped to current tenant context."""
        stmt = (
            select(self.model_cls)
            .where(getattr(self.model_cls, "tenant_id") == self.tenant_id)  # noqa: B009
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, entity: ModelT) -> ModelT:
        """Persist a new entity record ensuring tenant_id is attached to entity."""
        entity_tenant_id = getattr(entity, "tenant_id", None)
        if entity_tenant_id is None:
            setattr(entity, "tenant_id", self.tenant_id)  # noqa: B010
        elif str(entity_tenant_id) != str(self.tenant_id):
            raise DeveloperSecurityException(
                f"Entity tenant_id '{entity_tenant_id}' conflicts with repo '{self.tenant_id}'."
            )

        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update(self, entity: ModelT, expected_version: int | None = None) -> ModelT:
        """Update an existing record enforcing tenant scoping and optimistic concurrency control."""
        entity_id = getattr(entity, "id", None)
        entity_tenant_id = getattr(entity, "tenant_id", None)

        if entity_tenant_id is not None and str(entity_tenant_id) != str(self.tenant_id):
            raise DeveloperSecurityException(
                "Cross-tenant update prohibited: Entity tenant_id mismatches repo tenant context."
            )

        current_version = getattr(entity, "version", None)
        version_to_check = expected_version if expected_version is not None else current_version

        if entity_id is None:
            raise NotFoundException(f"Record of type {self.model_cls.__name__} has no primary key.")

        db_entity = await self.get_by_id(entity_id)
        if db_entity is None:
            raise NotFoundException(
                f"Record of type {self.model_cls.__name__} not found in tenant scope."
            )

        if version_to_check is not None:
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
        """Delete a record by primary key ID strictly scoped to current tenant context."""
        entity = await self.get_by_id(id_)
        if entity is None:
            return False
        await self.session.delete(entity)
        await self.session.flush()
        return True
