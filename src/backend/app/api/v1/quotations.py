"""Quotation REST API v1 Endpoints (WS-10, BR-003, BR-005, BR-006, BR-015, TASK-1004)."""

import datetime
import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.object_storage_local import LocalStorageAdapter
from app.adapters.whatsapp_demo import DemoWhatsAppProvider
from app.api.deps import CurrentUser, get_current_tenant_id
from app.core.database import get_db_session
from app.core.errors import ForbiddenException, NotFoundException
from app.models.customer import Customer
from app.models.lead import Lead
from app.models.user import User, UserRole
from app.ports.object_storage import ObjectStorageProvider
from app.ports.whatsapp import WhatsAppProvider
from app.schemas.quotation import (
    QuotationCreate,
    QuotationDetailRead,
    QuotationRead,
    QuotationSendResponse,
)
from app.services.document_service import DocumentService
from app.services.quotation_service import ItemCreateParams, QuotationService

router = APIRouter(prefix="/quotes", tags=["Quotations"])
alias_router = APIRouter(prefix="/quotations", tags=["Quotations Alias"])


def get_storage_adapter() -> ObjectStorageProvider:
    """Get configured ObjectStorageProvider instance (defaults to LocalStorageAdapter)."""
    return LocalStorageAdapter()


def get_whatsapp_adapter() -> WhatsAppProvider:
    """Get configured WhatsAppProvider instance (defaults to DemoWhatsAppProvider)."""
    return DemoWhatsAppProvider()


