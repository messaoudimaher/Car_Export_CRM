"""API integration tests for Vehicle Catalog REST endpoints (TASK-0902, BR-005)."""

import uuid

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient

from app.api.deps import CurrentUser, get_current_user
from app.core.database import check_database_health, get_db_session
from app.models.tenant import Tenant
from app.models.user import UserRole
from app.models.vehicle import VATRegime


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
        email="logistics@vehicletn.com",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_list_vehicles_unauthenticated_returns_401(app: FastAPI) -> None:
    """Verify unauthenticated GET /api/v1/vehicles returns HTTP 401 Unauthorized."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/vehicles")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        json_resp = response.json()
        assert json_resp["status"] == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_vehicle_api_crud_and_search_filtering(
    app: FastAPI, sales_agent_user: CurrentUser
) -> None:
    """Verify POST, GET, and filter search on /api/v1/vehicles under DB session context."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    app.dependency_overrides[get_current_user] = lambda: sales_agent_user

    async for session in get_db_session():
        tenant = Tenant(
            id=sales_agent_user.tenant_id,
            name="Epsilon Stock GmbH",
            slug=f"epsilon-stock-{uuid.uuid4().hex[:8]}",
        )
        session.add(tenant)
        await session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            # 1. Create Vehicle Stock Record (POST /api/v1/vehicles)
            create_payload = {
                "vin": "WBA33AG09NFP12345",
                "make": "BMW",
                "model": "320d Touring",
                "first_registration_year": 2023,
                "mileage_km": 35000,
                "fuel_type": "Diesel",
                "transmission": "Automatic",
                "purchase_price_eur": "29800.00",
                "vat_regime": "Netto_Export",
                "supplier_name": "BMW Niederlassung München",
                "supplier_location": "Munich, Germany",
                "status": "Available",
            }
            create_resp = await client.post("/api/v1/vehicles", json=create_payload)
            assert create_resp.status_code == status.HTTP_201_CREATED
            veh_data = create_resp.json()["data"]
            assert veh_data["make"] == "BMW"
            assert veh_data["model"] == "320d Touring"
            assert veh_data["vat_regime"] == VATRegime.NETTO_EXPORT.value
            assert veh_data["purchase_price_eur"] == "29800.00"
            veh_id = veh_data["id"]

            # 2. Fetch Vehicle by ID (GET /api/v1/vehicles/{id})
            get_resp = await client.get(f"/api/v1/vehicles/{veh_id}")
            assert get_resp.status_code == status.HTTP_200_OK
            assert get_resp.json()["data"]["id"] == veh_id

            # 3. Filter Vehicles by make, min_year & max_price_eur
            filter_url = "/api/v1/vehicles?make=BMW&min_year=2022&max_price_eur=30000"
            list_resp = await client.get(filter_url)
            assert list_resp.status_code == status.HTTP_200_OK
            list_data = list_resp.json()
            assert list_data["success"] is True
            assert len(list_data["data"]) == 1
            assert list_data["data"][0]["id"] == veh_id
            assert list_data["meta"]["total"] == 1
        break


@pytest.mark.asyncio
async def test_vehicles_unrecognized_query_param_returns_422(
    app: FastAPI, sales_agent_user: CurrentUser
) -> None:
    """Verify query parameter whitelist violation returns HTTP 422 (ADR 0009)."""
    app.dependency_overrides[get_current_user] = lambda: sales_agent_user
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/vehicles?invalid_key=xyz")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        json_resp = response.json()
        assert "Unrecognized query parameter" in json_resp["detail"]
