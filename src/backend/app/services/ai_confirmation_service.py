"""AI Understanding & Human Confirmation Boundary Service (INV-003, ADR 0012)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundException
from app.core.logging import logger
from app.models.lead import Lead, LeadStatus
from app.models.vehicle_request import VehicleRequest
from app.schemas.lead import ConfirmAIVehicleRequest
from app.services.lead_service import lead_service


class AIConfirmationService:
    """Domain service enforcing Human-in-the-Loop boundary for AI extractions (INV-003)."""

    async def confirm_ai_vehicle_request(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        lead_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: ConfirmAIVehicleRequest,
    ) -> tuple[VehicleRequest, Lead]:
        """Convert provisional Layer 2 AI extraction into ground-truth VehicleRequest (ADR 0012).

        Args:
            db: AsyncSession database session.
            tenant_id: Authenticated tenant organization UUID.
            lead_id: Sales Lead entity UUID.
            user_id: Authenticated sales representative user UUID.
            payload: Human-reviewed vehicle sourcing parameters.

        Returns:
            tuple[VehicleRequest, Lead]: Created VehicleRequest and updated Lead entity tuple.

        Raises:
            NotFoundException: If Lead with lead_id is not found under tenant_id.
        """
        lead = await lead_service.get_lead_by_id(db, tenant_id=tenant_id, lead_id=lead_id)
        if lead is None:
            raise NotFoundException(f"Lead with ID '{lead_id}' not found.")

        budget_dec: Decimal | None = None
        if payload.budget_eur is not None:
            budget_dec = Decimal(str(payload.budget_eur))

        # 1. Instantiate authoritative VehicleRequest (Layer 3/4)
        vreq = VehicleRequest(
            tenant_id=tenant_id,
            customer_id=lead.customer_id,
            make=payload.make,
            model=payload.model,
            min_year=payload.min_year,
            max_year=payload.max_year,
            fuel_type=payload.fuel_type,
            transmission=payload.transmission,
            max_mileage_km=payload.max_mileage_km,
            budget_eur=budget_dec,
            destination_port=payload.destination_port,
            is_human_validated=True,
            confirmed_by_user_id=user_id,
            confirmed_at=datetime.now(UTC),
        )
        db.add(vreq)
        await db.flush()

        # 2. Link VehicleRequest to Lead
        lead.vehicle_request_id = vreq.id

        # 3. Advance Lead state from New -> Qualified if current state is New
        if lead.status == LeadStatus.NEW.value:
            lead = await lead_service.transition_lead_stage(
                db=db,
                tenant_id=tenant_id,
                lead_id=lead_id,
                target_status=LeadStatus.QUALIFIED,
                vehicle_request_id=vreq.id,
            )
        else:
            await db.commit()
            await db.refresh(lead)

        await db.refresh(vreq)

        # 4. Audit Log Event: AI_EXTRACTION_CORRECTED_BY_HUMAN
        logger.info(
            "ai_extraction_corrected_by_human",
            extra={
                "event_type": "AI_EXTRACTION_CORRECTED_BY_HUMAN",
                "lead_id": str(lead_id),
                "vehicle_request_id": str(vreq.id),
                "tenant_id": str(tenant_id),
                "confirmed_by_user_id": str(user_id),
                "ai_understanding_id": (
                    str(payload.ai_understanding_id) if payload.ai_understanding_id else None
                ),
            },
        )

        return vreq, lead


ai_confirmation_service = AIConfirmationService()
