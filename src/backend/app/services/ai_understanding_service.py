"""AI Understanding Service for provisional Layer 2 extraction results (INV-003, ADR 0007)."""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_understanding import (
    AIUnderstanding,
    AIUnderstandingStatus,
)
from app.schemas.ai_extraction import AIExtractionResult


class AIUnderstandingService:
    """Service layer managing persistence and status transitions for AIUnderstanding records."""

    @staticmethod
    async def create_provisional_understanding(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        extraction_result: AIExtractionResult,
        conversation_id: uuid.UUID | None = None,
        message_id: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
        model_name: str = "gpt-4o-mini",
        prompt_version: str = "v1.0",
    ) -> AIUnderstanding:
        """Persist a provisional Layer 2 extraction result into the ai_understandings table.

        INVARIANT (INV-003): Initial creation strictly sets status = Provisional and writes
        ONLY to the ai_understandings table. Ground-truth domain tables (leads, vehicle_requests,
        vehicles, customers) are NEVER mutated directly by AI operations.
        """
        # Ensure confidence_score is Decimal formatted between 0.000 and 1.000
        raw_conf = min(max(float(extraction_result.confidence_score), 0.0), 1.0)
        confidence_decimal = Decimal(f"{raw_conf:.3f}")

        intent_val = (
            extraction_result.intent.value
            if hasattr(extraction_result.intent, "value")
            else str(extraction_result.intent)
        )
        lang_val = (
            extraction_result.detected_language.value
            if hasattr(extraction_result.detected_language, "value")
            else str(extraction_result.detected_language)
        )

        understanding = AIUnderstanding(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            message_id=message_id,
            customer_id=customer_id,
            intent=intent_val,
            extracted_data_jsonb=extraction_result.model_dump(mode="json"),
            confidence_score=confidence_decimal,
            status=AIUnderstandingStatus.PROVISIONAL.value,
            detected_language=lang_val,
            summary_fr=extraction_result.summary_fr,
            model_name=model_name,
            prompt_version=prompt_version,
        )

        db.add(understanding)
        await db.flush()
        return understanding

    @staticmethod
    async def get_understanding_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        understanding_id: uuid.UUID,
    ) -> AIUnderstanding | None:
        """Fetch an AIUnderstanding record by ID scoped by tenant_id."""
        stmt = select(AIUnderstanding).where(
            AIUnderstanding.id == understanding_id,
            AIUnderstanding.tenant_id == tenant_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_understandings(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        conversation_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AIUnderstanding]:
        """List AIUnderstanding records with optional conversation and status filters."""
        stmt = select(AIUnderstanding).where(AIUnderstanding.tenant_id == tenant_id)
        if conversation_id is not None:
            stmt = stmt.where(AIUnderstanding.conversation_id == conversation_id)
        if status is not None:
            stmt = stmt.where(AIUnderstanding.status == status)

        stmt = stmt.order_by(AIUnderstanding.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_status(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        understanding_id: uuid.UUID,
        new_status: AIUnderstandingStatus | str,
    ) -> AIUnderstanding:
        """Transition status of an AIUnderstanding record (e.g. Confirmed or Rejected)."""
        status_val = (
            new_status.value if isinstance(new_status, AIUnderstandingStatus) else str(new_status)
        )
        if status_val not in [s.value for s in AIUnderstandingStatus]:
            raise ValueError(f"Invalid AIUnderstandingStatus value: {new_status}")

        understanding = await AIUnderstandingService.get_understanding_by_id(
            db=db,
            tenant_id=tenant_id,
            understanding_id=understanding_id,
        )
        if not understanding:
            raise ValueError(
                f"AIUnderstanding record {understanding_id} not found for tenant {tenant_id}"
            )

        understanding.status = status_val
        await db.flush()
        return understanding
