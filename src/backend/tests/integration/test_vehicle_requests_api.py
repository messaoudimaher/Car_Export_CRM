"""API integration tests for Vehicle Requests REST endpoints (TASK-0803, BR-004)."""

import uuid

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient

from app.api.deps import CurrentUser, get_current_user
from app.core.database import check_database_health, get_db_session
from app.models.customer import Customer
from app.models.tenant import Tenant
from app.models.user import UserRole


@pytest.fixture
def test_tenant_id() -> uuid.UUID:
    """Return a consistent tenant UUID for API testing."""
    return uuid.uuid4()


@pytest.fixture
def test_user_id() -> uuid.UUID:
    """Return a consistent sales rep user UUID for API testing."""
    return uuid.uuid4()


@pytest.fixture
def sales_agent_user(test_user_id: uuid.UUID, test_tenant_id: uuid.UUID) -> CurrentUser:
    """Return CurrentUser authenticated context with SalesAgent role."""
    return CurrentUser(
        user_id=test_user_id,
        tenant_id=test_tenant_id,
        role=UserRole.SALES_AGENT,
        email="agent@vehicleexport.tn",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_list_vehicle_requests_unauthenticated_returns_401(app: FastAPI) -> None:
    """Verify unauthenticated GET /api/v1/vehicle-requests returns HTTP 401 Unauthorized."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/vehicle-requests")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        json_resp = response.json()
        assert json_resp["status"] == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_create_and_get_vehicle_request_api_flow(
    app: FastAPI, sales_agent_user: CurrentUser
) -> None:
    """Verify POST and GET /api/v1/vehicle-requests under DB session lifecycle."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    app.dependency_overrides[get_current_user] = lambda: sales_agent_user

    async for session in get_db_session():
        # Setup tenant & customer record
        tenant = Tenant(
            id=sales_agent_user.tenant_id,
            name="Alpha Export Sarl",
            slug=f"alpha-{uuid.uuid4().hex[:8]}",
        )
        session.add(tenant)
        await session.flush()

        customer = Customer(
            tenant_id=tenant.id,
            phone_e164=f"+2169{uuid.uuid4().int % 10000000:07d}",
            full_name="Bilel Sassi",
            tenant=tenant,
        )
        session.add(customer)
        await session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            # 1. Create Vehicle Request (POST)
            create_payload = {
                "customer_id": str(customer.id),
                "make": "Volkswagen",
                "model": "Golf 8",
                "min_year": 2022,
                "fuel_type": "Diesel",
                "transmission": "Automatic",
                "budget_eur": "20000.00",
                "destination_port": "Rades",
            }
            create_resp = await client.post("/api/v1/vehicle-requests", json=create_payload)
            assert create_resp.status_code == status.HTTP_201_CREATED
            data = create_resp.json()["data"]
            assert data["make"] == "Volkswagen"
            assert data["model"] == "Golf 8"
            assert data["fcr_compatible"] is True  # 2022 >= 2021 (BR-004)
            vreq_id = data["id"]

            # 2. Get Vehicle Request by ID (GET)
            get_resp = await client.get(f"/api/v1/vehicle-requests/{vreq_id}")
            assert get_resp.status_code == status.HTTP_200_OK
            get_data = get_resp.json()["data"]
            assert get_data["id"] == vreq_id
            assert get_data["customer_id"] == str(customer.id)

            # 3. List Vehicle Requests with filters (GET)
            list_resp = await client.get("/api/v1/vehicle-requests?make=Volkswagen")
            assert list_resp.status_code == status.HTTP_200_OK
            list_data = list_resp.json()
            assert list_data["success"] is True
            assert len(list_data["data"]) == 1
            assert list_data["meta"]["total"] == 1
        break


@pytest.mark.asyncio
async def test_vehicle_request_unrecognized_query_param_returns_422(
    app: FastAPI, sales_agent_user: CurrentUser
) -> None:
    """Verify query parameter whitelist violation returns HTTP 422 (ADR 0009)."""
    app.dependency_overrides[get_current_user] = lambda: sales_agent_user
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/vehicle-requests?invalid_param=123")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        json_resp = response.json()
        assert "Unrecognized query parameter" in json_resp["detail"]
