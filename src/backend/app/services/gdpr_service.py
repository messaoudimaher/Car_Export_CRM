"""GDPR Right-to-Erasure & Anonymization Engine Service (WS-15, TASK-1503)."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundException, ValidationException
from app.models.customer import Customer
from app.models.document import Document
from app.services.document_service import DocumentService

logger = logging.getLogger(__name__)


class GDPRService:
    """Service handling GDPR right-to-erasure, PII anonymization, and legal holds (TASK-1503)."""

    def __init__(
        self,
        session: AsyncSession,
        document_service: DocumentService | None = None,
    ) -> None:
        self.session = session
        self.document_service = document_service or DocumentService(session=session)

    async def anonymize_customer(
        self,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        requester_user_id: uuid.UUID,
        reason: str = "GDPR Right to Erasure Request",
    ) -> dict[str, Any]:
        """Anonymize customer PII and purge linked documents while preserving accounting history.

        Args:
            tenant_id: Tenant UUID.
            customer_id: Customer UUID to anonymize.
            requester_user_id: User UUID executing erasure request.
            reason: Execution justification notes.

        Returns:
            dict containing anonymization summary details.
        """
        if not tenant_id:
            raise ValueError("tenant_id is strictly mandatory (SEC-007)")

        stmt = select(Customer).where(
            Customer.id == customer_id,
            Customer.tenant_id == tenant_id,  # SEC-007 Filter
        )
        result = await self.session.execute(stmt)
        customer = result.scalar_one_or_none()

        if customer is None:
            raise NotFoundException(f"Customer '{customer_id}' not found for tenant")

        # Legal Hold check: Prevent erasure if active legal hold is set
        if customer.legal_hold:
            raise ValidationException("Cannot anonymize customer under active legal retention hold")

        # Idempotency check: Return cleanly if already anonymized
        if customer.is_anonymized:
            logger.info(
                f"Customer '{customer_id}' is already anonymized (idempotent call)",
                extra={"tenant_id": str(tenant_id), "customer_id": str(customer_id)},
            )
            return {
                "customer_id": customer.id,
                "tenant_id": customer.tenant_id,
                "is_anonymized": True,
                "anonymized_at": customer.anonymized_at or datetime.now(UTC),
                "documents_purged_count": 0,
                "message": "Customer PII was previously anonymized.",
            }

        # 1. Purge or delete customer-linked documents
        doc_stmt = select(Document).where(
            Document.tenant_id == tenant_id,
            Document.customer_id == customer_id,
        )
        doc_result = await self.session.execute(doc_stmt)
        docs = list(doc_result.scalars().all())
        purged_count = 0

        for doc in docs:
            try:
                await self.document_service.delete_document(tenant_id=tenant_id, document_id=doc.id)
                purged_count += 1
            except Exception as err:
                logger.warning(
                    f"Failed to delete document '{doc.id}' during GDPR anonymization: {err}",
                    extra={"document_id": str(doc.id)},
                )

        # 2. Scrub customer PII fields
        hex_suffix = customer.id.hex[:8]
        customer.first_name = "Anonymized"
        customer.last_name = f"User-{hex_suffix}"
        customer.full_name = f"Anonymized User {hex_suffix}"
        customer.email = None
        customer.phone_e164 = f"+0000000{hex_suffix}"
        customer.whatsapp_id = None
        customer.notes = None
        customer.is_anonymized = True
        customer.anonymized_at = datetime.now(UTC)

        await self.session.commit()
        await self.session.refresh(customer)

        # 3. Emit immutable audit log event
        logger.info(
            "GDPR_CUSTOMER_ANONYMIZED: Customer PII successfully scrubbed under GDPR request",
            extra={
                "event_type": "GDPR_CUSTOMER_ANONYMIZED",
                "tenant_id": str(tenant_id),
                "customer_id": str(customer_id),
                "requester_user_id": str(requester_user_id),
                "reason": reason,
                "documents_purged_count": purged_count,
                "anonymized_at": customer.anonymized_at.isoformat(),
            },
        )

        return {
            "customer_id": customer.id,
            "tenant_id": customer.tenant_id,
            "is_anonymized": True,
            "anonymized_at": customer.anonymized_at,
            "documents_purged_count": purged_count,
            "message": f"Successfully anonymized customer PII and purged {purged_count} documents.",
        }

    async def set_legal_hold(
        self,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        legal_hold: bool,
    ) -> Customer:
        """Toggle legal retention hold on a customer record under tenant scope (SEC-007)."""
        stmt = select(Customer).where(
            Customer.id == customer_id,
            Customer.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        customer = result.scalar_one_or_none()

        if customer is None:
            raise NotFoundException(f"Customer '{customer_id}' not found for tenant")

        customer.legal_hold = legal_hold
        await self.session.commit()
        await self.session.refresh(customer)

        logger.info(
            f"Set legal hold={legal_hold} on customer '{customer_id}'",
            extra={"tenant_id": str(tenant_id), "customer_id": str(customer_id)},
        )
        return customer
