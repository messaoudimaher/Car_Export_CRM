"""Lead Service & Pipeline State Machine manager (WS-08, BR-011, BR-012)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundException, ValidationException
from app.core.logging import logger
from app.models.lead import (
    VALID_STAGE_TRANSITIONS,
    Lead,
    LeadPriority,
    LeadStatus,
    LostReason,
)


class LeadService:
    """Domain service managing Lead lifecycle state machine and 90-day auto-reopen logic."""

    @staticmethod
    def validate_stage_transition(
        current_status: str | LeadStatus,
        target_status: str | LeadStatus,
    ) -> None:
        """Validate whether a lead stage transition is permitted by BR-011 state machine rules.

        Args:
            current_status: Current lead status string or LeadStatus enum.
            target_status: Target lead status string or LeadStatus enum.

        Raises:
            ValidationException: If the state transition is invalid or unpermitted.
        """
        curr_enum = (
            current_status if isinstance(current_status, LeadStatus) else LeadStatus(current_status)
        )
        target_enum = (
            target_status if isinstance(target_status, LeadStatus) else LeadStatus(target_status)
        )

        if curr_enum == target_enum:
            return  # No-op status change is valid

        allowed_targets = VALID_STAGE_TRANSITIONS.get(curr_enum, set())
        if target_enum not in allowed_targets:
            msg = f"Invalid lead transition from '{curr_enum.value}' to '{target_enum.value}'."
            raise ValidationException(
                message=msg,
                invalid_params=[
                    {
                        "name": "status",
                        "reason": (
                            f"Transition from '{curr_enum.value}' to '{target_enum.value}' "
                            f"violates pipeline state machine (BR-011). Allowed target stages: "
                            f"{[s.value for s in allowed_targets]}"
                        ),
                    }
                ],
            )

    async def create_lead(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        assigned_agent_id: uuid.UUID | None = None,
        priority: str | LeadPriority = LeadPriority.MEDIUM,
        vehicle_request_id: uuid.UUID | None = None,
    ) -> Lead:
        """Create a new sales Lead opportunity in New stage.

        Args:
            db: AsyncSession database session.
            tenant_id: Tenant organization UUID.
            customer_id: Buyer customer profile UUID.
            assigned_agent_id: Optional assigned sales rep user UUID.
            priority: Lead priority (Low, Medium, High, Urgent).
            vehicle_request_id: Optional linked vehicle request UUID.

        Returns:
            Lead: Created Lead entity instance.
        """
        prio_val = priority.value if isinstance(priority, LeadPriority) else priority
        lead = Lead(
            tenant_id=tenant_id,
            customer_id=customer_id,
            assigned_agent_id=assigned_agent_id,
            vehicle_request_id=vehicle_request_id,
            status=LeadStatus.NEW.value,
            priority=prio_val,
        )
        db.add(lead)
        await db.commit()
        await db.refresh(lead)

        logger.info(
            "lead_created",
            extra={
                "lead_id": str(lead.id),
                "tenant_id": str(tenant_id),
                "customer_id": str(customer_id),
                "status": lead.status,
            },
        )
        return lead

    async def get_lead_by_id(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        lead_id: uuid.UUID,
    ) -> Lead | None:
        """Retrieve a Lead by ID under tenant isolation context (ADR 0005).

        Args:
            db: AsyncSession database session.
            tenant_id: Tenant organization UUID.
            lead_id: Lead entity UUID.

        Returns:
            Lead | None: Lead model instance if found, None otherwise.
        """
        stmt = select(Lead).where(
            Lead.id == lead_id,
            Lead.tenant_id == tenant_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def transition_lead_stage(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        lead_id: uuid.UUID,
        target_status: str | LeadStatus,
        lost_reason: str | LostReason | None = None,
        vehicle_request_id: uuid.UUID | None = None,
        assigned_agent_id: uuid.UUID | None = None,
    ) -> Lead:
        """Transition a Lead to a new pipeline stage (BR-011).

        Args:
            db: AsyncSession database session.
            tenant_id: Tenant organization UUID.
            lead_id: Lead entity UUID.
            target_status: Target pipeline status stage.
            lost_reason: Optional reason string/enum if target status is Lost.
            vehicle_request_id: Optional vehicle request UUID to link.
            assigned_agent_id: Optional assigned sales rep user UUID.

        Returns:
            Lead: Updated Lead entity instance.

        Raises:
            NotFoundException: If lead with lead_id does not exist under tenant_id.
            ValidationException: If requested stage transition is invalid under BR-011 rules.
        """
        lead = await self.get_lead_by_id(db, tenant_id=tenant_id, lead_id=lead_id)
        if lead is None:
            raise NotFoundException(f"Lead with ID '{lead_id}' not found.")

        target_enum = (
            target_status if isinstance(target_status, LeadStatus) else LeadStatus(target_status)
        )
        curr_enum = LeadStatus(lead.status)

        # Validate stage transition against BR-011 state machine rules
        self.validate_stage_transition(curr_enum, target_enum)

        # Mutate Lead attributes according to stage rules
        lead.status = target_enum.value

        if target_enum == LeadStatus.LOST:
            lead.closed_at = datetime.now(UTC)
            if lost_reason is not None:
                reason_val = (
                    lost_reason.value if isinstance(lost_reason, LostReason) else str(lost_reason)
                )
                lead.lost_reason = reason_val
        elif target_enum == LeadStatus.WON:
            lead.closed_at = datetime.now(UTC)
            lead.lost_reason = None
        elif target_enum == LeadStatus.NEW:
            # Reopened lead resets closure metrics
            lead.closed_at = None
            lead.lost_reason = None

        if vehicle_request_id is not None:
            lead.vehicle_request_id = vehicle_request_id

        if assigned_agent_id is not None:
            lead.assigned_agent_id = assigned_agent_id

        await db.commit()
        await db.refresh(lead)

        logger.info(
            "lead_stage_transitioned",
            extra={
                "lead_id": str(lead.id),
                "tenant_id": str(tenant_id),
                "previous_status": curr_enum.value,
                "new_status": lead.status,
                "closed_at": str(lead.closed_at) if lead.closed_at else None,
            },
        )
        return lead

    async def check_and_reopen_lost_lead(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        reference_time: datetime | None = None,
    ) -> Lead | None:
        """Check if customer has a Lost lead eligible for 90-day auto-reopening (BR-012).

        If customer sends an inbound message within 90 days of lead closure, the lead
        is automatically reopened from Lost to New stage.

        Args:
            db: AsyncSession database session.
            tenant_id: Tenant organization UUID.
            customer_id: Customer buyer UUID.
            reference_time: Optional reference timestamp (defaults to UTC now).

        Returns:
            Lead | None: Reopened Lead entity instance if eligible, None otherwise.
        """
        stmt = (
            select(Lead)
            .where(
                Lead.tenant_id == tenant_id,
                Lead.customer_id == customer_id,
                Lead.status == LeadStatus.LOST.value,
            )
            .order_by(Lead.closed_at.desc())
        )
        result = await db.execute(stmt)
        most_recent_lost_lead = result.scalars().first()

        if most_recent_lost_lead is None:
            return None

        if not most_recent_lost_lead.is_eligible_for_reopen(reference_time):
            return None

        # Reopen lead to New stage
        return await self.transition_lead_stage(
            db=db,
            tenant_id=tenant_id,
            lead_id=most_recent_lost_lead.id,
            target_status=LeadStatus.NEW,
        )


lead_service = LeadService()
