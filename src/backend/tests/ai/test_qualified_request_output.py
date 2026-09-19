"""Qualified Request Output & Deterministic CSV Export Test Suite (Phase 7).

Verifies:
1. PostgreSQL is the authoritative source of truth.
2. CSV contains ONLY QUALIFIED vehicle requests; incomplete requests are strictly excluded.
3. UTF-8 (with BOM) encoding preserving Arabic, French, and German characters.
4. Deterministic stable column order.
5. Complete CSV file regeneration on-demand from PostgreSQL database.
6. Owner notification content completeness (name, phone, vehicle, requirements, timestamp).
7. Attempting to export non-qualified requests raises validation errors.
"""

import csv
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.tenant import Tenant
from app.models.vehicle_request import VehicleRequest, VehicleRequestStatus
from app.ports.whatsapp import WhatsAppProvider
from app.services.csv_export_service import CSV_FIELDNAMES, CSVExportService
from app.services.owner_notifier import OwnerNotificationService
from app.utils.uuid import generate_uuidv7


@pytest.mark.asyncio
async def test_csv_contains_only_qualified_requests_and_excludes_incomplete(db_session: AsyncSession):
    """Verify CSV export includes ONLY qualified requests, strictly excluding Collecting and Pending requests."""
    tenant_id = generate_uuidv7()
    tenant = Tenant(id=tenant_id, name="Test Auto Export", slug=f"t-{uuid.uuid4().hex[:6]}")
    
    cust1 = Customer(id=generate_uuidv7(), tenant_id=tenant_id, phone_e164="+33611111111", first_name="Ali")
    cust2 = Customer(id=generate_uuidv7(), tenant_id=tenant_id, phone_e164="+33622222222", first_name="Bilal")
    cust3 = Customer(id=generate_uuidv7(), tenant_id=tenant_id, phone_e164="+33633333333", first_name="Chokri")
    
    # 1. Qualified Request
    req_qualified = VehicleRequest(
        id=generate_uuidv7(),
        tenant_id=tenant_id,
        customer_id=cust1.id,
        make="BMW",
        model="X5",
        min_year=2022,
        budget_eur=Decimal("45000.00"),
        fuel_type="Diesel",
        transmission="Automatic",
        status=VehicleRequestStatus.QUALIFIED,
        confirmed_at=datetime.now(UTC) - timedelta(hours=2),
    )
    
    # 2. Incomplete Collecting Request
    req_collecting = VehicleRequest(
        id=generate_uuidv7(),
        tenant_id=tenant_id,
        customer_id=cust2.id,
        make="Volkswagen",
        model="Golf 8",
        min_year=2021,
        status=VehicleRequestStatus.COLLECTING,
        confirmed_at=None,
    )

    # 3. Incomplete Awaiting Confirmation Request
    req_awaiting = VehicleRequest(
        id=generate_uuidv7(),
        tenant_id=tenant_id,
        customer_id=cust3.id,
        make="Audi",
        model="A6",
        min_year=2023,
        budget_eur=Decimal("40000.00"),
        status=VehicleRequestStatus.AWAITING_CONFIRMATION,
        confirmed_at=None,
    )

    db_session.add_all([tenant, cust1, cust2, cust3, req_qualified, req_collecting, req_awaiting])
    await db_session.commit()

    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_service = CSVExportService(export_dir=tmp_dir)
        csv_path = await csv_service.regenerate_csv_from_db(db=db_session, tenant_id=tenant_id)

        assert csv_path.exists()
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = list(csv.DictReader(f))
            # Must contain ONLY the qualified request (1 row out of 3 requests)
            assert len(reader) == 1
            assert reader[0]["request_id"] == str(req_qualified.id)
            assert reader[0]["make"] == "BMW"
            assert reader[0]["model"] == "X5"
            assert reader[0]["status"] == VehicleRequestStatus.QUALIFIED


