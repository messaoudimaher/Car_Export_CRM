"""Integration & unit tests for VehicleRequest declarative model and FCR compliance (BR-004)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import Index

from app.core.database import check_database_health, get_db_session
from app.models.customer import Customer
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.vehicle_request import VehicleRequest, check_fcr_compliance


def test_check_fcr_compliance_logic() -> None:
    """Verify check_fcr_compliance properly enforces 5-year FCR age limit (BR-004)."""
    # Reference year 2026 -> min allowed year is 2021 (2026 - 5)

    # Compliant scenarios (manufacture year >= 2021)
    assert check_fcr_compliance(min_year=2021, reference_year=2026) is True
    assert check_fcr_compliance(min_year=2022, max_year=2025, reference_year=2026) is True
    assert check_fcr_compliance(min_year=2024, reference_year=2026) is True

    # Non-compliant scenarios (manufacture year < 2021)
    assert check_fcr_compliance(max_year=2020, reference_year=2026) is False
    assert check_fcr_compliance(min_year=2018, max_year=2020, reference_year=2026) is False
    assert check_fcr_compliance(min_year=2019, reference_year=2026) is False

    # Edge cases (None values)
    assert check_fcr_compliance(min_year=None, max_year=None, reference_year=2026) is True


def test_vehicle_request_instantiation_and_defaults() -> None:
    """Verify VehicleRequest model instantiates with UUIDv7 and auto-calculates FCR compliance."""
    tenant_id = uuid.uuid4()
    customer_id = uuid.uuid4()

    # Create request with compliant year specs
    req = VehicleRequest(
        tenant_id=tenant_id,
        customer_id=customer_id,
        make="Volkswagen",
        model="Golf 8",
        min_year=2022,
        fuel_type="Diesel",
        transmission="Automatic",
        budget_eur=Decimal("22000.00"),
    )

    assert req.id is not None
    assert isinstance(req.id, uuid.UUID)
    assert req.id.version == 7
    assert req.tenant_id == tenant_id
    assert req.customer_id == customer_id
    assert req.make == "Volkswagen"
    assert req.model == "Golf 8"
    assert req.min_year == 2022
    assert req.destination_port == "Rades"
    assert req.status == "Pending"
    assert req.is_human_validated is False
    assert req.fcr_compatible is True


def test_vehicle_request_fcr_auto_calculation_non_compliant() -> None:
    """Verify VehicleRequest auto-sets fcr_compatible=False for vehicles older than 5 years."""
    tenant_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    current_year = datetime.now(UTC).year

    # Vehicle model year older than current_year - 5
    req = VehicleRequest(
        tenant_id=tenant_id,
        customer_id=customer_id,
        make="Peugeot",
        model="308",
        max_year=current_year - 6,
    )

    assert req.fcr_compatible is False


def test_vehicle_request_relationships_in_memory() -> None:
    """Verify in-memory relationship navigation between Tenant, Customer, User and Request."""
    tenant = Tenant(name="Delta Export Auto", slug="delta-export")
    customer = Customer(
        tenant_id=tenant.id,
        phone_e164="+21698765432",
        full_name="Sami Khelifi",
        tenant=tenant,
    )
    user = User(
        tenant_id=tenant.id,
        email="agent@deltaexport.tn",
        hashed_password="hashed_pw_secret",  # noqa: S106
        full_name="Agent Sami",
        role=UserRole.SALES_AGENT,
    )

    req = VehicleRequest(
        tenant_id=tenant.id,
        customer_id=customer.id,
        make="BMW",
        model="X5",
        min_year=2023,
        tenant=tenant,
        customer=customer,
        confirmed_by_user=user,
        confirmed_at=datetime.now(UTC),
        is_human_validated=True,
    )

    assert req.tenant is tenant
    assert req.customer is customer
    assert req.confirmed_by_user is user
    assert req in tenant.vehicle_requests
    assert req in customer.vehicle_requests


def test_vehicle_request_table_indexes() -> None:
    """Verify VehicleRequest __table_args__ includes expected indexes."""
    table_args = VehicleRequest.__table_args__
    indexes = [arg for arg in table_args if isinstance(arg, Index)]
    index_names = [idx.name for idx in indexes]

    assert "ix_vehicle_requests_tenant_id" in index_names
    assert "ix_vehicle_requests_customer_id" in index_names
    assert "ix_vehicle_requests_make_model" in index_names
    assert "ix_vehicle_requests_created_at" in index_names


@pytest.mark.asyncio
async def test_vehicle_request_db_persistence() -> None:
    """Verify AsyncSession DB persistence, query retrieval, and foreign key integrity.

    Note: Skips if PostgreSQL service is not reachable.
    """
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    async for session in get_db_session():
        tenant = Tenant(name="Epsilon Auto Export", slug=f"epsilon-auto-{uuid.uuid4().hex[:8]}")
        session.add(tenant)
        await session.flush()

        customer = Customer(
            tenant_id=tenant.id,
            phone_e164=f"+2165{uuid.uuid4().int % 10000000:07d}",
            full_name="Youssef Ben Ammar",
            tenant=tenant,
        )
        session.add(customer)
        await session.flush()

        sales_user = User(
            tenant_id=tenant.id,
            email=f"sales_{uuid.uuid4().hex[:6]}@epsilon.tn",
            hashed_password="password_hash_123",  # noqa: S106
            full_name="Sales Rep",
            role=UserRole.SALES_AGENT,
        )
        session.add(sales_user)
        await session.flush()

        req = VehicleRequest(
            tenant_id=tenant.id,
            customer_id=customer.id,
            make="Audi",
            model="A4",
            min_year=2022,
            max_year=2024,
            fuel_type="Diesel",
            transmission="Automatic",
            max_mileage_km=80000,
            budget_eur=Decimal("25000.00"),
            destination_port="Rades",
            status="Pending",
            is_human_validated=True,
            confirmed_by_user_id=sales_user.id,
            confirmed_at=datetime.now(UTC),
        )
        session.add(req)
        await session.commit()

        # Retrieve from DB and verify attributes
        retrieved = await session.get(VehicleRequest, req.id)
        assert retrieved is not None
        assert retrieved.make == "Audi"
        assert retrieved.model == "A4"
        assert retrieved.min_year == 2022
        assert retrieved.max_year == 2024
        assert retrieved.budget_eur == Decimal("25000.00")
        assert retrieved.fcr_compatible is True
        assert retrieved.is_human_validated is True
        assert retrieved.confirmed_by_user_id == sales_user.id
        break
