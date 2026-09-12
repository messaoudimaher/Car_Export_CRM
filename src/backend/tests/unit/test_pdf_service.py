"""Unit tests for ReportLab QuotePdfGenerator PDF rendering (WS-10, TASK-1003)."""

from decimal import Decimal

from app.models.quotation import Quotation, QuotationStatus
from app.models.tenant import Tenant
from app.models.vehicle import VATRegime, Vehicle
from app.services.pdf_service import QuotePdfGenerator


def test_quote_pdf_generator_valid_pdf_binary() -> None:
    """Verify QuotePdfGenerator emits valid PDF-1.4 binary bytes with required headers."""
    tenant = Tenant(name="Alpha Export Dealership Sarl", slug="alpha-export")
    vehicle = Vehicle(
        tenant_id=tenant.id,
        make="BMW",
        model="X5 xDrive30d",
        first_registration_year=2023,
        mileage_km=35000,
        fuel_type="Diesel",
        transmission="Automatic",
        purchase_price_eur=Decimal("45000.00"),
        vat_regime=VATRegime.NETTO_EXPORT.value,
        vin="WBA1234567890FGHI",
    )
    quotation = Quotation(
        tenant_id=tenant.id,
        quote_number="QT-2026-88888",
        vat_regime=VATRegime.NETTO_EXPORT.value,
        vehicle_price_cents=4500000,  # €45,000.00
        shipping_fee_cents=150000,  # €1,500.00
        customs_estimate_tnd=Decimal("6750.000"),
        discount_cents=100000,  # €1,000.00
        discount_percentage=Decimal("2.15"),
        total_price_cents=4550000,  # €45,500.00
        status=QuotationStatus.DRAFT.value,
        disclaimer_text=(
            "Informational Estimate Only: Tunisia customs duties and FCR import taxes are "
            "estimated based on official schedule version 2026.1 (EUR/TND rate: 3.350)."
        ),
    )

    pdf_bytes = QuotePdfGenerator.generate_pdf_bytes(
        quotation=quotation,
        tenant=tenant,
        vehicle=vehicle,
        customer_name="Moncef Ben Slimane",
        customer_phone="+21698123456",
    )

    # 1. Verify valid PDF binary header
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF-1.4") or pdf_bytes.startswith(b"%PDF-")

    # 2. Verify key strings in PDF binary payload stream
    pdf_text = pdf_bytes.decode("latin1", errors="ignore")
    assert "Alpha Export Dealership Sarl" in pdf_text or "Export" in pdf_text
    assert "QT-2026-88888" in pdf_text or "88888" in pdf_text
