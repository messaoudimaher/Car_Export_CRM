"""GDPR Right-to-Erasure & Legal Hold REST API Endpoints (WS-15, TASK-1503)."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentUser,
    get_current_tenant_id,
    require_roles,
)
from app.core.database import get_db_session
from app.models.user import UserRole
from app.schemas.gdpr import (
    GDPRAnonymizeRequest,
    GDPRAnonymizeResponse,
    GDPRLegalHoldRequest,
)
from app.services.gdpr_service import GDPRService

router = APIRouter(prefix="/customers", tags=["gdpr"])


@router.post(
    "/{customer_id}/anonymize",
    response_model=GDPRAnonymizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Anonymize Customer PII under GDPR Right to Erasure",
)
async def anonymize_customer_pii(
    customer_id: UUID,
    payload: GDPRAnonymizeRequest = GDPRAnonymizeRequest(),
    tenant_id: UUID = Depends(get_current_tenant_id),
    current_user: CurrentUser = Depends(require_roles(UserRole.TENANT_ADMIN, UserRole.SUPER_ADMIN)),
    session: AsyncSession = Depends(get_db_session),
) -> GDPRAnonymizeResponse:
    """Scrub customer PII and purge linked documents while keeping financial records intact."""
    service = GDPRService(session=session)
    res = await service.anonymize_customer(
        tenant_id=tenant_id,
        customer_id=customer_id,
        requester_user_id=current_user.user_id,
        reason=payload.reason,
    )
    return GDPRAnonymizeResponse.model_validate(res)


@router.put(
    "/{customer_id}/legal-hold",
    status_code=status.HTTP_200_OK,
    summary="Set or Release Legal Retention Hold on Customer Record",
)
async def set_customer_legal_hold(
    customer_id: UUID,
    payload: GDPRLegalHoldRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    _: CurrentUser = Depends(require_roles(UserRole.TENANT_ADMIN, UserRole.SUPER_ADMIN)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Enforce or release legal retention hold blocking GDPR automated erasure."""
    service = GDPRService(session=session)
    customer = await service.set_legal_hold(
        tenant_id=tenant_id,
        customer_id=customer_id,
        legal_hold=payload.legal_hold,
    )
    return {
        "customer_id": customer.id,
        "tenant_id": customer.tenant_id,
        "legal_hold": customer.legal_hold,
        "message": f"Legal hold set to {customer.legal_hold}.",
    }
