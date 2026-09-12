"""API integration tests for Lead REST endpoints (TASK-0803, BR-011, BR-012)."""

import uuid

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient

from app.api.deps import CurrentUser, get_current_user
from app.core.database import check_database_health, get_db_session
from app.models.customer import Customer
from app.models.lead import LeadPriority, LeadStatus
from app.models.tenant import Tenant
from app.models.user import UserRole


@pytest.fixture
def test_tenant_id() -> uuid.UUID:
    """Return a consistent tenant UUID for API testing."""
    return uuid.uuid4()


@pytest.fixture
def test_user_id() -> uuid.UUID:
    """Return a consistent sales agent user UUID for API testing."""
    return uuid.uuid4()


@pytest.fixture
def sales_agent_user(test_user_id: uuid.UUID, test_tenant_id: uuid.UUID) -> CurrentUser:
    """Return CurrentUser authenticated context with SalesAgent role."""
    return CurrentUser(
        user_id=test_user_id,
        tenant_id=test_tenant_id,
        role=UserRole.SALES_AGENT,
        email="agent@leadexport.tn",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_list_leads_unauthenticated_returns_401(app: FastAPI) -> None:
    """Verify unauthenticated GET /api/v1/leads returns HTTP 401 Unauthorized."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/leads")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        json_resp = response.json()
        assert json_resp["status"] == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_lead_api_lifecycle_and_stage_transitions(
    app: FastAPI, sales_agent_user: CurrentUser
) -> None:
    """Verify POST, GET, and PATCH /api/v1/leads lifecycle under DB session context."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    app.dependency_overrides[get_current_user] = lambda: sales_agent_user

    async for session in get_db_session():
        tenant = Tenant(
            id=sales_agent_user.tenant_id,
            name="Beta Lead Export",
            slug=f"beta-lead-{uuid.uuid4().hex[:8]}",
        )
        session.add(tenant)
        await session.flush()

        customer = Customer(
            tenant_id=tenant.id,
            phone_e164=f"+2169{uuid.uuid4().int % 10000000:07d}",
            full_name="Tarek Gharbi",
            tenant=tenant,
        )
        session.add(customer)
        await session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            # 1. Create Lead (POST /api/v1/leads)
            create_payload = {
                "customer_id": str(customer.id),
                "priority": "High",
            }
            create_resp = await client.post("/api/v1/leads", json=create_payload)
            assert create_resp.status_code == status.HTTP_201_CREATED
            lead_data = create_resp.json()["data"]
            assert lead_data["status"] == LeadStatus.NEW.value
            assert lead_data["priority"] == LeadPriority.HIGH.value
            lead_id = lead_data["id"]

            # 2. Get Lead details (GET /api/v1/leads/{id})
            get_resp = await client.get(f"/api/v1/leads/{lead_id}")
            assert get_resp.status_code == status.HTTP_200_OK
            assert get_resp.json()["data"]["id"] == lead_id

            # 3. Patch Lead Stage: New -> Qualified (PATCH /api/v1/leads/{id}/stage)
            patch_resp = await client.patch(
                f"/api/v1/leads/{lead_id}/stage",
                json={"status": "Qualified"},
            )
            assert patch_resp.status_code == status.HTTP_200_OK
            assert patch_resp.json()["data"]["status"] == LeadStatus.QUALIFIED.value

            # 4. List Leads with filter (GET /api/v1/leads?status=Qualified)
            list_resp = await client.get("/api/v1/leads?status=Qualified")
            assert list_resp.status_code == status.HTTP_200_OK
            list_json = list_resp.json()
            assert list_json["success"] is True
            assert len(list_json["data"]) == 1
            assert list_json["data"][0]["id"] == lead_id
        break


@pytest.mark.asyncio
async def test_patch_lead_invalid_stage_jump_returns_422(
    app: FastAPI, sales_agent_user: CurrentUser
) -> None:
    """Verify invalid stage jump (e.g. New to Won) returns HTTP 422 (BR-011)."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    app.dependency_overrides[get_current_user] = lambda: sales_agent_user

    async for session in get_db_session():
        tenant = Tenant(
            id=sales_agent_user.tenant_id,
            name="Gamma Lead Motors",
            slug=f"gamma-lead-{uuid.uuid4().hex[:8]}",
        )
        session.add(tenant)
        await session.flush()

        customer = Customer(
            tenant_id=tenant.id,
            phone_e164=f"+2165{uuid.uuid4().int % 10000000:07d}",
            full_name="Sami Mansour",
            tenant=tenant,
        )
        session.add(customer)
        await session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            # Create Lead (New)
            create_resp = await client.post(
                "/api/v1/leads",
                json={"customer_id": str(customer.id)},
            )
            lead_id = create_resp.json()["data"]["id"]

            # Attempt invalid jump: New -> Won
            invalid_patch = await client.patch(
                f"/api/v1/leads/{lead_id}",
                json={"status": "Won"},
            )
            assert invalid_patch.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            json_resp = invalid_patch.json()
            assert json_resp["status"] == status.HTTP_422_UNPROCESSABLE_ENTITY
            assert "Invalid lead transition from 'New' to 'Won'." in json_resp["detail"]
        break


@pytest.mark.asyncio
async def test_leads_unrecognized_query_param_returns_422(
    app: FastAPI, sales_agent_user: CurrentUser
) -> None:
    """Verify query parameter whitelist violation returns HTTP 422 (ADR 0009)."""
    app.dependency_overrides[get_current_user] = lambda: sales_agent_user
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/leads?unknown_key=xyz")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        json_resp = response.json()
        assert "Unrecognized query parameter" in json_resp["detail"]
