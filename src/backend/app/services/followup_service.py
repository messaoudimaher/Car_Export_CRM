"""FollowUp Service handling task scheduling and tenant isolation (WS-14, SEC-007)."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundException, ValidationException
from app.models.followup import FollowUp, FollowUpStatus
from app.models.lead import Lead
from app.schemas.followup import FollowUpCreate, FollowUpUpdate

logger = logging.getLogger(__name__)


class FollowUpService:
    """Tenant-scoped service managing sales follow-up task lifecycle (SEC-007)."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize FollowUpService with database session."""
        self.session = session

    async def create_followup(
        self,
        tenant_id: uuid.UUID,
        payload: FollowUpCreate,
    ) -> FollowUp:
        """Create a new scheduled follow-up task under tenant context (SEC-007)."""
        if not tenant_id:
            raise ValueError("tenant_id is strictly mandatory for creating follow-up (SEC-007)")

        # Verify lead exists under tenant context
        lead_stmt = select(Lead).where(
            Lead.id == payload.lead_id,
            Lead.tenant_id == tenant_id,
        )
        lead_result = await self.session.execute(lead_stmt)
        lead = lead_result.scalar_one_or_none()
        if not lead:
            raise NotFoundException(f"Lead '{payload.lead_id}' not found for tenant.")

        followup = FollowUp(
            tenant_id=tenant_id,
            lead_id=payload.lead_id,
            assigned_user_id=payload.assigned_user_id or lead.assigned_agent_id,
            title=payload.title,
            description=payload.description,
            due_at=payload.due_at,
            status=FollowUpStatus.PENDING.value,
            reminder_sent=False,
        )

        self.session.add(followup)
        await self.session.commit()
        await self.session.refresh(followup)

        logger.info(
            f"Created follow-up task '{followup.id}' for lead '{payload.lead_id}'",
            extra={"tenant_id": str(tenant_id), "followup_id": str(followup.id)},
        )

        return followup

    async def get_followup_by_id(
        self,
        tenant_id: uuid.UUID,
        followup_id: uuid.UUID,
    ) -> FollowUp:
        """Retrieve a specific follow-up task record under tenant context (SEC-007)."""
        if not tenant_id:
            raise ValueError("tenant_id is mandatory (SEC-007)")

        stmt = select(FollowUp).where(
            FollowUp.id == followup_id,
            FollowUp.tenant_id == tenant_id,  # SEC-007 Filter
        )
        result = await self.session.execute(stmt)
        followup = result.scalar_one_or_none()

        if not followup:
            raise NotFoundException(f"Follow-up task '{followup_id}' not found for tenant.")

        return followup

    async def list_followups(
        self,
        tenant_id: uuid.UUID,
        lead_id: uuid.UUID | None = None,
        assigned_user_id: uuid.UUID | None = None,
        status: str | None = None,
        due_before: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FollowUp]:
        """List follow-up tasks with optional filters under tenant scope (SEC-007)."""
        if not tenant_id:
            raise ValueError("tenant_id is mandatory (SEC-007)")

        stmt = (
            select(FollowUp)
            .where(FollowUp.tenant_id == tenant_id)  # SEC-007 Filter
            .order_by(FollowUp.due_at.asc(), FollowUp.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        if lead_id:
            stmt = stmt.where(FollowUp.lead_id == lead_id)
        if assigned_user_id:
            stmt = stmt.where(FollowUp.assigned_user_id == assigned_user_id)
        if status:
            stmt = stmt.where(FollowUp.status == status)
        if due_before:
            stmt = stmt.where(FollowUp.due_at <= due_before)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def complete_followup(
        self,
        tenant_id: uuid.UUID,
        followup_id: uuid.UUID,
        completion_time: datetime | None = None,
    ) -> FollowUp:
        """Mark a follow-up task as Completed (SEC-007)."""
        followup = await self.get_followup_by_id(tenant_id=tenant_id, followup_id=followup_id)
        try:
            followup.mark_completed(completion_time=completion_time or datetime.now(UTC))
        except ValueError as err:
            raise ValidationException(str(err)) from err

        await self.session.commit()
        await self.session.refresh(followup)

        logger.info(
            f"Completed follow-up task '{followup_id}'",
            extra={"tenant_id": str(tenant_id), "followup_id": str(followup_id)},
        )

        return followup

    async def cancel_followup(
        self,
        tenant_id: uuid.UUID,
        followup_id: uuid.UUID,
    ) -> FollowUp:
        """Mark a follow-up task as Cancelled (SEC-007)."""
        followup = await self.get_followup_by_id(tenant_id=tenant_id, followup_id=followup_id)
        try:
            followup.mark_cancelled()
        except ValueError as err:
            raise ValidationException(str(err)) from err

        await self.session.commit()
        await self.session.refresh(followup)

        return followup

    async def update_followup(
        self,
        tenant_id: uuid.UUID,
        followup_id: uuid.UUID,
        payload: FollowUpUpdate,
    ) -> FollowUp:
        """Update mutable fields of a follow-up task under tenant scope (SEC-007)."""
        followup = await self.get_followup_by_id(tenant_id=tenant_id, followup_id=followup_id)

        # Disallow updating core content of terminal follow-ups unless changing status
        if followup.status in (FollowUpStatus.COMPLETED.value, FollowUpStatus.CANCELLED.value):
            if (
                payload.title is not None
                or payload.description is not None
                or payload.due_at is not None
            ):
                raise ValidationException(
                    "Cannot edit task content when follow-up is already in terminal state "
                    f"'{followup.status}'."
                )

        if payload.title is not None:
            followup.title = payload.title
        if payload.description is not None:
            followup.description = payload.description
        if payload.due_at is not None:
            followup.due_at = payload.due_at
        if payload.assigned_user_id is not None:
            followup.assigned_user_id = payload.assigned_user_id
        if payload.status is not None:
            status_str = (
                payload.status.value
                if isinstance(payload.status, FollowUpStatus)
                else str(payload.status)
            )
            if status_str not in tuple(s.value for s in FollowUpStatus):
                raise ValidationException(f"Invalid follow-up status '{status_str}'.")
            try:
                if (
                    status_str == FollowUpStatus.COMPLETED.value
                    and followup.status != FollowUpStatus.COMPLETED.value
                ):
                    followup.mark_completed()
                elif status_str == FollowUpStatus.CANCELLED.value:
                    followup.mark_cancelled()
                else:
                    followup.status = status_str
            except ValueError as err:
                raise ValidationException(str(err)) from err

        await self.session.commit()
        await self.session.refresh(followup)

        return followup
