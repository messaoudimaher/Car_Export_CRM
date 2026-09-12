"""API Integration tests for Quotation REST Endpoints (WS-10, TASK-1004)."""

import uuid
from collections.abc import AsyncGenerator
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db_session
from app.core.security import create_access_token
from app.main import create_app
from app.models.lead import Lead, LeadStatus
from app.models.quotation import Quotation, QuotationApprovalStatus, QuotationStatus
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.vehicle import VATRegime, Vehicle


def create_quotation_test_app(mock_session: AsyncMock) -> FastAPI:
    """Create FastAPI application bound to mock DB session for Quotation API tests."""
    app = create_app()

    async def override_get_db_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    return app


@pytest.mark.asyncio
async def test_create_quotation_endpoint_success() -> None:
    """Verify POST /api/v1/quotes calculates deterministic math and creates quote draft."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    app = create_quotation_test_app(mock_session)

    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    lead_id = uuid.uuid4()
    vehicle_id = uuid.uuid4()

    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="agent@export.de",
        password_hash="pwd_hash",  # noqa: S106
        role=UserRole.SALES_AGENT.value,
        is_active=True,
    )
    tenant = Tenant(id=tenant_id, name="Test Tenant", slug="test-tenant")
    lead = Lead(id=lead_id, tenant_id=tenant_id, status=LeadStatus.QUALIFIED.value)
    vehicle = Vehicle(
        id=vehicle_id,
        tenant_id=tenant_id,
        make="BMW",
        model="Series 3",
        first_registration_year=2022,
        mileage_km=30000,
        fuel_type="Diesel",
        transmission="Automatic",
        purchase_price_eur=Decimal("25000.00"),
        vat_regime=VATRegime.NETTO_EXPORT.value,
    )

    def mock_get(model: object, entity_id: object) -> object:
        if model is User and entity_id == user_id:
            return user
        if model is Tenant and entity_id == tenant_id:
            return tenant
        return None

    mock_session.get.side_effect = mock_get

    def mock_execute(stmt: object, *args: object, **kwargs: object) -> MagicMock:
        res = MagicMock()
        stmt_str = str(stmt)
        if "FROM leads" in stmt_str:
            res.scalar_one_or_none.return_value = lead
        elif "FROM vehicles" in stmt_str:
            res.scalar_one_or_none.return_value = vehicle
        else:
            res.scalar_one_or_none.return_value = None
        return res

    mock_session.execute.side_effect = mock_execute

    token = create_access_token(user_id, tenant_id, role=UserRole.SALES_AGENT.value)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "lead_id": str(lead_id),
            "vehicle_id": str(vehicle_id),
            "vat_regime": "Netto_Export",
            "vehicle_price_cents": 2500000,
            "shipping_fee_cents": 100000,
            "items": [
                {"description": "Export Documentation", "unit_price_cents": 20000, "quantity": 1}
            ],
            "discount_percentage": "2.00",
        }

        response = await client.post(
            "/api/v1/quotes",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["vat_regime"] == "Netto_Export"
        assert data["status"] == "Draft"
        assert data["approval_status"] == "Auto_Approved"
        assert data["total_price_cents"] == 2567600
        assert data["vehicle_price_eur"] == "25000.00"
        assert data["shipping_fee_eur"] == "1000.00"


@pytest.mark.asyncio
async def test_approve_quotation_endpoint_tenant_admin_only() -> None:
    """Verify POST /api/v1/quotes/{id}/approve enforces TenantAdmin role constraint (BR-015)."""
    mock_session = AsyncMock()
    app = create_quotation_test_app(mock_session)

    user_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    quote_id = uuid.uuid4()

    sales_user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="agent@export.de",
        password_hash="pwd_hash",  # noqa: S106
        role=UserRole.SALES_AGENT.value,
        is_active=True,
    )
    admin_user = User(
        id=admin_id,
        tenant_id=tenant_id,
        email="admin@export.de",
        password_hash="pwd_hash",  # noqa: S106
        role=UserRole.TENANT_ADMIN.value,
        is_active=True,
    )

    pending_quote = Quotation(
        id=quote_id,
        tenant_id=tenant_id,
        lead_id=uuid.uuid4(),
        quote_number="QT-2026-99999",
        vat_regime=VATRegime.NETTO_EXPORT.value,
        vehicle_price_cents=3000000,
        shipping_fee_cents=100000,
        customs_estimate_tnd=Decimal("4500.000"),
        total_price_cents=2790000,
        status=QuotationStatus.PENDING_APPROVAL.value,
        approval_status=QuotationApprovalStatus.PENDING_APPROVAL.value,
    )

    def mock_get(model: object, entity_id: object) -> object:
        if model is User and entity_id == user_id:
            return sales_user
        if model is User and entity_id == admin_id:
            return admin_user
        return None

    mock_session.get.side_effect = mock_get

    def mock_execute(stmt: object, *args: object, **kwargs: object) -> MagicMock:
        res = MagicMock()
        stmt_str = str(stmt)
        if "FROM quotations" in stmt_str:
            res.scalar_one_or_none.return_value = pending_quote
        else:
            res.scalar_one_or_none.return_value = None
        return res

    mock_session.execute.side_effect = mock_execute

    sales_token = create_access_token(user_id, tenant_id, role=UserRole.SALES_AGENT.value)
    admin_token = create_access_token(admin_id, tenant_id, role=UserRole.TENANT_ADMIN.value)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Sales Agent attempt returns 403 Forbidden
        response_agent = await client.post(
            f"/api/v1/quotes/{quote_id}/approve",
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert response_agent.status_code == 403

        # 2. Tenant Admin approval succeeds
        response_admin = await client.post(
            f"/api/v1/quotes/{quote_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response_admin.status_code == 200
        data = response_admin.json()
        assert data["approval_status"] == "Approved"
        assert data["status"] == "Approved"


@pytest.mark.asyncio
async def test_send_unapproved_quotation_blocks_dispatch() -> None:
    """Verify POST /api/v1/quotes/{id}/send blocks dispatch for pending quotes (BR-015)."""
    mock_session = AsyncMock()
    app = create_quotation_test_app(mock_session)

    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    quote_id = uuid.uuid4()

    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="agent@export.de",
        password_hash="pwd_hash",  # noqa: S106
        role=UserRole.SALES_AGENT.value,
        is_active=True,
    )
    pending_quote = Quotation(
        id=quote_id,
        tenant_id=tenant_id,
        lead_id=uuid.uuid4(),
        quote_number="QT-2026-PENDING",
        vat_regime=VATRegime.NETTO_EXPORT.value,
        vehicle_price_cents=3000000,
        shipping_fee_cents=100000,
        customs_estimate_tnd=Decimal("4500.000"),
        total_price_cents=2790000,
        status=QuotationStatus.PENDING_APPROVAL.value,
        approval_status=QuotationApprovalStatus.PENDING_APPROVAL.value,
    )

    mock_session.get.return_value = user

    def mock_execute(stmt: object, *args: object, **kwargs: object) -> MagicMock:
        res = MagicMock()
        stmt_str = str(stmt)
        if "FROM quotations" in stmt_str:
            res.scalar_one_or_none.return_value = pending_quote
        else:
            res.scalar_one_or_none.return_value = None
        return res

    mock_session.execute.side_effect = mock_execute

    token = create_access_token(user_id, tenant_id, role=UserRole.SALES_AGENT.value)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/quotes/{quote_id}/send",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        error = response.json()
        assert "pending manager discount approval" in error["detail"]
