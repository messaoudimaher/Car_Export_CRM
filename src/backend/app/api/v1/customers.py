"""Customer REST API v1 Endpoints (ADR 0008, ADR 0009)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_tenant_id, get_current_user
from app.core.database import get_db_session
from app.core.errors import ValidationException
from app.models.customer import Customer
from app.schemas.customer import (
    CustomerCreate,
    CustomerEnvelope,
    CustomerListEnvelope,
    CustomerListMeta,
    CustomerResponse,
    CustomerUpdate,
)
from app.services.customer_service import CustomerService
from app.utils.pagination import decode_cursor, encode_cursor

router = APIRouter(prefix="/customers", tags=["Customers"])

ALLOWED_CUSTOMER_QUERY_PARAMS = {
    "search",
    "fcr_eligible",
    "preferred_language",
    "cursor",
    "limit",
    "sort_by",
}


@router.get("", response_model=CustomerListEnvelope, status_code=status.HTTP_200_OK)
async def list_customers(
    request: Request,
    search: str | None = Query(None, description="Search term"),
    fcr_eligible: bool | None = Query(None, description="FCR filter"),
    preferred_language: str | None = Query(None, description="Language filter (fr, ar_tn, en)"),
    cursor: str | None = Query(None, description="Base64 cursor"),
    limit: int = Query(25, ge=1, le=100, description="Page limit (1-100)"),
    sort_by: str = Query("-created_at", description="Sort order"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> CustomerListEnvelope:
    """List customer profiles with search filtering and cursor pagination."""
    # Whitelist check for query parameters (ADR 0009)
    unrecognized = set(request.query_params.keys()) - ALLOWED_CUSTOMER_QUERY_PARAMS
    if unrecognized:
        raise ValidationException(f"Unrecognized query parameter(s): {sorted(list(unrecognized))}.")

    # Base query scoped to current tenant
    base_stmt = select(Customer).where(Customer.tenant_id == tenant_id)

    # Filter constraints
    if fcr_eligible is not None:
        base_stmt = base_stmt.where(Customer.fcr_eligible == fcr_eligible)

    if preferred_language:
        if preferred_language not in ("fr", "ar_tn", "en"):
            raise ValidationException(
                f"Invalid preferred_language parameter '{preferred_language}'."
            )
        base_stmt = base_stmt.where(Customer.preferred_language == preferred_language)

    if search:
        search_pattern = f"%{search.strip()}%"
        base_stmt = base_stmt.where(
            or_(
                Customer.phone_e164.ilike(search_pattern),
                Customer.full_name.ilike(search_pattern),
                Customer.email.ilike(search_pattern),
            )
        )

    # Count total records matching filters
    total_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_count = await session.scalar(total_stmt) or 0

    # Cursor pagination predicate
    query_stmt = base_stmt
    if cursor:
        cursor_created_at, cursor_id = decode_cursor(cursor)
        query_stmt = query_stmt.where(
            or_(
                Customer.created_at < cursor_created_at,
                (Customer.created_at == cursor_created_at) & (Customer.id < cursor_id),
            )
        )

    # Ordering & Fetching limit + 1
    query_stmt = query_stmt.order_by(Customer.created_at.desc(), Customer.id.desc()).limit(
        limit + 1
    )
    results = list((await session.execute(query_stmt)).scalars().all())

    has_next = len(results) > limit
    items = results[:limit]

    next_cursor = None
    if has_next and items:
        next_cursor = encode_cursor(items[-1].created_at, items[-1].id)

    data = [CustomerResponse.model_validate(c) for c in items]
    meta = CustomerListMeta(
        limit=limit,
        has_next=has_next,
        next_cursor=next_cursor,
        total=total_count,
    )
    return CustomerListEnvelope(success=True, data=data, meta=meta)


@router.post("", response_model=CustomerEnvelope, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerCreate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> CustomerEnvelope:
    """Create a new customer profile under authenticated tenant context."""
    service = CustomerService(session, tenant_id)
    customer = await service.create_customer(
        phone=payload.phone,
        full_name=payload.full_name,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        preferred_language=payload.preferred_language,
        fcr_eligible=payload.fcr_eligible,
        notes=payload.notes,
    )
    return CustomerEnvelope(success=True, data=CustomerResponse.model_validate(customer))


@router.get("/{id}", response_model=CustomerEnvelope, status_code=status.HTTP_200_OK)
async def get_customer(
    id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> CustomerEnvelope:
    """Fetch customer profile by ID (HTTP 404 masked IDOR defense)."""
    service = CustomerService(session, tenant_id)
    customer = await service.get_by_id(id)
    return CustomerEnvelope(success=True, data=CustomerResponse.model_validate(customer))


@router.patch("/{id}", response_model=CustomerEnvelope, status_code=status.HTTP_200_OK)
async def update_customer(
    id: UUID,
    payload: CustomerUpdate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> CustomerEnvelope:
    """Update customer profile details strictly scoped to tenant context."""
    service = CustomerService(session, tenant_id)
    customer = await service.get_by_id(id)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(customer, field, value)

    updated_customer = await service.repo.update(customer)
    return CustomerEnvelope(success=True, data=CustomerResponse.model_validate(updated_customer))