@router.post("", response_model=QuotationDetailRead, status_code=status.HTTP_201_CREATED)
@alias_router.post("", response_model=QuotationDetailRead, status_code=status.HTTP_201_CREATED)
async def create_quotation(
    payload: QuotationCreate,
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuotationDetailRead:
    """Create a new commercial export quotation draft with deterministic tax math."""
    service = QuotationService(db)

    items_params = [
        ItemCreateParams(
            description=item.description,
            unit_price_cents=item.unit_price_cents,
            quantity=item.quantity,
        )
        for item in payload.items
    ]

    quotation = await service.create_quotation(
        tenant_id=tenant_id,
        lead_id=payload.lead_id,
        vehicle_id=payload.vehicle_id,
        vat_regime=payload.vat_regime,
        vehicle_price_cents=payload.vehicle_price_cents,
        shipping_fee_cents=payload.shipping_fee_cents,
        items=items_params,
        discount_percentage=payload.discount_percentage,
        discount_cents=payload.discount_cents,
        has_margin_override=payload.has_margin_override,
        notes=payload.notes,
    )

    full_quote = await service.get_quotation_by_id(tenant_id, quotation.id)
    return QuotationDetailRead.from_orm_quote_detail(full_quote or quotation)


@router.get("", response_model=list[QuotationRead], status_code=status.HTTP_200_OK)
@alias_router.get("", response_model=list[QuotationRead], status_code=status.HTTP_200_OK)
async def list_quotations(
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    lead_id: Annotated[uuid.UUID | None, Query(description="Filter by Lead ID")] = None,
    quotation_status: Annotated[
        str | None, Query(alias="status", description="Filter by quotation status")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[QuotationRead]:
    """List export quotations scoped to tenant with optional filtering."""
    service = QuotationService(db)
    quotes = await service.list_quotations(
        tenant_id=tenant_id,
        lead_id=lead_id,
        status=quotation_status,
        limit=limit,
        offset=offset,
    )
    return [QuotationRead.from_orm_quote(q) for q in quotes]


@router.get("/{quotation_id}", response_model=QuotationDetailRead, status_code=status.HTTP_200_OK)
@alias_router.get(
    "/{quotation_id}", response_model=QuotationDetailRead, status_code=status.HTTP_200_OK
)
async def get_quotation(
    quotation_id: uuid.UUID,
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuotationDetailRead:
    """Fetch quotation detailed breakdown by ID."""
    service = QuotationService(db)
    quotation = await service.get_quotation_by_id(tenant_id, quotation_id)
    if quotation is None:
        raise NotFoundException(f"Quotation with ID '{quotation_id}' not found")
    return QuotationDetailRead.from_orm_quote_detail(quotation)


@router.post(
    "/{quotation_id}/approve",
    response_model=QuotationDetailRead,
    status_code=status.HTTP_200_OK,
)
@alias_router.post(
    "/{quotation_id}/approve",
    response_model=QuotationDetailRead,
    status_code=status.HTTP_200_OK,
)
async def approve_quotation(
    quotation_id: uuid.UUID,
    current_user: CurrentUser,
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuotationDetailRead:
    """Approve a pending manager discount quotation (BR-015, TenantAdmin role required)."""
    user_role_val = (
        current_user.role.value
        if isinstance(current_user.role, UserRole)
        else str(current_user.role)
    )
    if user_role_val != UserRole.TENANT_ADMIN.value:
        raise ForbiddenException("Only TenantAdmin can approve quotations with discount overrides")

    user_entity = User(
        id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        role=user_role_val,
        email=current_user.email,
        is_active=current_user.is_active,
    )

    service = QuotationService(db)
    quotation = await service.approve_quotation(
        tenant_id=tenant_id,
        quotation_id=quotation_id,
        admin_user=user_entity,
    )
    return QuotationDetailRead.from_orm_quote_detail(quotation)


@router.post(
    "/{quotation_id}/reject",
    response_model=QuotationDetailRead,
    status_code=status.HTTP_200_OK,
)
@alias_router.post(
    "/{quotation_id}/reject",
    response_model=QuotationDetailRead,
    status_code=status.HTTP_200_OK,
)
async def reject_quotation(
    quotation_id: uuid.UUID,
    current_user: CurrentUser,
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuotationDetailRead:
    """Reject a pending manager discount quotation (BR-015, TenantAdmin role required)."""
    user_role_val = (
        current_user.role.value
        if isinstance(current_user.role, UserRole)
        else str(current_user.role)
    )
    if user_role_val != UserRole.TENANT_ADMIN.value:
        raise ForbiddenException("Only TenantAdmin can reject quotations")

    user_entity = User(
        id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        role=user_role_val,
        email=current_user.email,
        is_active=current_user.is_active,
    )

    service = QuotationService(db)
    quotation = await service.reject_quotation(
        tenant_id=tenant_id,
        quotation_id=quotation_id,
        admin_user=user_entity,
    )
    return QuotationDetailRead.from_orm_quote_detail(quotation)


@router.post(
    "/{quotation_id}/send",
    response_model=QuotationSendResponse,
    status_code=status.HTTP_200_OK,
)
@alias_router.post(
    "/{quotation_id}/send",
    response_model=QuotationSendResponse,
    status_code=status.HTTP_200_OK,
)
async def send_quotation(
    quotation_id: uuid.UUID,
    current_user: CurrentUser,
    tenant_id: Annotated[uuid.UUID, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    storage: Annotated[ObjectStorageProvider, Depends(get_storage_adapter)],
    whatsapp: Annotated[WhatsAppProvider, Depends(get_whatsapp_adapter)],
) -> QuotationSendResponse:
    """Render PDF, upload to storage, and dispatch via WhatsApp (BR-003, BR-015)."""
    quote_service = QuotationService(db)
    quotation = await quote_service.get_quotation_by_id(tenant_id, quotation_id)
    if quotation is None:
        raise NotFoundException(f"Quotation with ID '{quotation_id}' not found")

    # BR-015: Enforce manager approval check before sending
    if quotation.approval_status == "Pending_Approval":
        raise ForbiddenException("Cannot dispatch quote pending manager discount approval (BR-015)")
    if quotation.approval_status == "Rejected":
        raise ForbiddenException("Cannot dispatch a rejected quotation")

    user_role_val = (
        current_user.role.value
        if isinstance(current_user.role, UserRole)
        else str(current_user.role)
    )
    user_entity = User(
        id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        role=user_role_val,
        email=current_user.email,
        is_active=current_user.is_active,
    )

    # 1. Render & upload PDF document
    doc_service = DocumentService(session=db, storage_provider=storage)
    doc = await doc_service.generate_and_store_quote_pdf(
        tenant_id=tenant_id,
        quotation_id=quotation_id,
        requesting_user=user_entity,
    )

    # 2. Retrieve presigned access URL
    _, access_url = await doc_service.get_document_access_url(
        tenant_id=tenant_id,
        document_id=doc.id,
        requesting_user=user_entity,
        expiration_seconds=86400,
    )

    # 3. Update quote status to Sent
    updated_quote = await quote_service.mark_as_sent(
        tenant_id=tenant_id,
        quotation_id=quotation_id,
        pdf_s3_key=doc.object_key,
    )

    # 4. Fetch customer phone number
    lead_query = select(Lead).where(Lead.id == quotation.lead_id)
    lead_res = await db.execute(lead_query)
    lead = lead_res.scalar_one_or_none()

    recipient_phone = "+21698000000"
    if lead and lead.customer_id:
        cust_query = select(Customer).where(Customer.id == lead.customer_id)
        cust_res = await db.execute(cust_query)
        customer = cust_res.scalar_one_or_none()
        if customer and customer.phone_e164:
            recipient_phone = customer.phone_e164

    # 5. Dispatch via WhatsAppProvider
    message_text = (
        f"Bonjour,\n\nVoici votre devis d'exportation automobile "
        f"{updated_quote.quote_number}:\n"
        f"Montant Total: € {Decimal(updated_quote.total_price_cents) / Decimal('100'):,.2f}\n"
        f"Estimation Douane Tunisie: TND {updated_quote.customs_estimate_tnd:,.3f}\n\n"
        f"Téléchargez votre PDF sécurisé: {access_url}\n\n"
        f"Offre valable 30 jours."
    )

    dispatch_res = await whatsapp.send_text_message(
        phone_number_id="business_phone_id",
        recipient_e164=recipient_phone,
        text_body=message_text,
    )

    return QuotationSendResponse(
        quotation_id=updated_quote.id,
        quote_number=updated_quote.quote_number,
        status=updated_quote.status,
        pdf_access_url=access_url,
        recipient_phone=recipient_phone,
        whatsapp_message_id=dispatch_res.wamid,
        dispatched_at=datetime.datetime.now(datetime.UTC),
    )
