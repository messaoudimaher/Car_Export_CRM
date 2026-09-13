"""Unit and DB integration tests for GDPR Service & API Endpoints (WS-15, TASK-1503)."""

import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.api.v1.router import api_v1_router
from app.core.database import check_database_health, get_db_session
from app.core.errors import ValidationException, register_exception_handlers
from app.models.customer import Customer
from app.models.tenant import Tenant
from app.models.user import UserRole
from app.services.gdpr_service import GDPRService


@pytest.fixture
def test_app() -> FastAPI:
    """Create test FastAPI application with API v1 router attached."""
    app = FastAPI(title="GDPR Test App")
    register_exception_handlers(app)
    app.include_router(api_v1_router)
    return app


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """AsyncMock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_gdpr_service_anonymize_customer_db_persistence() -> None:
    """Integration test verifying customer PII scrubbing, idempotency, and legal hold guards."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database unavailable for integration test.")

    async for session in get_db_session():
        tenant = Tenant(
            name=f"GDPR Org {uuid.uuid4().hex[:6]}",
            slug=f"gdpr-{uuid.uuid4().hex[:6]}",
        )
        session.add(tenant)
        await session.flush()

        customer = Customer(
            tenant_id=tenant.id,
            first_name="Salem",
            last_name="Gharbi",
            full_name="Salem Gharbi",
            phone_e164=f"+21695{uuid.uuid4().int % 1000000:06d}",
            email="salem.gharbi@example.com",
            notes="Wants Golf 8 quote with FCR privilege",
            is_anonymized=False,
            legal_hold=False,
        )
        session.add(customer)
        await session.commit()

        service = GDPRService(session=session)
        admin_user_id = uuid.uuid4()

        # 1. Anonymize customer PII
        result = await service.anonymize_customer(
            tenant_id=tenant.id,
            customer_id=customer.id,
            requester_user_id=admin_user_id,
            reason="Customer formal erasure request under GDPR Art. 17",
        )

        assert result["is_anonymized"] is True
        assert result["customer_id"] == customer.id

        # Verify scrubbed database attributes
        anonymized_cust = await session.get(Customer, customer.id)
        assert anonymized_cust is not None
        assert anonymized_cust.is_anonymized is True
        assert anonymized_cust.first_name == "Anonymized"
        assert anonymized_cust.email is None
        assert anonymized_cust.notes is None
        assert customer.id.hex[:8] in anonymized_cust.phone_e164

        # 2. Idempotency test: second invocation returns cleanly
        result_idempotent = await service.anonymize_customer(
            tenant_id=tenant.id,
            customer_id=customer.id,
            requester_user_id=admin_user_id,
        )
        assert result_idempotent["is_anonymized"] is True

        # 3. Legal hold guard test
        customer_legal = Customer(
            tenant_id=tenant.id,
            first_name="Kais",
            last_name="Saied",
            phone_e164=f"+21694{uuid.uuid4().int % 1000000:06d}",
            legal_hold=True,
        )
        session.add(customer_legal)
        await session.commit()

        with pytest.raises(ValidationException, match="active legal retention hold"):
            await service.anonymize_customer(
                tenant_id=tenant.id,
                customer_id=customer_legal.id,
                requester_user_id=admin_user_id,
            )

        break


@pytest.mark.asyncio
async def test_gdpr_anonymize_endpoint_rbac_and_flow(
    test_app: FastAPI,
    mock_db_session: AsyncMock,
) -> None:
    """Verify POST /api/v1/customers/{id}/anonymize endpoint RBAC and execution."""
    tenant_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    customer_id = uuid.uuid4()

    mock_admin = CurrentUser(
        user_id=admin_id,
        tenant_id=tenant_id,
        role=UserRole.TENANT_ADMIN.value,
        email="admin@test.com",
        is_active=True,
    )

    mock_service_res = {
        "customer_id": customer_id,
        "tenant_id": tenant_id,
        "is_anonymized": True,
        "anonymized_at": "2026-09-13T17:10:00Z",
        "documents_purged_count": 2,
        "message": "Successfully anonymized customer PII.",
    }

    mock_service_instance = AsyncMock()
    mock_service_instance.anonymize_customer.return_value = mock_service_res

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield mock_db_session

    test_app.dependency_overrides[get_db_session] = override_db
    test_app.dependency_overrides[get_current_user] = lambda: mock_admin

    with patch("app.api.v1.gdpr.GDPRService", return_value=mock_service_instance):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=test_app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/customers/{customer_id}/anonymize",
                json={"reason": "User right to erasure"},
                headers={"Authorization": "Bearer mock_token"},
            )

    test_app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["is_anonymized"] is True
    assert data["customer_id"] == str(customer_id)
