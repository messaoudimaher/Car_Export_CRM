"""Unit tests for TaxEngine deterministic pricing, FCR customs duties & BR-015 approval logic."""

from decimal import Decimal

import pytest

from app.models.quotation import QuotationApprovalStatus, QuotationStatus
from app.models.vehicle import VATRegime
from app.services.tax_engine import TaxEngine, TaxRuleVersion


def test_tax_engine_default_version_initialization() -> None:
    """Verify TaxEngine initializes with default 2026.1 rule schedule."""
    engine = TaxEngine()
    assert engine.rule_version.version_id == "2026.1"
    assert engine.rule_version.standard_customs_duty_rate == Decimal("30.00")
    assert engine.rule_version.fcr_customs_discount_rate == Decimal("85.00")
    assert engine.rule_version.eur_tnd_exchange_rate == Decimal("3.350")


def test_tax_engine_calculate_standard_quote_under_5_percent_discount() -> None:
    """Verify deterministic pricing and auto-approval when discount <= 5% (BR-015)."""
    engine = TaxEngine()
    result = engine.calculate(
        vat_regime=VATRegime.NETTO_EXPORT,
        vehicle_price_cents=3000000,  # €30,000.00
        shipping_fee_cents=100000,  # €1,000.00
        additional_items_cents=50000,  # €500.00
        discount_percentage=Decimal("4.00"),  # 4% discount <= 5% threshold
    )

    assert result.subtotal_cents == 3150000
    assert result.discount_cents == 126000  # 3,150,000 * 0.04 = 126,000 cents
    assert result.total_price_cents == 3024000
    assert result.requires_manager_approval is False
    assert result.approval_status == QuotationApprovalStatus.AUTO_APPROVED
    assert result.status == QuotationStatus.DRAFT

    # FCR Customs estimate check (BR-006):
    # €30,000 * 3.350 = TND 100,500.
    # Effective duty = 30% * (1 - 0.85) = 4.5%.
    # TND 100,500 * 0.045 = TND 4,522.500
    assert result.customs_estimate_tnd == Decimal("4522.500")
    assert "Informational Estimate Only" in result.disclaimer_text
    assert "version 2026.1" in result.disclaimer_text


def test_tax_engine_calculate_high_discount_triggers_pending_approval() -> None:
    """Verify discount > 5% sets approval_status = Pending_Approval (BR-015)."""
    engine = TaxEngine()
    result = engine.calculate(
        vat_regime=VATRegime.BRUTTO_MARGIN,
        vehicle_price_cents=2000000,  # €20,000.00
        shipping_fee_cents=100000,  # €1,000.00
        discount_percentage=Decimal("7.00"),  # 7% discount > 5%
    )

    assert result.subtotal_cents == 2100000
    assert result.discount_cents == 147000
    assert result.total_price_cents == 1953000
    assert result.requires_manager_approval is True
    assert result.approval_status == QuotationApprovalStatus.PENDING_APPROVAL
    assert result.status == QuotationStatus.PENDING_APPROVAL


def test_tax_engine_margin_override_triggers_pending_approval() -> None:
    """Verify margin override flag sets approval_status = Pending_Approval."""
    engine = TaxEngine()
    result = engine.calculate(
        vat_regime=VATRegime.NETTO_EXPORT,
        vehicle_price_cents=1500000,
        discount_percentage=Decimal("2.00"),
        has_margin_override=True,
    )

    assert result.requires_manager_approval is True
    assert result.approval_status == QuotationApprovalStatus.PENDING_APPROVAL
    assert result.status == QuotationStatus.PENDING_APPROVAL


def test_tax_engine_fixed_cents_discount_calculation() -> None:
    """Verify fixed discount in cents calculates percentage and evaluates threshold correctly."""
    engine = TaxEngine()
    # Subtotal = €20,000.00 (2,000,000 cents). Fixed discount = €1,200.00 (120,000 cents) -> 6.00%
    result = engine.calculate(
        vat_regime=VATRegime.NETTO_EXPORT,
        vehicle_price_cents=2000000,
        discount_cents=120000,
    )

    assert result.discount_percentage == Decimal("6.00")
    assert result.requires_manager_approval is True
    assert result.approval_status == QuotationApprovalStatus.PENDING_APPROVAL


def test_tax_engine_custom_version_schedule() -> None:
    """Verify TaxEngine respects custom TaxRuleVersion schedules."""
    custom_version = TaxRuleVersion(
        version_id="2026.2_TEST",
        effective_date="2026-06-01",
        vat_netto_rate=Decimal("0.00"),
        vat_brutto_margin_rate=Decimal("19.00"),
        standard_customs_duty_rate=Decimal("20.00"),
        fcr_customs_discount_rate=Decimal("90.00"),
        eur_tnd_exchange_rate=Decimal("3.400"),
    )
    engine = TaxEngine(rule_version=custom_version)
    result = engine.calculate(
        vat_regime=VATRegime.NETTO_EXPORT,
        vehicle_price_cents=1000000,  # €10,000.00
    )

    # €10,000 * 3.400 = TND 34,000. Effective duty = 20% * (1 - 0.90) = 2.0%.
    # TND 34,000 * 0.02 = TND 680.000
    assert result.customs_estimate_tnd == Decimal("680.000")
    assert "version 2026.2_TEST" in result.disclaimer_text


def test_tax_engine_validation_errors() -> None:
    """Verify TaxEngine raises ValueError on invalid inputs."""
    engine = TaxEngine()

    with pytest.raises(ValueError, match="Subtotal price cannot be negative"):
        engine.calculate(vat_regime=VATRegime.NETTO_EXPORT, vehicle_price_cents=-500)

    with pytest.raises(ValueError, match="Discount percentage must be between 0 and 100"):
        engine.calculate(
            vat_regime=VATRegime.NETTO_EXPORT,
            vehicle_price_cents=1000000,
            discount_percentage=Decimal("150.00"),
        )

    with pytest.raises(ValueError, match="Discount cannot exceed subtotal price"):
        engine.calculate(
            vat_regime=VATRegime.NETTO_EXPORT,
            vehicle_price_cents=1000000,
            discount_cents=1500000,
        )
