"""Authentication & Dev Session Management Endpoints (FR-AUTH-001, FR-AUTH-002)."""

from uuid import UUID
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import create_access_token, hash_password, verify_password
from app.core.errors import UnauthorizedException
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.utils.uuid import generate_uuidv7

router = APIRouter(prefix="/auth", tags=["Authentication"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    tenant_id: str
    role: str
    email: str


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/dev-token", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def get_or_create_dev_token(
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Issue a valid development JWT Bearer token, auto-provisioning a demo tenant and sales agent if needed."""
    # Find existing demo tenant or create one
    stmt_tenant = select(Tenant).limit(1)
    tenant = (await session.scalars(stmt_tenant)).first()
    if not tenant:
        tenant = Tenant(
            id=generate_uuidv7(),
            name="Car Export Demo Org",
            slug="demo-org",
            is_active=True,
        )
        session.add(tenant)
        await session.flush()

    # Find existing sales user or create demo agent
    stmt_user = select(User).where(User.tenant_id == tenant.id).limit(1)
    user = (await session.scalars(stmt_user)).first()
    if not user:
        user = User(
            id=generate_uuidv7(),
            tenant_id=tenant.id,
            email="agent@carexport.tn",
            full_name="Sami Khedira",
            role=UserRole.SALES_AGENT,
            hashed_password=hash_password("DemoPassword123!"),
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    token = create_access_token(
        subject=user.id,
        tenant_id=tenant.id,
        role=user.role if isinstance(user.role, str) else user.role.value,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=str(user.id),
        tenant_id=str(tenant.id),
        role=user.role if isinstance(user.role, str) else user.role.value,
        email=user.email,
    )
