"""Unit tests for QuotationService creation, tax provenance, and manager approval workflows."""

import uuid
from decimal import Decimal

import pytest

from app.core.database import check_database_health, get_db_session
from app.core.errors import ForbiddenException, NotFoundException, ValidationException
from app.models.customer import Customer
from app.models.lead import Lead, LeadStatus
from app.models.quotation import QuotationApprovalStatus, QuotationStatus
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.vehicle import VATRegime, Vehicle
from app.services.quotation_service import ItemCreateParams, QuotationService


@pytest.mark.asyncio
async def test_create_quotation_auto_approved_success() -> None:
    """Verify Quotation creation under 5% discount auto-approves and attaches customs disclaimer."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    async for db_session in get_db_session():
        tenant = Tenant(name="Test Dealer Tenant", slug=f"t-{uuid.uuid4().hex[:8]}")
        customer = Customer(tenant_id=tenant.id, phone="+21698111222", full_name="Ali Karoui")
        lead = Lead(tenant_id=tenant.id, customer_id=customer.id, status=LeadStatus.QUALIFIED.value)
        vehicle = Vehicle(
            tenant_id=tenant.id,
            make="BMW",
            model="530d",
            first_registration_year=2023,
            mileage_km=30000,
            fuel_type="Diesel",
            transmission="Automatic",
            purchase_price_eur=Decimal("38000.00"),
            vat_regime=VATRegime.NETTO_EXPORT.value,
        )
        db_session.add_all([tenant, customer, lead, vehicle])
        await db_session.flush()

        service = QuotationService(session=db_session)
        quote = await service.create_quotation(
            tenant_id=tenant.id,
            lead_id=lead.id,
            vehicle_id=vehicle.id,
            vat_regime=VATRegime.NETTO_EXPORT.value,
            vehicle_price_cents=3800000,  # €38,000.00
            shipping_fee_cents=150000,   # €1,500.00
            items=[
                ItemCreateParams(
                    description="Export Preparation", unit_price_cents=50000, quantity=1
                )
            ],
            discount_percentage=Decimal("3.00"),  # 3% <= 5%
        )

        assert quote.id is not None
        assert quote.quote_number.startswith("QT-2026-")
        assert quote.vehicle_price_cents == 3800000
        assert quote.shipping_fee_cents == 150000
        assert quote.discount_cents == 120000
        assert quote.total_price_cents == 3880000
        assert quote.approval_status == QuotationApprovalStatus.AUTO_APPROVED.value
        assert quote.status == QuotationStatus.DRAFT.value
        assert len(quote.items) == 1
        assert quote.items[0].description == "Export Preparation"
        assert quote.disclaimer_text is not None
        assert "Informational Estimate Only" in quote.disclaimer_text
        break


@pytest.mark.asyncio
async def test_create_quotation_missing_lead_raises_not_found() -> None:
    """Verify create_quotation with non-existent lead ID raises NotFoundException."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    async for db_session in get_db_session():
        tenant_id = uuid.uuid4()
        service = QuotationService(session=db_session)

        with pytest.raises(NotFoundException, match="Lead with ID"):
            await service.create_quotation(
                tenant_id=tenant_id,
                lead_id=uuid.uuid4(),
                vehicle_id=None,
                vat_regime=VATRegime.NETTO_EXPORT.value,
                vehicle_price_cents=1000000,
            )
        break


