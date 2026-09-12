"""Vehicle Catalog REST API v1 Endpoints (ADR 0008, ADR 0009, BR-005)."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_tenant_id, get_current_user
from app.core.database import get_db_session
from app.core.errors import NotFoundException, ValidationException
from app.models.vehicle import VATRegime, Vehicle, VehicleStatus
from app.schemas.vehicle import (
    VehicleCreate,
    VehicleEnvelope,
    VehicleListEnvelope,
    VehicleListMeta,
    VehicleResponse,
    VehicleUpdate,
)
from app.utils.pagination import decode_cursor, encode_cursor

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])

ALLOWED_VEHICLE_QUERY_PARAMS = {
    "make",
    "model",
    "min_year",
    "max_year",
    "max_price_eur",
    "vat_regime",
    "status",
    "cursor",
    "limit",
    "sort_by",
}


@router.get("", response_model=VehicleListEnvelope, status_code=status.HTTP_200_OK)
async def list_vehicles(
    request: Request,
    make: str | None = Query(None, description="Filter by make manufacturer"),
    model: str | None = Query(None, description="Filter by model name"),
    min_year: int | None = Query(None, ge=1900, le=2100, description="Minimum registration year"),
    max_year: int | None = Query(None, ge=1900, le=2100, description="Maximum registration year"),
    max_price_eur: Decimal | None = Query(None, ge=0, description="Maximum purchase price in EUR"),
    vat_regime: str | None = Query(None, description="Filter by Netto_Export or Brutto_Margin"),
    veh_status: str | None = Query(None, alias="status", description="Stock status filter"),
    cursor: str | None = Query(None, description="Base64 pagination cursor"),
    limit: int = Query(25, ge=1, le=100, description="Page limit (1-100)"),
    sort_by: str = Query("-created_at", description="Sort order"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> VehicleListEnvelope:
    """List vehicle catalog stock with search filtering and cursor pagination."""
    # Whitelist query parameter check (ADR 0009)
    unrecognized = set(request.query_params.keys()) - ALLOWED_VEHICLE_QUERY_PARAMS
    if unrecognized:
        raise ValidationException(f"Unrecognized query parameter(s): {sorted(list(unrecognized))}.")

    base_stmt = select(Vehicle).where(Vehicle.tenant_id == tenant_id)

    if make:
        base_stmt = base_stmt.where(Vehicle.make.ilike(f"%{make.strip()}%"))

    if model:
        base_stmt = base_stmt.where(Vehicle.model.ilike(f"%{model.strip()}%"))

    if min_year is not None:
        base_stmt = base_stmt.where(Vehicle.first_registration_year >= min_year)

    if max_year is not None:
        base_stmt = base_stmt.where(Vehicle.first_registration_year <= max_year)

    if max_price_eur is not None:
        base_stmt = base_stmt.where(Vehicle.purchase_price_eur <= max_price_eur)

    if vat_regime:
        try:
            vat_enum = VATRegime(vat_regime.strip())
            base_stmt = base_stmt.where(Vehicle.vat_regime == vat_enum.value)
        except ValueError as err:
            raise ValidationException(f"Invalid vat_regime parameter '{vat_regime}'.") from err

    if veh_status:
        try:
            status_enum = VehicleStatus(veh_status.strip())
            base_stmt = base_stmt.where(Vehicle.status == status_enum.value)
        except ValueError as err:
            raise ValidationException(f"Invalid status parameter '{veh_status}'.") from err

    # Count total records matching filters
    total_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_count = await session.scalar(total_stmt) or 0

    # Cursor pagination predicate
    query_stmt = base_stmt
    if cursor:
        cursor_created_at, cursor_id = decode_cursor(cursor)
        query_stmt = query_stmt.where(
            or_(
                Vehicle.created_at < cursor_created_at,
                (Vehicle.created_at == cursor_created_at) & (Vehicle.id < cursor_id),
            )
        )

    query_stmt = query_stmt.order_by(Vehicle.created_at.desc(), Vehicle.id.desc()).limit(limit + 1)
    results = list((await session.execute(query_stmt)).scalars().all())

    has_next = len(results) > limit
    items = results[:limit]

    next_cursor = None
    if has_next and items:
        next_cursor = encode_cursor(items[-1].created_at, items[-1].id)

    data = [VehicleResponse.model_validate(v) for v in items]
    meta = VehicleListMeta(
        limit=limit,
        has_next=has_next,
        next_cursor=next_cursor,
        total=total_count,
    )
    return VehicleListEnvelope(success=True, data=data, meta=meta)


@router.post("", response_model=VehicleEnvelope, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    payload: VehicleCreate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> VehicleEnvelope:
    """Create a new vehicle stock record under tenant context."""
    vehicle = Vehicle(
        tenant_id=tenant_id,
        vin=payload.vin,
        make=payload.make,
        model=payload.model,
        first_registration_year=payload.first_registration_year,
        mileage_km=payload.mileage_km,
        fuel_type=payload.fuel_type,
        transmission=payload.transmission,
        purchase_price_eur=payload.purchase_price_eur,
        vat_regime=payload.vat_regime.value,
        supplier_name=payload.supplier_name,
        supplier_location=payload.supplier_location,
        status=payload.status.value,
    )
    session.add(vehicle)
    await session.commit()
    await session.refresh(vehicle)

    return VehicleEnvelope(success=True, data=VehicleResponse.model_validate(vehicle))


@router.get("/{id}", response_model=VehicleEnvelope, status_code=status.HTTP_200_OK)
async def get_vehicle(
    id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> VehicleEnvelope:
    """Fetch single vehicle stock record by ID (masked HTTP 404 IDOR check)."""
    stmt = select(Vehicle).where(
        Vehicle.id == id,
        Vehicle.tenant_id == tenant_id,
    )
    vehicle = (await session.execute(stmt)).scalar_one_or_none()
    if vehicle is None:
        raise NotFoundException(f"Vehicle with ID '{id}' not found.")

    return VehicleEnvelope(success=True, data=VehicleResponse.model_validate(vehicle))


@router.patch("/{id}", response_model=VehicleEnvelope, status_code=status.HTTP_200_OK)
async def update_vehicle(
    id: UUID,
    payload: VehicleUpdate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> VehicleEnvelope:
    """Update vehicle stock details under tenant context."""
    stmt = select(Vehicle).where(
        Vehicle.id == id,
        Vehicle.tenant_id == tenant_id,
    )
    vehicle = (await session.execute(stmt)).scalar_one_or_none()
    if vehicle is None:
        raise NotFoundException(f"Vehicle with ID '{id}' not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            if isinstance(value, (VATRegime, VehicleStatus)):
                setattr(vehicle, field, value.value)
            else:
                setattr(vehicle, field, value)

    await session.commit()
    await session.refresh(vehicle)

    return VehicleEnvelope(success=True, data=VehicleResponse.model_validate(vehicle))