@pytest.mark.asyncio
async def test_csv_utf8_encoding_preserves_arabic_and_french_characters(db_session: AsyncSession):
    """Verify Arabic and French characters are preserved flawlessly in UTF-8 BOM CSV export."""
    tenant_id = generate_uuidv7()
    tenant = Tenant(id=tenant_id, name="Export Méditerranée", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(
        id=generate_uuidv7(),
        tenant_id=tenant_id,
        phone_e164="+21698765432",
        first_name="محمد",
        full_name="محمد بن سالم",
        preferred_language="ar",
    )
    vreq = VehicleRequest(
        id=generate_uuidv7(),
        tenant_id=tenant_id,
        customer_id=customer.id,
        make="Mercedes-Benz",
        model="Classe C Édition Spéciale",
        min_year=2022,
        fuel_type="Diesel",
        transmission="Automatique",
        budget_eur=Decimal("35000.00"),
        destination_port="Radès (Port)",
        additional_requirements="Toit ouvrant panoramique, Pack AMG, Couleur Noir Métallisé, حالة ممتازة",
        status=VehicleRequestStatus.QUALIFIED,
        confirmed_at=datetime.now(UTC),
    )

    db_session.add_all([tenant, customer, vreq])
    await db_session.commit()

    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_service = CSVExportService(export_dir=tmp_dir)
        csv_path = await csv_service.regenerate_csv_from_db(db=db_session, tenant_id=tenant_id)

        # Read back raw UTF-8 BOM and parse
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = list(csv.DictReader(f))
            assert len(reader) == 1
            row = reader[0]
            assert row["customer_name"] == "محمد بن سالم"
            assert row["model"] == "Classe C Édition Spéciale"
            assert "Radès" in row["destination_port"]
            assert "Toit ouvrant panoramique" in row["additional_requirements"]
            assert "حالة ممتازة" in row["additional_requirements"]


def test_csv_stable_column_order():
    """Verify CSV column order is strictly identical and deterministic."""
    expected_order = [
        "request_id",
        "tenant_id",
        "customer_id",
        "customer_phone",
        "customer_name",
        "make",
        "model",
        "year",
        "fuel_type",
        "transmission",
        "budget_eur",
        "destination_port",
        "fcr_compatible",
        "additional_requirements",
        "confirmed_at",
        "status",
    ]
    assert CSV_FIELDNAMES == expected_order


@pytest.mark.asyncio
async def test_full_csv_regeneration_from_database(db_session: AsyncSession):
    """Verify complete CSV regeneration from PostgreSQL reproduces all historical qualified requests."""
    tenant_id = generate_uuidv7()
    tenant = Tenant(id=tenant_id, name="Auto Export Hub", slug=f"t-{uuid.uuid4().hex[:6]}")
    cust = Customer(id=generate_uuidv7(), tenant_id=tenant_id, phone_e164="+33699887766", first_name="Tarek")
    
    t1 = datetime.now(UTC) - timedelta(days=2)
    t2 = datetime.now(UTC) - timedelta(days=1)
    t3 = datetime.now(UTC)

    req1 = VehicleRequest(
        id=generate_uuidv7(),
        tenant_id=tenant_id,
        customer_id=cust.id,
        make="Peugeot",
        model="3008",
        min_year=2021,
        budget_eur=Decimal("22000.00"),
        status=VehicleRequestStatus.QUALIFIED,
        confirmed_at=t1,
    )
    req2 = VehicleRequest(
        id=generate_uuidv7(),
        tenant_id=tenant_id,
        customer_id=cust.id,
        make="Renault",
        model="Austral",
        min_year=2023,
        budget_eur=Decimal("27000.00"),
        status=VehicleRequestStatus.QUALIFIED,
        confirmed_at=t2,
    )
    req3 = VehicleRequest(
        id=generate_uuidv7(),
        tenant_id=tenant_id,
        customer_id=cust.id,
        make="Hyundai",
        model="Tucson",
        min_year=2022,
        budget_eur=Decimal("26000.00"),
        status=VehicleRequestStatus.QUALIFIED,
        confirmed_at=t3,
    )

    db_session.add_all([tenant, cust, req1, req2, req3])
    await db_session.commit()

    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_service = CSVExportService(export_dir=tmp_dir)
        csv_path = await csv_service.regenerate_csv_from_db(db=db_session, tenant_id=tenant_id)

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
            assert len(rows) == 3
            # Check ordered deterministically by confirmed_at
            assert rows[0]["make"] == "Peugeot"
            assert rows[1]["make"] == "Renault"
            assert rows[2]["make"] == "Hyundai"


def test_incomplete_request_cannot_be_exported_to_qualified_csv():
    """Verify attempting to export an incomplete / unconfirmed request raises ValueError."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_service = CSVExportService(export_dir=tmp_dir)

        # 1. Test unconfirmed request (confirmed_at is None)
        with pytest.raises(ValueError, match="Cannot export non-qualified request"):
            csv_service.export_qualified_request(
                request_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                customer_id=uuid.uuid4(),
                customer_phone="+33612345678",
                customer_name="Test Customer",
                make="Volkswagen",
                model="Golf",
                year=2022,
                fuel_type="Diesel",
                transmission="Manual",
                budget_eur=20000.0,
                destination_port="Rades",
                fcr_compatible=True,
                additional_requirements=None,
                confirmed_at=None,
                status="Collecting",
            )

        # 2. Test status != QUALIFIED
        with pytest.raises(ValueError, match="Cannot export non-qualified request"):
            csv_service.export_qualified_request(
                request_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                customer_id=uuid.uuid4(),
                customer_phone="+33612345678",
                customer_name="Test Customer",
                make="Audi",
                model="A4",
                year=2021,
                fuel_type="Diesel",
                transmission="Automatic",
                budget_eur=25000.0,
                destination_port="Rades",
                fcr_compatible=True,
                additional_requirements=None,
                confirmed_at=datetime.now(UTC),
                status="Pending",
            )


@pytest.mark.asyncio
async def test_owner_notification_contains_all_required_details(monkeypatch: pytest.MonkeyPatch):
    """Verify owner notification contains customer name, phone, vehicle, requirements, and confirmation timestamp."""
    monkeypatch.setattr("app.core.config.settings.OWNER_NOTIFICATION_PHONE_E164", "+4917011223344")

    mock_whatsapp = AsyncMock(spec=WhatsAppProvider)
    notifier = OwnerNotificationService(whatsapp_provider=mock_whatsapp)

    confirmed_ts = datetime(2026, 9, 19, 17, 30, 0, tzinfo=UTC)

    success = await notifier.notify_owner_of_qualified_request(
        tenant_name="Auto Export Europe",
        customer_phone="+33612345678",
        customer_name="Nabil Karoui",
        make="BMW",
        model="X3",
        year=2022,
        fuel_type="Diesel",
        transmission="Automatique",
        budget_eur=32000.0,
        destination_port="Radès",
        fcr_compatible=True,
        additional_requirements="Pack M Sport, Toit panoramique",
        confirmed_at=confirmed_ts,
    )

    assert success is True
    mock_whatsapp.send_text_message.assert_awaited_once()

    call_kwargs = mock_whatsapp.send_text_message.call_args.kwargs
    alert_body = call_kwargs["text_body"]
    recipient = call_kwargs["recipient_e164"]

    assert recipient == "+4917011223344"
    assert "Nabil Karoui" in alert_body
    assert "+33612345678" in alert_body
    assert "BMW X3" in alert_body
    assert "2022" in alert_body
    assert "32,000 €" in alert_body
    assert "Diesel" in alert_body
    assert "Automatique" in alert_body
    assert "Radès" in alert_body
    assert "Conforme 5 ans FCR" in alert_body
    assert "Pack M Sport, Toit panoramique" in alert_body
    assert "2026-09-19 17:30:00 UTC" in alert_body