@pytest.mark.asyncio
async def test_create_quotation_high_discount_pending_approval_and_admin_approval() -> None:
    """Verify >5% discount requires TenantAdmin approval (BR-015)."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    async for db_session in get_db_session():
        tenant = Tenant(name="Approval Test Tenant", slug=f"t-{uuid.uuid4().hex[:8]}")
        customer = Customer(tenant_id=tenant.id, phone="+21698333444", full_name="Sami Mansour")
        lead = Lead(tenant_id=tenant.id, customer_id=customer.id, status=LeadStatus.QUALIFIED.value)
        admin_user = User(
            tenant_id=tenant.id,
            email=f"admin-{uuid.uuid4().hex[:6]}@example.com",
            password_hash="hashed_pw_dummy_1234567890",  # noqa: S106
            full_name="Admin Manager",
            role=UserRole.TENANT_ADMIN.value,
        )
        sales_rep = User(
            tenant_id=tenant.id,
            email=f"sales-{uuid.uuid4().hex[:6]}@example.com",
            password_hash="hashed_pw_dummy_1234567890",  # noqa: S106
            full_name="Sales Rep",
            role=UserRole.SALES_AGENT.value,
        )
        db_session.add_all([tenant, customer, lead, admin_user, sales_rep])
        await db_session.flush()

        service = QuotationService(session=db_session)

        # 1. Create quote with 8% discount -> Pending Approval
        quote = await service.create_quotation(
            tenant_id=tenant.id,
            lead_id=lead.id,
            vehicle_id=None,
            vat_regime=VATRegime.NETTO_EXPORT.value,
            vehicle_price_cents=2500000,  # €25,000.00
            discount_percentage=Decimal("8.00"),  # > 5% threshold
        )

        assert quote.approval_status == QuotationApprovalStatus.PENDING_APPROVAL.value
        assert quote.status == QuotationStatus.PENDING_APPROVAL.value

        # 2. Sales rep attempting approval fails with ForbiddenException
        with pytest.raises(ForbiddenException, match="Only TenantAdmin can approve"):
            await service.approve_quotation(
                tenant_id=tenant.id, quotation_id=quote.id, admin_user=sales_rep
            )

        # 3. TenantAdmin approves quote successfully
        approved_quote = await service.approve_quotation(
            tenant_id=tenant.id, quotation_id=quote.id, admin_user=admin_user
        )
        assert approved_quote.approval_status == QuotationApprovalStatus.APPROVED.value
        assert approved_quote.status == QuotationStatus.APPROVED.value

        # 4. Attempting to approve an already approved quote fails with ValidationException
        with pytest.raises(ValidationException, match="is not pending approval"):
            await service.approve_quotation(
                tenant_id=tenant.id, quotation_id=quote.id, admin_user=admin_user
            )
        break


@pytest.mark.asyncio
async def test_reject_quotation_by_admin() -> None:
    """Verify TenantAdmin can reject a pending discount quotation (BR-015)."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    async for db_session in get_db_session():
        tenant = Tenant(name="Reject Test Tenant", slug=f"t-{uuid.uuid4().hex[:8]}")
        customer = Customer(tenant_id=tenant.id, phone="+21698555666", full_name="Kamel Gharbi")
        lead = Lead(tenant_id=tenant.id, customer_id=customer.id, status=LeadStatus.QUALIFIED.value)
        admin_user = User(
            tenant_id=tenant.id,
            email=f"admin-{uuid.uuid4().hex[:6]}@example.com",
            password_hash="hashed_pw_dummy_1234567890",  # noqa: S106
            full_name="Admin Manager",
            role=UserRole.TENANT_ADMIN.value,
        )
        db_session.add_all([tenant, customer, lead, admin_user])
        await db_session.flush()

        service = QuotationService(session=db_session)
        quote = await service.create_quotation(
            tenant_id=tenant.id,
            lead_id=lead.id,
            vehicle_id=None,
            vat_regime=VATRegime.NETTO_EXPORT.value,
            vehicle_price_cents=2000000,
            discount_percentage=Decimal("10.00"),
        )

        rejected_quote = await service.reject_quotation(
            tenant_id=tenant.id, quotation_id=quote.id, admin_user=admin_user
        )
        assert rejected_quote.approval_status == QuotationApprovalStatus.REJECTED.value
        assert rejected_quote.status == QuotationStatus.REJECTED.value
        break
