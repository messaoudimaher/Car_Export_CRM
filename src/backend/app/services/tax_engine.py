"""Deterministic Tax Engine for European VAT & Tunisian FCR Customs Duty (WS-10)."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.models.quotation import QuotationApprovalStatus, QuotationStatus
from app.models.vehicle import VATRegime

# Mandatory BR-006 Disclaimer Template
BR006_CUSTOMS_DISCLAIMER = (
    "Informational Estimate Only: Tunisia customs duties and FCR import taxes are estimated "
    "based on official schedule version {version_id} (EUR/TND exchange rate: {exchange_rate}). "
    "Final duties are assessed at customs clearance."
)

# Manager Discount Approval Threshold (BR-015)
MAX_AUTO_APPROVED_DISCOUNT_PERCENT = Decimal("5.00")


@dataclass(frozen=True)
class TaxRuleVersion:
    """Versioned tax schedule configuration rules."""

    version_id: str
    effective_date: str
    vat_netto_rate: Decimal
    vat_brutto_margin_rate: Decimal
    standard_customs_duty_rate: Decimal
    fcr_customs_discount_rate: Decimal
    eur_tnd_exchange_rate: Decimal


# Current active tax rule schedule (Version 2026.1)
DEFAULT_TAX_RULE_VERSION = TaxRuleVersion(
    version_id="2026.1",
    effective_date="2026-01-01",
    vat_netto_rate=Decimal("0.00"),
    vat_brutto_margin_rate=Decimal("19.00"),
    standard_customs_duty_rate=Decimal("30.00"),
    fcr_customs_discount_rate=Decimal("85.00"),
    eur_tnd_exchange_rate=Decimal("3.350"),
)


@dataclass(frozen=True)
class TaxCalculationResult:
    """Provenanced deterministic calculation output."""

    rule_version_id: str
    vat_regime: str
    vehicle_price_cents: int
    shipping_fee_cents: int
    additional_items_cents: int
    subtotal_cents: int
    discount_cents: int
    discount_percentage: Decimal
    total_price_cents: int
    customs_estimate_tnd: Decimal
    customs_duty_rate_percent: Decimal
    fcr_discount_percent: Decimal
    eur_tnd_exchange_rate: Decimal
    disclaimer_text: str
    requires_manager_approval: bool
    approval_status: QuotationApprovalStatus
    status: QuotationStatus


class TaxEngine:
    """Pure, deterministic calculation engine for export quote pricing and customs duties.

    Note: LLM and AI models are strictly barred from performing or modifying tax calculations.
    """

    def __init__(self, rule_version: TaxRuleVersion = DEFAULT_TAX_RULE_VERSION) -> None:
        self.rule_version = rule_version

    def calculate(
        self,
        vat_regime: str | VATRegime,
        vehicle_price_cents: int,
        shipping_fee_cents: int = 0,
        additional_items_cents: int = 0,
        discount_percentage: Decimal | None = None,
        discount_cents: int | None = None,
        has_margin_override: bool = False,
    ) -> TaxCalculationResult:
        """Perform deterministic calculation of quotation pricing and FCR customs estimates.

        Args:
            vat_regime: European VAT regime (Netto_Export or Brutto_Margin).
            vehicle_price_cents: Vehicle price in Euro cents.
            shipping_fee_cents: Shipping fee in Euro cents.
            additional_items_cents: Total additional line items price in Euro cents.
            discount_percentage: Optional percentage discount (0.00 to 100.00).
            discount_cents: Optional fixed amount discount in Euro cents.
            has_margin_override: Flag indicating manual margin adjustment.

        Returns:
            TaxCalculationResult with exact integer cents, TND estimate, and approval status.
        """
        regime_str = vat_regime.value if isinstance(vat_regime, VATRegime) else vat_regime

        subtotal_cents = vehicle_price_cents + shipping_fee_cents + additional_items_cents
        if subtotal_cents < 0:
            raise ValueError("Subtotal price cannot be negative")

        calc_discount_cents = 0
        calc_discount_percentage = Decimal("0.00")

        if discount_percentage is not None:
            if discount_percentage < Decimal("0.00") or discount_percentage > Decimal("100.00"):
                raise ValueError("Discount percentage must be between 0 and 100")
            calc_discount_percentage = discount_percentage.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            raw_cents = Decimal(subtotal_cents) * (calc_discount_percentage / Decimal("100"))
            calc_discount_cents = int(raw_cents.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        elif discount_cents is not None:
            if discount_cents < 0:
                raise ValueError("Discount cents cannot be negative")
            calc_discount_cents = discount_cents
            if subtotal_cents > 0:
                raw_pct = (Decimal(calc_discount_cents) / Decimal(subtotal_cents)) * Decimal("100")
                calc_discount_percentage = raw_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if calc_discount_cents > subtotal_cents:
            raise ValueError("Discount cannot exceed subtotal price")

        total_price_cents = subtotal_cents - calc_discount_cents

        eff_duty_pct = self.rule_version.standard_customs_duty_rate * (
            Decimal("1.00") - (self.rule_version.fcr_customs_discount_rate / Decimal("100.00"))
        )
        vehicle_eur = Decimal(vehicle_price_cents) / Decimal("100")
        base_tnd = vehicle_eur * self.rule_version.eur_tnd_exchange_rate
        customs_estimate_tnd = (base_tnd * (eff_duty_pct / Decimal("100"))).quantize(
            Decimal("0.001"), rounding=ROUND_HALF_UP
        )

        requires_approval = (
            calc_discount_percentage > MAX_AUTO_APPROVED_DISCOUNT_PERCENT or has_margin_override
        )

        if requires_approval:
            approval_status = QuotationApprovalStatus.PENDING_APPROVAL
            status = QuotationStatus.PENDING_APPROVAL
        else:
            approval_status = QuotationApprovalStatus.AUTO_APPROVED
            status = QuotationStatus.DRAFT

        disclaimer_text = BR006_CUSTOMS_DISCLAIMER.format(
            version_id=self.rule_version.version_id,
            exchange_rate=f"{self.rule_version.eur_tnd_exchange_rate:.3f}",
        )

        return TaxCalculationResult(
            rule_version_id=self.rule_version.version_id,
            vat_regime=regime_str,
            vehicle_price_cents=vehicle_price_cents,
            shipping_fee_cents=shipping_fee_cents,
            additional_items_cents=additional_items_cents,
            subtotal_cents=subtotal_cents,
            discount_cents=calc_discount_cents,
            discount_percentage=calc_discount_percentage,
            total_price_cents=total_price_cents,
            customs_estimate_tnd=customs_estimate_tnd,
            customs_duty_rate_percent=self.rule_version.standard_customs_duty_rate,
            fcr_discount_percent=self.rule_version.fcr_customs_discount_rate,
            eur_tnd_exchange_rate=self.rule_version.eur_tnd_exchange_rate,
            disclaimer_text=disclaimer_text,
            requires_manager_approval=requires_approval,
            approval_status=approval_status,
            status=status,
        )
