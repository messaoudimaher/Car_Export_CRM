"""Pydantic request and response schemas for Quotation REST API (WS-10, TASK-1004)."""

import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.quotation import Quotation, QuotationItem


class QuotationItemCreate(BaseModel):
    """Line item creation parameters."""

    description: str = Field(..., min_length=1, max_length=255, description="Item description")
    unit_price_cents: int = Field(..., ge=0, description="Unit price in integer EUR cents")
    quantity: int = Field(1, ge=1, description="Quantity")


class QuotationItemRead(BaseModel):
    """Line item representation."""

    id: uuid.UUID
    quotation_id: uuid.UUID
    description: str
    unit_price_cents: int
    unit_price_eur: Decimal = Field(..., description="Unit price formatted as EUR decimal")
    quantity: int
    total_price_cents: int
    total_price_eur: Decimal = Field(..., description="Total line price formatted as EUR decimal")
    created_at: datetime.datetime

    @classmethod
    def from_orm_item(cls, item: QuotationItem) -> "QuotationItemRead":
        """Convert QuotationItem ORM entity to response schema."""
        unit_cents = getattr(item, "unit_price_cents", 0)
        total_cents = getattr(item, "total_price_cents", 0)
        return cls(
            id=item.id,
            quotation_id=item.quotation_id,
            description=item.description,
            unit_price_cents=unit_cents,
            unit_price_eur=(Decimal(unit_cents) / Decimal("100")).quantize(Decimal("0.01")),
            quantity=getattr(item, "quantity", 1),
            total_price_cents=total_cents,
            total_price_eur=(Decimal(total_cents) / Decimal("100")).quantize(Decimal("0.01")),
            created_at=item.created_at,
        )


class QuotationCreate(BaseModel):
    """Payload for creating a new quotation draft."""

    lead_id: uuid.UUID = Field(..., description="Target Lead ID")
    vehicle_id: uuid.UUID | None = Field(None, description="Optional associated Vehicle ID")
    vat_regime: str = Field(
        "Netto_Export",
        description="VAT regime (Netto_Export or Brutto_Margin)",
    )
    vehicle_price_cents: int = Field(
        ..., ge=0, description="Vehicle base purchase price in integer EUR cents"
    )
    shipping_fee_cents: int = Field(
        0, ge=0, description="Shipping & logistics fee in integer EUR cents"
    )
    items: list[QuotationItemCreate] = Field(
        default_factory=list, description="Additional quote line items"
    )
    discount_percentage: Decimal | None = Field(
        None, ge=Decimal("0.00"), le=Decimal("100.00"), description="Percentage discount"
    )
    discount_cents: int | None = Field(None, ge=0, description="Fixed EUR cent discount amount")
    has_margin_override: bool = Field(False, description="Flag indicating manual margin override")
    notes: str | None = Field(None, max_length=1000, description="Internal quotation notes")


class QuotationRead(BaseModel):
    """Summary quotation representation."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    lead_id: uuid.UUID
    vehicle_id: uuid.UUID | None
    quote_number: str
    vat_regime: str
    vehicle_price_cents: int
    vehicle_price_eur: Decimal
    shipping_fee_cents: int
    shipping_fee_eur: Decimal
    customs_estimate_tnd: Decimal
    discount_cents: int
    discount_percentage: Decimal
    total_price_cents: int
    total_price_eur: Decimal
    status: str
    approval_status: str
    pdf_s3_key: str | None
    disclaimer_text: str | None
    notes: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @classmethod
    def from_orm_quote(cls, quote: Quotation) -> "QuotationRead":
        """Convert Quotation ORM entity to summary response schema."""
        veh_cents = getattr(quote, "vehicle_price_cents", 0)
        ship_cents = getattr(quote, "shipping_fee_cents", 0)
        tot_cents = getattr(quote, "total_price_cents", 0)
        return cls(
            id=quote.id,
            tenant_id=quote.tenant_id,
            lead_id=quote.lead_id,
            vehicle_id=quote.vehicle_id,
            quote_number=quote.quote_number,
            vat_regime=quote.vat_regime,
            vehicle_price_cents=veh_cents,
            vehicle_price_eur=(Decimal(veh_cents) / Decimal("100")).quantize(Decimal("0.01")),
            shipping_fee_cents=ship_cents,
            shipping_fee_eur=(Decimal(ship_cents) / Decimal("100")).quantize(Decimal("0.01")),
            customs_estimate_tnd=quote.customs_estimate_tnd,
            discount_cents=getattr(quote, "discount_cents", 0),
            discount_percentage=getattr(quote, "discount_percentage", Decimal("0.00")),
            total_price_cents=tot_cents,
            total_price_eur=(Decimal(tot_cents) / Decimal("100")).quantize(Decimal("0.01")),
            status=quote.status,
            approval_status=quote.approval_status,
            pdf_s3_key=quote.pdf_s3_key,
            disclaimer_text=quote.disclaimer_text,
            notes=quote.notes,
            created_at=quote.created_at,
            updated_at=quote.updated_at,
        )


class QuotationDetailRead(QuotationRead):
    """Detailed quotation representation including line items."""

    items: list[QuotationItemRead] = Field(default_factory=list)

    @classmethod
    def from_orm_quote_detail(cls, quote: Quotation) -> "QuotationDetailRead":
        """Convert Quotation ORM entity with items to detailed response schema."""
        summary = QuotationRead.from_orm_quote(quote)
        raw_items = getattr(quote, "items", []) or []
        items_read = [QuotationItemRead.from_orm_item(i) for i in raw_items]
        return cls(
            **summary.model_dump(),
            items=items_read,
        )


class QuotationSendResponse(BaseModel):
    """Response payload following quotation WhatsApp dispatch."""

    quotation_id: uuid.UUID
    quote_number: str
    status: str
    pdf_access_url: str
    recipient_phone: str
    whatsapp_message_id: str
    dispatched_at: datetime.datetime
