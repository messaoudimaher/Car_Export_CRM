"""Quotation Service managing export price offers, approval workflows & provenance (WS-10)."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ForbiddenException, NotFoundException, ValidationException
from app.models.lead import Lead
from app.models.quotation import Quotation, QuotationApprovalStatus, QuotationItem, QuotationStatus
from app.models.user import User, UserRole
from app.models.vehicle import Vehicle
from app.services.tax_engine import TaxCalculationResult, TaxEngine


@dataclass(frozen=True)
class ItemCreateParams:
    """Input payload parameters for creating quote line items."""

    description: str
    unit_price_cents: int
    quantity: int = 1


class QuotationService:
    """Service layer managing commercial export quote creation and approval workflows."""

    def __init__(self, session: AsyncSession, tax_engine: TaxEngine | None = None) -> None:
        self.session = session
        self.tax_engine = tax_engine or TaxEngine()

    async def create_quotation(
        self,
        tenant_id: uuid.UUID,
        lead_id: uuid.UUID,
        vehicle_id: uuid.UUID | None,
        vat_regime: str,
        vehicle_price_cents: int,
        shipping_fee_cents: int = 0,
        items: Sequence[ItemCreateParams] | None = None,
        discount_percentage: Decimal | None = None,
        discount_cents: int | None = None,
        has_margin_override: bool = False,
        notes: str | None = None,
    ) -> Quotation:
        """Create a new Quotation record with deterministic tax & customs calculations."""
        # Validate lead existence and tenant ownership
        lead_query = select(Lead).where(Lead.id == lead_id, Lead.tenant_id == tenant_id)
        lead_result = await self.session.execute(lead_query)
        lead = lead_result.scalar_one_or_none()
        if lead is None:
            raise NotFoundException(f"Lead with ID '{lead_id}' not found")

        # Validate vehicle existence if provided
        if vehicle_id is not None:
            v_query = select(Vehicle).where(
                Vehicle.id == vehicle_id, Vehicle.tenant_id == tenant_id
            )
            v_result = await self.session.execute(v_query)
            if v_result.scalar_one_or_none() is None:
                raise NotFoundException(f"Vehicle with ID '{vehicle_id}' not found")

        # Calculate additional line items total
        item_objects: list[QuotationItem] = []
        additional_items_cents = 0

        if items:
            for item in items:
                if item.quantity <= 0:
                    raise ValidationException("Line item quantity must be greater than zero")
                if item.unit_price_cents < 0:
                    raise ValidationException("Line item price cannot be negative")
                item_total = item.unit_price_cents * item.quantity
                additional_items_cents += item_total
                item_objects.append(
                    QuotationItem(
                        description=item.description,
                        unit_price_cents=item.unit_price_cents,
                        quantity=item.quantity,
                        total_price_cents=item_total,
                    )
                )

        # Execute deterministic tax and customs calculation engine
        calc_result: TaxCalculationResult = self.tax_engine.calculate(
            vat_regime=vat_regime,
            vehicle_price_cents=vehicle_price_cents,
            shipping_fee_cents=shipping_fee_cents,
            additional_items_cents=additional_items_cents,
            discount_percentage=discount_percentage,
            discount_cents=discount_cents,
            has_margin_override=has_margin_override,
        )

        # Generate unique quote reference number
        quote_ref_id = uuid.uuid4().hex[:8].upper()
        quote_number = f"QT-2026-{quote_ref_id}"

        quotation = Quotation(
            tenant_id=tenant_id,
            lead_id=lead_id,
            vehicle_id=vehicle_id,
            quote_number=quote_number,
            vat_regime=calc_result.vat_regime,
            vehicle_price_cents=calc_result.vehicle_price_cents,
            shipping_fee_cents=calc_result.shipping_fee_cents,
            customs_estimate_tnd=calc_result.customs_estimate_tnd,
            discount_cents=calc_result.discount_cents,
            discount_percentage=calc_result.discount_percentage,
            total_price_cents=calc_result.total_price_cents,
            status=calc_result.status.value,
            approval_status=calc_result.approval_status.value,
            disclaimer_text=calc_result.disclaimer_text,
            notes=notes,
        )

        for item_obj in item_objects:
            quotation.items.append(item_obj)

        self.session.add(quotation)
        await self.session.flush()
        return quotation

    async def get_quotation_by_id(
        self, tenant_id: uuid.UUID, quotation_id: uuid.UUID
    ) -> Quotation | None:
        """Fetch quotation by ID with eager loading of items, scoped to tenant."""
        stmt = (
            select(Quotation)
            .options(selectinload(Quotation.items))
            .where(Quotation.id == quotation_id, Quotation.tenant_id == tenant_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def approve_quotation(
        self, tenant_id: uuid.UUID, quotation_id: uuid.UUID, admin_user: User
    ) -> Quotation:
        """Approve a pending manager discount/margin quotation (BR-015)."""
        if admin_user.role != UserRole.TENANT_ADMIN.value:
            raise ForbiddenException(
                "Only TenantAdmin can approve quotations with discount overrides"
            )

        quotation = await self.get_quotation_by_id(tenant_id, quotation_id)
        if quotation is None:
            raise NotFoundException(f"Quotation with ID '{quotation_id}' not found")

        if quotation.approval_status != QuotationApprovalStatus.PENDING_APPROVAL.value:
            msg = f"Quotation '{quotation_id}' is not pending approval"
            raise ValidationException(msg)

        quotation.approval_status = QuotationApprovalStatus.APPROVED.value
        quotation.status = QuotationStatus.APPROVED.value
        await self.session.flush()
        return quotation

    async def reject_quotation(
        self, tenant_id: uuid.UUID, quotation_id: uuid.UUID, admin_user: User
    ) -> Quotation:
        """Reject a pending manager discount/margin quotation (BR-015)."""
        if admin_user.role != UserRole.TENANT_ADMIN.value:
            raise ForbiddenException("Only TenantAdmin can reject quotations")

        quotation = await self.get_quotation_by_id(tenant_id, quotation_id)
        if quotation is None:
            raise NotFoundException(f"Quotation with ID '{quotation_id}' not found")

        if quotation.approval_status != QuotationApprovalStatus.PENDING_APPROVAL.value:
            msg = f"Quotation '{quotation_id}' is not pending approval"
            raise ValidationException(msg)

        quotation.approval_status = QuotationApprovalStatus.REJECTED.value
        quotation.status = QuotationStatus.REJECTED.value
        await self.session.flush()
        return quotation
