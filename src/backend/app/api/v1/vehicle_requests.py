"""Vehicle Request REST API v1 Endpoints (ADR 0008, ADR 0009, BR-004)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_tenant_id, get_current_user
from app.core.database import get_db_session
from app.core.errors import NotFoundException, ValidationException
from app.models.customer import Customer
from app.models.vehicle_request import VehicleRequest
from app.schemas.vehicle_request import (
    VehicleRequestCreate,
    VehicleRequestEnvelope,
    VehicleRequestListEnvelope,
    VehicleRequestListMeta,
    VehicleRequestResponse,
)
from app.utils.pagination import decode_cursor, encode_cursor

router = APIRouter(prefix="/vehicle-requests", tags=["Vehicle Requests"])

ALLOWED_VEHICLE_REQUEST_QUERY_PARAMS = {
    "customer_id",
    "fcr_compatible",
    "make",
    "status",
    "cursor",
    "limit",
    "sort_by",
}


@router.get("", response_model=VehicleRequestListEnvelope, status_code=status.HTTP_200_OK)
async def list_vehicle_requests(
    request: Request,
    customer_id: UUID | None = Query(None, description="Filter by customer UUID"),
    fcr_compatible: bool | None = Query(None, description="Filter by FCR age compliance"),
    make: str | None = Query(None, description="Filter by manufacturer brand"),
    req_status: str | None = Query(None, alias="status", description="Filter by request status"),
    cursor: str | None = Query(None, description="Base64 pagination cursor"),
    limit: int = Query(25, ge=1, le=100, description="Page limit (1-100)"),
    sort_by: str = Query("-created_at", description="Sort order"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> VehicleRequestListEnvelope:
    """List vehicle requests with filters and cursor pagination under tenant context."""
    # Whitelist query parameter check (ADR 0009)
    unrecognized = set(request.query_params.keys()) - ALLOWED_VEHICLE_REQUEST_QUERY_PARAMS
    if unrecognized:
        raise ValidationException(f"Unrecognized query parameter(s): {sorted(list(unrecognized))}.")

    base_stmt = select(VehicleRequest).where(VehicleRequest.tenant_id == tenant_id)

    if customer_id is not None:
        base_stmt = base_stmt.where(VehicleRequest.customer_id == customer_id)

    if fcr_compatible is not None:
        base_stmt = base_stmt.where(VehicleRequest.fcr_compatible == fcr_compatible)

    if make:
        base_stmt = base_stmt.where(VehicleRequest.make.ilike(f"%{make.strip()}%"))

    if req_status:
        base_stmt = base_stmt.where(VehicleRequest.status == req_status.strip())

    # Count total records matching filter predicate
    total_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_count = await session.scalar(total_stmt) or 0

    # Cursor pagination
    query_stmt = base_stmt
    if cursor:
        cursor_created_at, cursor_id = decode_cursor(cursor)
        query_stmt = query_stmt.where(
            or_(
                VehicleRequest.created_at < cursor_created_at,
                (VehicleRequest.created_at == cursor_created_at) & (VehicleRequest.id < cursor_id),
            )
        )

    query_stmt = query_stmt.order_by(
        VehicleRequest.created_at.desc(), VehicleRequest.id.desc()
    ).limit(limit + 1)
    results = list((await session.execute(query_stmt)).scalars().all())

    has_next = len(results) > limit
    items = results[:limit]

    next_cursor = None
    if has_next and items:
        next_cursor = encode_cursor(items[-1].created_at, items[-1].id)

    data = [VehicleRequestResponse.model_validate(v) for v in items]
    meta = VehicleRequestListMeta(
        limit=limit,
        has_next=has_next,
        next_cursor=next_cursor,
        total=total_count,
    )
    return VehicleRequestListEnvelope(success=True, data=data, meta=meta)


@router.post("", response_model=VehicleRequestEnvelope, status_code=status.HTTP_201_CREATED)
async def create_vehicle_request(
    payload: VehicleRequestCreate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> VehicleRequestEnvelope:
    """Create a vehicle request calculating FCR 5-year age compliance (BR-004)."""
    # Verify target customer exists under tenant context
    cust_stmt = select(Customer).where(
        Customer.id == payload.customer_id,
        Customer.tenant_id == tenant_id,
    )
    customer = (await session.execute(cust_stmt)).scalar_one_or_none()
    if customer is None:
        raise NotFoundException(f"Customer with ID '{payload.customer_id}' not found.")

    vreq = VehicleRequest(
        tenant_id=tenant_id,
        customer_id=payload.customer_id,
        make=payload.make,
        model=payload.model,
        min_year=payload.min_year,
        max_year=payload.max_year,
        fuel_type=payload.fuel_type,
        transmission=payload.transmission,
        max_mileage_km=payload.max_mileage_km,
        budget_eur=payload.budget_eur,
        destination_port=payload.destination_port,
    )
    session.add(vreq)
    await session.commit()
    await session.refresh(vreq)

    return VehicleRequestEnvelope(
        success=True,
        data=VehicleRequestResponse.model_validate(vreq),
    )


@router.get("/{id}", response_model=VehicleRequestEnvelope, status_code=status.HTTP_200_OK)
async def get_vehicle_request(
    id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> VehicleRequestEnvelope:
    """Fetch single vehicle request by ID (masked HTTP 404 IDOR check)."""
    stmt = select(VehicleRequest).where(
        VehicleRequest.id == id,
        VehicleRequest.tenant_id == tenant_id,
    )
    vreq = (await session.execute(stmt)).scalar_one_or_none()
    if vreq is None:
        raise NotFoundException(f"Vehicle request with ID '{id}' not found.")

    return VehicleRequestEnvelope(
        success=True,
        data=VehicleRequestResponse.model_validate(vreq),
    )
