"""Integration & unit tests for Quotation and QuotationItem models (WS-10, TASK-1001)."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import CheckConstraint, Index

from app.core.database import check_database_health, get_db_session
from app.models.customer import Customer
from app.models.lead import Lead, LeadStatus
from app.models.quotation import Quotation, QuotationApprovalStatus, QuotationItem, QuotationStatus
from app.models.tenant import Tenant
from app.models.vehicle import VATRegime, Vehicle, VehicleStatus


def test_quotation_enums() -> None:
    """Verify QuotationStatus and QuotationApprovalStatus enum values."""
    assert QuotationStatus.DRAFT.value == "Draft"
    assert QuotationStatus.PENDING_APPROVAL.value == "Pending_Approval"
    assert QuotationStatus.APPROVED.value == "Approved"
    assert QuotationStatus.SENT.value == "Sent"
    assert QuotationStatus.ACCEPTED.value == "Accepted"
    assert QuotationStatus.REJECTED.value == "Rejected"
    assert QuotationStatus.EXPIRED.value == "Expired"

    assert QuotationApprovalStatus.AUTO_APPROVED.value == "Auto_Approved"
    assert QuotationApprovalStatus.PENDING_APPROVAL.value == "Pending_Approval"
    assert QuotationApprovalStatus.APPROVED.value == "Approved"
    assert QuotationApprovalStatus.REJECTED.value == "Rejected"


def test_quotation_instantiation_and_cent_pricing_defaults() -> None:
    """Verify Quotation and QuotationItem model instantiation with integer cent pricing math."""
    tenant_id = uuid.uuid4()
    lead_id = uuid.uuid4()
    vehicle_id = uuid.uuid4()

    q = Quotation(
        tenant_id=tenant_id,
        lead_id=lead_id,
        vehicle_id=vehicle_id,
        quote_number="QT-2026-00001",
        vat_regime=VATRegime.NETTO_EXPORT.value,
        vehicle_price_cents=3500000,  # €35,000.00 in integer cents
        shipping_fee_cents=120000,  # €1,200.00 in integer cents
        customs_estimate_tnd=Decimal("14250.500"),  # TND 14,250.500
        discount_cents=100000,  # €1,000.00 discount
        discount_percentage=Decimal("2.86"),
        total_price_cents=3520000,  # €35,200.00 total
    )

    assert q.id is not None
    assert isinstance(q.id, uuid.UUID)
    assert q.id.version == 7
    assert q.tenant_id == tenant_id
    assert q.lead_id == lead_id
    assert q.vehicle_id == vehicle_id
    assert q.quote_number == "QT-2026-00001"
    assert q.vat_regime == VATRegime.NETTO_EXPORT.value
    assert q.vehicle_price_cents == 3500000
    assert q.shipping_fee_cents == 120000
    assert q.customs_estimate_tnd == Decimal("14250.500")
    assert q.discount_cents == 100000
    assert q.discount_percentage == Decimal("2.86")
    assert q.total_price_cents == 3520000
    assert q.status == QuotationStatus.DRAFT.value
    assert q.approval_status == QuotationApprovalStatus.AUTO_APPROVED.value
    assert q.disclaimer_text is None
    assert q.pdf_s3_key is None

    # QuotationItem instantiation
    item = QuotationItem(
        quotation_id=q.id,
        description="Homologation & FCR Documentation",
        unit_price_cents=30000,  # €300.00
        quantity=1,
        total_price_cents=30000,
    )

    assert item.id is not None
    assert isinstance(item.id, uuid.UUID)
    assert item.id.version == 7
    assert item.quotation_id == q.id
    assert item.description == "Homologation & FCR Documentation"
    assert item.unit_price_cents == 30000
    assert item.quantity == 1
    assert item.total_price_cents == 30000


def test_quotation_relationships_in_memory() -> None:
    """Verify in-memory navigation between Tenant, Lead, Vehicle, and Quotation."""
    tenant = Tenant(name="Sfax Auto Export", slug="sfax-auto")
    customer = Customer(tenant_id=tenant.id, phone="+21698765432", full_name="Mohamed Ben Ali")
    lead = Lead(tenant_id=tenant.id, customer_id=customer.id, status=LeadStatus.SOURCING.value)
    vehicle = Vehicle(
        tenant_id=tenant.id,
        make="Volkswagen",
        model="Golf 8",
        first_registration_year=2023,
        mileage_km=25000,
        fuel_type="Diesel",
        transmission="Automatic",
        purchase_price_eur=Decimal("21000.00"),
        vat_regime=VATRegime.NETTO_EXPORT.value,
        status=VehicleStatus.AVAILABLE.value,
    )

    q = Quotation(
        tenant_id=tenant.id,
        lead_id=lead.id,
        vehicle_id=vehicle.id,
        quote_number="QT-2026-00002",
        vehicle_price_cents=2100000,
        total_price_cents=2100000,
        tenant=tenant,
        lead=lead,
        vehicle=vehicle,
    )

    item1 = QuotationItem(
        quotation_id=q.id,
        description="Antwerp Port Transport",
        unit_price_cents=80000,
        quantity=1,
        total_price_cents=80000,
        quotation=q,
    )

    assert q.tenant is tenant
    assert q in tenant.quotations
    assert q.lead is lead
    assert q in lead.quotations
    assert q.vehicle is vehicle
    assert q in vehicle.quotations
    assert item1 in q.items
    assert item1.quotation is q


def test_quotation_table_indexes_and_constraints() -> None:
    """Verify Quotation __table_args__ defines check constraints and indexes."""
    table_args = Quotation.__table_args__
    constraints = [arg for arg in table_args if isinstance(arg, CheckConstraint)]
    indexes = [arg for arg in table_args if isinstance(arg, Index)]

    constraint_names = [c.name for c in constraints]
    assert "ck_quotations_vat_regime" in constraint_names
    assert "ck_quotations_status" in constraint_names
    assert "ck_quotations_approval_status" in constraint_names

    index_names = [idx.name for idx in indexes]
    assert "ix_quotations_tenant_id" in index_names
    assert "ix_quotations_lead_id" in index_names
    assert "ix_quotations_vehicle_id" in index_names
    assert "ix_quotations_tenant_status" in index_names
    assert "ix_quotations_quote_number" in index_names
    assert "ix_quotations_created_at" in index_names


@pytest.mark.asyncio
async def test_quotation_db_persistence() -> None:
    """Verify AsyncSession DB persistence for Quotation and QuotationItem."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    async for session in get_db_session():
        tenant = Tenant(name="Tunis Export Sarl", slug=f"tunis-{uuid.uuid4().hex[:8]}")
        customer = Customer(tenant_id=tenant.id, phone="+21622334455", full_name="Youssef Trabelsi")
        lead = Lead(tenant_id=tenant.id, customer_id=customer.id, status=LeadStatus.QUALIFIED.value)
        vehicle = Vehicle(
            tenant_id=tenant.id,
            make="BMW",
            model="320d",
            first_registration_year=2022,
            mileage_km=40000,
            fuel_type="Diesel",
            transmission="Automatic",
            purchase_price_eur=Decimal("26500.00"),
            vat_regime=VATRegime.NETTO_EXPORT.value,
        )
        session.add_all([tenant, customer, lead, vehicle])
        await session.flush()

        q = Quotation(
            tenant_id=tenant.id,
            lead_id=lead.id,
            vehicle_id=vehicle.id,
            quote_number="QT-2026-99999",
            vat_regime=VATRegime.NETTO_EXPORT.value,
            vehicle_price_cents=2650000,
            shipping_fee_cents=100000,
            customs_estimate_tnd=Decimal("9800.000"),
            discount_cents=50000,
            discount_percentage=Decimal("1.88"),
            total_price_cents=2700000,
            status=QuotationStatus.DRAFT.value,
            approval_status=QuotationApprovalStatus.AUTO_APPROVED.value,
            disclaimer_text="Informational estimate only per BR-006.",
        )
        session.add(q)
        await session.flush()

        item = QuotationItem(
            quotation_id=q.id,
            description="Export Registration Certificate",
            unit_price_cents=25000,
            quantity=1,
            total_price_cents=25000,
        )
        session.add(item)
        await session.commit()

        # Retrieve and verify exact values
        retrieved = await session.get(Quotation, q.id)
        assert retrieved is not None
        assert retrieved.quote_number == "QT-2026-99999"
        assert retrieved.vehicle_price_cents == 2650000
        assert retrieved.shipping_fee_cents == 100000
        assert retrieved.customs_estimate_tnd == Decimal("9800.000")
        assert retrieved.discount_cents == 50000
        assert retrieved.total_price_cents == 2700000
        assert len(retrieved.items) == 1
        assert retrieved.items[0].description == "Export Registration Certificate"
        assert retrieved.items[0].unit_price_cents == 25000
        break
