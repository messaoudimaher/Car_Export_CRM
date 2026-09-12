"""Integration & unit tests for Vehicle catalog model and VAT regime fields (BR-005)."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import CheckConstraint, Index

from app.core.database import check_database_health, get_db_session
from app.models.tenant import Tenant
from app.models.vehicle import VATRegime, Vehicle, VehicleStatus


def test_vat_regime_enum_values() -> None:
    """Verify VATRegime enum contains exact Netto/Brutto strings required by BR-005."""
    assert VATRegime.NETTO_EXPORT.value == "Netto_Export"
    assert VATRegime.BRUTTO_MARGIN.value == "Brutto_Margin"


def test_vehicle_status_enum_values() -> None:
    """Verify VehicleStatus enum contains expected stock status strings."""
    assert VehicleStatus.AVAILABLE.value == "Available"
    assert VehicleStatus.RESERVED.value == "Reserved"
    assert VehicleStatus.SOLD.value == "Sold"
    assert VehicleStatus.ARCHIVED.value == "Archived"


def test_vehicle_model_instantiation_and_defaults() -> None:
    """Verify Vehicle model instantiates with UUIDv7 PK and default VAT regime."""
    tenant_id = uuid.uuid4()
    v = Vehicle(
        tenant_id=tenant_id,
        make="BMW",
        model="X5 xDrive30d",
        first_registration_year=2023,
        mileage_km=45000,
        fuel_type="Diesel",
        transmission="Automatic",
        purchase_price_eur=Decimal("42000.00"),
    )

    assert v.id is not None
    assert isinstance(v.id, uuid.UUID)
    assert v.id.version == 7
    assert v.tenant_id == tenant_id
    assert v.make == "BMW"
    assert v.model == "X5 xDrive30d"
    assert v.first_registration_year == 2023
    assert v.mileage_km == 45000
    assert v.purchase_price_eur == Decimal("42000.00")
    assert v.vat_regime == VATRegime.NETTO_EXPORT.value
    assert v.status == VehicleStatus.AVAILABLE.value
    assert v.vin is None
    assert v.supplier_name is None
    assert v.supplier_location is None


def test_vehicle_relationships_in_memory() -> None:
    """Verify in-memory relationship navigation between Tenant and Vehicle models."""
    tenant = Tenant(name="Munich Motors Export", slug="munich-motors")
    v = Vehicle(
        tenant_id=tenant.id,
        make="Audi",
        model="A6 Avant",
        first_registration_year=2022,
        mileage_km=55000,
        fuel_type="Diesel",
        transmission="Automatic",
        purchase_price_eur=Decimal("31500.00"),
        vat_regime=VATRegime.BRUTTO_MARGIN.value,
        tenant=tenant,
    )

    assert v.tenant is tenant
    assert v in tenant.vehicles


def test_vehicle_table_indexes_and_constraints() -> None:
    """Verify Vehicle __table_args__ defines check constraints and indexes."""
    table_args = Vehicle.__table_args__
    constraints = [arg for arg in table_args if isinstance(arg, CheckConstraint)]
    indexes = [arg for arg in table_args if isinstance(arg, Index)]

    constraint_names = [c.name for c in constraints]
    assert "ck_vehicles_vat_regime" in constraint_names
    assert "ck_vehicles_status" in constraint_names

    index_names = [idx.name for idx in indexes]
    assert "ix_vehicles_tenant_id" in index_names
    assert "ix_vehicles_make_model" in index_names
    assert "ix_vehicles_tenant_status" in index_names
    assert "ix_vehicles_vin" in index_names
    assert "ix_vehicles_created_at" in index_names


@pytest.mark.asyncio
async def test_vehicle_db_persistence() -> None:
    """Verify AsyncSession DB persistence, exact decimal price, and query retrieval."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    async for session in get_db_session():
        tenant = Tenant(
            name="Stuttgart Auto Sarl",
            slug=f"stuttgart-{uuid.uuid4().hex[:8]}",
        )
        session.add(tenant)
        await session.flush()

        v = Vehicle(
            tenant_id=tenant.id,
            vin="WBA1234567890ABCD",
            make="Mercedes-Benz",
            model="E220d",
            first_registration_year=2022,
            mileage_km=62000,
            fuel_type="Diesel",
            transmission="Automatic",
            purchase_price_eur=Decimal("28500.00"),
            vat_regime=VATRegime.NETTO_EXPORT.value,
            supplier_name="Autohaus Stuttgart",
            supplier_location="Stuttgart, Germany",
        )
        session.add(v)
        await session.commit()

        # Retrieve and verify exact numeric precision
        retrieved = await session.get(Vehicle, v.id)
        assert retrieved is not None
        assert retrieved.make == "Mercedes-Benz"
        assert retrieved.model == "E220d"
        assert retrieved.purchase_price_eur == Decimal("28500.00")
        assert retrieved.vat_regime == VATRegime.NETTO_EXPORT.value
        assert retrieved.status == VehicleStatus.AVAILABLE.value
        break
