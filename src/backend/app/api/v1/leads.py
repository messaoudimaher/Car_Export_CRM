"""Lead REST API v1 Endpoints (ADR 0008, ADR 0009, BR-011, BR-012)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_tenant_id, get_current_user
from app.core.database import get_db_session
from app.core.errors import NotFoundException, ValidationException
from app.models.customer import Customer
from app.models.lead import Lead, LeadPriority, LeadStatus
from app.schemas.lead import (
    ConfirmAIVehicleRequest,
    ConfirmAIVehicleRequestEnvelope,
    ConfirmAIVehicleRequestResponse,
    LeadCreate,
    LeadEnvelope,
    LeadListEnvelope,
    LeadListMeta,
    LeadResponse,
    LeadStageUpdate,
)
from app.schemas.vehicle_request import VehicleRequestResponse
from app.services.ai_confirmation_service import ai_confirmation_service
from app.services.lead_service import lead_service
from app.utils.pagination import decode_cursor, encode_cursor

router = APIRouter(prefix="/leads", tags=["Leads"])

ALLOWED_LEAD_QUERY_PARAMS = {
    "status",
    "assigned_agent_id",
    "priority",
    "customer_id",
    "cursor",
    "limit",
    "sort_by",
}


@router.get("", response_model=LeadListEnvelope, status_code=status.HTTP_200_OK)
async def list_leads(
    request: Request,
    lead_status: str | None = Query(None, alias="status", description="Filter by stage status"),
    assigned_agent_id: UUID | None = Query(None, description="Filter by assigned sales rep UUID"),
    priority: str | None = Query(None, description="Filter by priority (Low, Medium, High)"),
    customer_id: UUID | None = Query(None, description="Filter by buyer customer UUID"),
    cursor: str | None = Query(None, description="Base64 pagination cursor"),
    limit: int = Query(25, ge=1, le=100, description="Page limit (1-100)"),
    sort_by: str = Query("-created_at", description="Sort order"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> LeadListEnvelope:
    """List leads with filters and cursor pagination under tenant context."""
    # Whitelist query parameter check (ADR 0009)
    unrecognized = set(request.query_params.keys()) - ALLOWED_LEAD_QUERY_PARAMS
    if unrecognized:
        raise ValidationException(f"Unrecognized query parameter(s): {sorted(list(unrecognized))}.")

    base_stmt = select(Lead).where(Lead.tenant_id == tenant_id)

    if lead_status:
        try:
            status_enum = LeadStatus(lead_status.strip())
            base_stmt = base_stmt.where(Lead.status == status_enum.value)
        except ValueError as err:
            raise ValidationException(f"Invalid status filter value '{lead_status}'.") from err

    if assigned_agent_id is not None:
        base_stmt = base_stmt.where(Lead.assigned_agent_id == assigned_agent_id)

    if priority:
        try:
            prio_enum = LeadPriority(priority.strip())
            base_stmt = base_stmt.where(Lead.priority == prio_enum.value)
        except ValueError as err:
            raise ValidationException(f"Invalid priority filter value '{priority}'.") from err

    if customer_id is not None:
        base_stmt = base_stmt.where(Lead.customer_id == customer_id)

    # Count total matching records
    total_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_count = await session.scalar(total_stmt) or 0

    # Cursor pagination predicate
    query_stmt = base_stmt
    if cursor:
        cursor_created_at, cursor_id = decode_cursor(cursor)
        query_stmt = query_stmt.where(
            or_(
                Lead.created_at < cursor_created_at,
                (Lead.created_at == cursor_created_at) & (Lead.id < cursor_id),
            )
        )

    query_stmt = query_stmt.order_by(Lead.created_at.desc(), Lead.id.desc()).limit(limit + 1)
    results = list((await session.execute(query_stmt)).scalars().all())

    has_next = len(results) > limit
    items = results[:limit]

    next_cursor = None
    if has_next and items:
        next_cursor = encode_cursor(items[-1].created_at, items[-1].id)

    data = [LeadResponse.model_validate(ld) for ld in items]
    meta = LeadListMeta(
        limit=limit,
        has_next=has_next,
        next_cursor=next_cursor,
        total=total_count,
    )
    return LeadListEnvelope(success=True, data=data, meta=meta)


@router.post("", response_model=LeadEnvelope, status_code=status.HTTP_201_CREATED)
async def create_lead(
    payload: LeadCreate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> LeadEnvelope:
    """Create a new Lead opportunity card in New stage."""
    # Verify customer exists under tenant context
    cust_stmt = select(Customer).where(
        Customer.id == payload.customer_id,
        Customer.tenant_id == tenant_id,
    )
    customer = (await session.execute(cust_stmt)).scalar_one_or_none()
    if customer is None:
        raise NotFoundException(f"Customer with ID '{payload.customer_id}' not found.")

    lead = await lead_service.create_lead(
        db=session,
        tenant_id=tenant_id,
        customer_id=payload.customer_id,
        assigned_agent_id=payload.assigned_agent_id,
        priority=payload.priority,
        vehicle_request_id=payload.vehicle_request_id,
    )

    return LeadEnvelope(success=True, data=LeadResponse.model_validate(lead))


@router.get("/{id}", response_model=LeadEnvelope, status_code=status.HTTP_200_OK)
async def get_lead(
    id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> LeadEnvelope:
    """Fetch lead card details by ID (masked HTTP 404 IDOR check)."""
    lead = await lead_service.get_lead_by_id(session, tenant_id=tenant_id, lead_id=id)
    if lead is None:
        raise NotFoundException(f"Lead with ID '{id}' not found.")

    return LeadEnvelope(success=True, data=LeadResponse.model_validate(lead))


@router.patch("/{id}", response_model=LeadEnvelope, status_code=status.HTTP_200_OK)
@router.patch("/{id}/stage", response_model=LeadEnvelope, status_code=status.HTTP_200_OK)
async def update_lead_stage(
    id: UUID,
    payload: LeadStageUpdate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> LeadEnvelope:
    """Update lead stage status (enforcing BR-011 state machine) or lead parameters."""
    lead = await lead_service.get_lead_by_id(session, tenant_id=tenant_id, lead_id=id)
    if lead is None:
        raise NotFoundException(f"Lead with ID '{id}' not found.")

    if payload.status is not None:
        lead = await lead_service.transition_lead_stage(
            db=session,
            tenant_id=tenant_id,
            lead_id=id,
            target_status=payload.status,
            lost_reason=payload.lost_reason,
            vehicle_request_id=payload.vehicle_request_id,
            assigned_agent_id=payload.assigned_agent_id,
        )

    # Apply other non-status updates if present
    update_data = payload.model_dump(exclude_unset=True)
    if "priority" in update_data and update_data["priority"] is not None:
        lead.priority = update_data["priority"].value
    if "assigned_agent_id" in update_data:
        lead.assigned_agent_id = update_data["assigned_agent_id"]
    if "vehicle_request_id" in update_data:
        lead.vehicle_request_id = update_data["vehicle_request_id"]

    await session.commit()
    await session.refresh(lead)

    return LeadEnvelope(success=True, data=LeadResponse.model_validate(lead))


@router.post(
    "/{id}/vehicle-request/confirm",
    response_model=ConfirmAIVehicleRequestEnvelope,
    status_code=status.HTTP_200_OK,
)
async def confirm_ai_vehicle_request(
    id: UUID,
    payload: ConfirmAIVehicleRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ConfirmAIVehicleRequestEnvelope:
    """Human Confirmation Endpoint (INV-003, ADR 0012).

    Validates or edits Layer 2 AI output to create an authoritative VehicleRequest
    with is_human_validated = True, links it to Lead, and advances Lead stage to Qualified.
    """
    vreq, updated_lead = await ai_confirmation_service.confirm_ai_vehicle_request(
        db=session,
        tenant_id=tenant_id,
        lead_id=id,
        user_id=current_user.user_id,
        payload=payload,
    )

    resp_data = ConfirmAIVehicleRequestResponse(
        vehicle_request=VehicleRequestResponse.model_validate(vreq).model_dump(),
        lead=LeadResponse.model_validate(updated_lead),
    )
    return ConfirmAIVehicleRequestEnvelope(success=True, data=resp_data)
