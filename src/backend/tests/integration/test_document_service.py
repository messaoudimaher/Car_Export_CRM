"""Integration tests for DocumentService PDF storage, tenant isolation & idempotency (TASK-1003)."""

import uuid
from decimal import Decimal
from pathlib import Path

import pytest

from app.adapters.object_storage_local import LocalStorageAdapter
from app.core.database import check_database_health, get_db_session
from app.core.errors import ForbiddenException
from app.models.customer import Customer
from app.models.lead import Lead, LeadStatus
from app.models.quotation import Quotation, QuotationStatus
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.vehicle import VATRegime, Vehicle
from app.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_document_service_pdf_generation_and_storage_lifecycle(tmp_path: Path) -> None:
    """Verify DocumentService generates PDF, uploads to storage, and records Document metadata."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    storage = LocalStorageAdapter(base_dir=tmp_path)

    async for db_session in get_db_session():
        tenant = Tenant(name="Sousse Motors", slug=f"sousse-{uuid.uuid4().hex[:8]}")
        customer = Customer(
            tenant_id=tenant.id,
            phone_e164="+21699887766",
            full_name="Habib Bourguiba",
        )
        lead = Lead(tenant_id=tenant.id, customer_id=customer.id, status=LeadStatus.QUALIFIED.value)
        vehicle = Vehicle(
            tenant_id=tenant.id,
            make="Audi",
            model="A4 Avant",
            first_registration_year=2022,
            mileage_km=45000,
            fuel_type="Diesel",
            transmission="Automatic",
            purchase_price_eur=Decimal("24000.00"),
            vat_regime=VATRegime.NETTO_EXPORT.value,
        )
        user = User(
            tenant_id=tenant.id,
            email=f"user-{uuid.uuid4().hex[:6]}@example.com",
            password_hash="hashed_pw_dummy_1234567890",  # noqa: S106
            full_name="Sales Representative",
            role=UserRole.SALES_AGENT.value,
        )
        db_session.add_all([tenant, customer, lead, vehicle, user])
        await db_session.flush()

        quotation = Quotation(
            tenant_id=tenant.id,
            lead_id=lead.id,
            vehicle_id=vehicle.id,
            quote_number="QT-2026-77777",
            vat_regime=VATRegime.NETTO_EXPORT.value,
            vehicle_price_cents=2400000,
            shipping_fee_cents=100000,
            total_price_cents=2500000,
            status=QuotationStatus.DRAFT.value,
        )
        db_session.add(quotation)
        await db_session.flush()

        doc_service = DocumentService(session=db_session, storage_provider=storage)

        # 1. Generate & Store PDF
        doc = await doc_service.generate_and_store_quote_pdf(
            tenant_id=tenant.id,
            quotation_id=quotation.id,
            requesting_user=user,
            version=1,
        )

        assert doc.id is not None
        assert doc.tenant_id == tenant.id
        assert doc.quotation_id == quotation.id
        assert doc.document_type == "Quotation_PDF"
        assert doc.file_name == "QT-2026-77777.pdf"
        assert doc.object_key == f"tenants/{tenant.id}/quotes/{quotation.id}/v1.pdf"
        assert doc.file_size_bytes > 500
        assert quotation.pdf_s3_key == doc.object_key

        # 2. Verify binary object can be retrieved from storage provider
        object_bytes = await storage.get_object(doc.object_key)
        assert object_bytes.startswith(b"%PDF-")

        # 3. Idempotency Check: Calling generate_and_store_quote_pdf again returns existing doc
        doc_again = await doc_service.generate_and_store_quote_pdf(
            tenant_id=tenant.id,
            quotation_id=quotation.id,
            requesting_user=user,
            version=1,
        )
        assert doc_again.id == doc.id

        # 4. Access URL presigned retrieval
        retrieved_doc, access_url = await doc_service.get_document_access_url(
            tenant_id=tenant.id,
            document_id=doc.id,
            requesting_user=user,
            expiration_seconds=3600,
        )
        assert retrieved_doc.id == doc.id
        assert access_url.startswith("file:///")
        break


@pytest.mark.asyncio
async def test_document_service_tenant_isolation(tmp_path: Path) -> None:
    """Verify tenant isolation blocks access/generation for users from different tenants."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    storage = LocalStorageAdapter(base_dir=tmp_path)

    async for db_session in get_db_session():
        tenant_a = Tenant(name="Tenant A", slug=f"ta-{uuid.uuid4().hex[:8]}")
        tenant_b = Tenant(name="Tenant B", slug=f"tb-{uuid.uuid4().hex[:8]}")
        user_a = User(
            tenant_id=tenant_a.id,
            email=f"usera-{uuid.uuid4().hex[:6]}@example.com",
            password_hash="hashed_pw_dummy_1234567890",  # noqa: S106
            full_name="User A",
            role=UserRole.SALES_AGENT.value,
        )
        user_b = User(
            tenant_id=tenant_b.id,
            email=f"userb-{uuid.uuid4().hex[:6]}@example.com",
            password_hash="hashed_pw_dummy_1234567890",  # noqa: S106
            full_name="User B",
            role=UserRole.SALES_AGENT.value,
        )
        db_session.add_all([tenant_a, tenant_b, user_a, user_b])
        await db_session.flush()

        doc_service = DocumentService(session=db_session, storage_provider=storage)

        # User B attempting to generate quote PDF for Tenant A fails with ForbiddenException
        with pytest.raises(ForbiddenException, match="outside their tenant organization"):
            await doc_service.generate_and_store_quote_pdf(
                tenant_id=tenant_a.id,
                quotation_id=uuid.uuid4(),
                requesting_user=user_b,
            )

        # User B attempting to get access URL for Tenant A document fails with ForbiddenException
        with pytest.raises(ForbiddenException, match="outside their tenant organization"):
            await doc_service.get_document_access_url(
                tenant_id=tenant_a.id,
                document_id=uuid.uuid4(),
                requesting_user=user_b,
            )
        break
