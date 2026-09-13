"""Follow-Up Task REST API v1 Endpoints (WS-14, TASK-1402, SEC-007)."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_tenant_id, get_current_user
from app.core.database import get_db_session
from app.schemas.followup import FollowUpCreate, FollowUpRead, FollowUpUpdate
from app.services.followup_service import FollowUpService

router = APIRouter(prefix="/followups", tags=["Follow-Ups"])


@router.post(
    "",
    response_model=FollowUpRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_followup(
    request: FollowUpCreate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> FollowUpRead:
    """Create a scheduled sales follow-up task under tenant context (SEC-007)."""
    service = FollowUpService(session=session)
    followup = await service.create_followup(tenant_id=tenant_id, payload=request)
    return FollowUpRead.model_validate(followup)


@router.get(
    "",
    response_model=list[FollowUpRead],
    status_code=status.HTTP_200_OK,
)
async def list_followups(
    lead_id: UUID | None = Query(None, description="Filter by lead UUID"),
    assigned_user_id: UUID | None = Query(None, description="Filter by assigned user UUID"),
    followup_status: str | None = Query(None, alias="status", description="Filter by status"),
    due_before: datetime | None = Query(None, description="Filter tasks due before timestamp"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Record offset"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> list[FollowUpRead]:
    """List tenant follow-up tasks with optional filters under tenant scope (SEC-007)."""
    service = FollowUpService(session=session)
    records = await service.list_followups(
        tenant_id=tenant_id,
        lead_id=lead_id,
        assigned_user_id=assigned_user_id,
        status=followup_status,
        due_before=due_before,
        limit=limit,
        offset=offset,
    )
    return [FollowUpRead.model_validate(r) for r in records]


@router.get(
    "/{followup_id}",
    response_model=FollowUpRead,
    status_code=status.HTTP_200_OK,
)
async def get_followup(
    followup_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> FollowUpRead:
    """Retrieve specific follow-up task details by UUID under tenant scope."""
    service = FollowUpService(session=session)
    followup = await service.get_followup_by_id(tenant_id=tenant_id, followup_id=followup_id)
    return FollowUpRead.model_validate(followup)


@router.patch(
    "/{followup_id}",
    response_model=FollowUpRead,
    status_code=status.HTTP_200_OK,
)
async def update_followup(
    followup_id: UUID,
    request: FollowUpUpdate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> FollowUpRead:
    """Update follow-up task details under tenant scope."""
    service = FollowUpService(session=session)
    followup = await service.update_followup(
        tenant_id=tenant_id, followup_id=followup_id, payload=request
    )
    return FollowUpRead.model_validate(followup)


@router.post(
    "/{followup_id}/complete",
    response_model=FollowUpRead,
    status_code=status.HTTP_200_OK,
)
async def complete_followup(
    followup_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> FollowUpRead:
    """Mark follow-up task as Completed (SEC-007)."""
    service = FollowUpService(session=session)
    followup = await service.complete_followup(tenant_id=tenant_id, followup_id=followup_id)
    return FollowUpRead.model_validate(followup)


@router.post(
    "/{followup_id}/cancel",
    response_model=FollowUpRead,
    status_code=status.HTTP_200_OK,
)
async def cancel_followup(
    followup_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> FollowUpRead:
    """Mark follow-up task as Cancelled (SEC-007)."""
    service = FollowUpService(session=session)
    followup = await service.cancel_followup(tenant_id=tenant_id, followup_id=followup_id)
    return FollowUpRead.model_validate(followup)
