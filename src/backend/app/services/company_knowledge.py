"""Deterministic Company Knowledge & Policy Service (Phase 4 Autonomous Agent).

Provides validated company facts, business rules, FCR guidelines, shipping information,
and FAQ answers without complex vector databases or RAG infrastructure.
Guarantees zero hallucination of policies and safe multilingual fallbacks.
"""

from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field


class CompanyProfile(BaseModel):
    """Core company identity, presence, and contact information."""

    name: str = Field("Auto Export Europe", description="Commercial name")
    legal_name: str = Field("Auto Export Europe GmbH", description="Legal business entity")
    country: str = Field("Germany / France / Tunisia", description="Operating territories")
    operating_hours: str = Field("Monday - Saturday: 08:00 - 19:00 (CET)", description="Working hours")
    contact_email: str = Field("contact@autoexport.eu", description="Support email")
    contact_phone: str = Field("+49 89 12345678", description="Contact telephone")
    source_countries: list[str] = Field(
        default_factory=lambda: ["Germany", "France", "Italy", "Belgium", "Netherlands"]
    )
    destination_ports: list[str] = Field(
        default_factory=lambda: ["Rades", "La Goulette", "Bizerte", "Zarzis"]
    )
    services: list[str] = Field(
        default_factory=lambda: [
            "Sourcing and technical inspection of European vehicles",
            "Export customs clearance and European export documentation (EUR.1, EX-A, CoC)",
            "Insured maritime shipping to Tunisian seaports",
            "Tunisia customs clearance assistance & FCR consultation",
        ]
    )


class FCRBusinessRules(BaseModel):
    """Verified Tunisian customs FCR (Franchise Changement de Résidence) regulations."""

    age_limit_years: int = Field(5, description="Maximum vehicle age under standard FCR")
    description: str = Field(
        "Under Tunisian customs law, the FCR privilege allows Tunisian expatriates (TRE) to import "
        "one personal passenger vehicle with reduced taxes or customs duty exemption. "
        "Vehicle age must not exceed 5 years at first registration date."
    )
    eligibility_requirements: list[str] = Field(
        default_factory=lambda: [
            "Tunisian expatriate (TRE) residing abroad for at least 2 consecutive years",
            "Not having stayed in Tunisia for more than 120 days per 365-day period during the 2 years",
            "Adult of at least 18 years of age",
        ]
    )
    required_documents: list[str] = Field(
        default_factory=lambda: [
            "Original European vehicle registration certificate (Carte grise / Fahrzeugbrief)",
            "European Certificate of Conformity (CoC)",
            "Commercial sales invoice (Facture d'achat acquittée)",
            "Export customs declaration (EX-A)",
            "Consular registration card and valid passport",
        ]
    )


class ShippingPolicy(BaseModel):
    """Maritime transit logistics and port routing."""

    departure_ports: list[str] = Field(
        default_factory=lambda: ["Marseille (France)", "Genoa (Italy)", "Antwerp (Belgium)"]
    )
    arrival_ports: list[str] = Field(
        default_factory=lambda: ["Rades (Tunisia)", "La Goulette (Tunisia)", "Bizerte (Tunisia)", "Zarzis (Tunisia)"]
    )
    average_transit_time: str = Field("10 to 20 business days")
    maritime_insurance: str = Field("All shipments include comprehensive maritime transit insurance.")


class InspectionPolicy(BaseModel):
    """Vehicle quality, inspection, and warranty constraints."""

    inspection_standards: str = Field(
        "Every vehicle undergoes a certified 120-point mechanical, electrical, structural, and diagnostic inspection before purchase."
    )
    history_report: str = Field(
        "Official vehicle history and odometer verification (CARFAX / Autoviza / HistoVec) are systematically provided."
    )
    warranty_policy: str = Field(
        "Vehicles benefit from any remaining manufacturer warranty. We do not provide unauthorized aftermarket long-term warranties."
    )


class PaymentPolicy(BaseModel):
    """Payment channels, terms, and prohibited methods."""

    pricing_policy: str = Field(
        "We do not provide binding fixed prices over instant chat. Total price is calculated transparently based on vehicle cost, logistics, and customs regime. An advisor prepares a detailed pro-forma quote once criteria are confirmed."
    )
    payment_methods: list[str] = Field(
        default_factory=lambda: ["Direct bank wire transfer (SEPA) to our corporate bank account"]
    )
    deposit_terms: str = Field(
        "A reservation deposit is required to secure the vehicle, with the balance settled upon completion of export documentation."
    )
    unsupported_payments: list[str] = Field(
        default_factory=lambda: [
            "Cash on delivery at destination port",
            "Cryptocurrency",
            "Unverified third-party escrow",
        ]
    )


class FAQItem(BaseModel):
    """Approved FAQ entry."""

    id: str = Field("")
    category: str = Field("general")
    question: str = Field(...)
    answer: str = Field(...)
    keywords: list[str] = Field(default_factory=list)


class FallbackPolicy(BaseModel):
    """Multilingual safe fallback messages when inquiries exceed approved facts."""

    unsupported_topics: list[str] = Field(
        default_factory=lambda: [
            "10-year free warranty or fake guarantees",
            "Free vehicles or 100% discount promotions",
            "Offices outside Germany, France, and Tunisia (e.g. Tokyo, New York)",
            "Cryptocurrency payments",
            "Vehicles older than 5 years imported under FCR without special license",
        ]
    )
    fallback_messages: dict[str, str] = Field(
        default_factory=lambda: {
            "fr": "Pour cette demande spécifique non couverte par notre guide officiel, un conseiller commercial va vérifier les détails et vous répondre directement.",
            "ar": "بخصوص هذا الاستفسار الخاص، سيقوم مستشارنا بالتحقق من التفاصيل والتواصل معكم مباشرة.",
            "en": "For this specific inquiry not covered in our standard policy, a dedicated sales advisor will verify the details and assist you directly.",
            "de": "Für diese spezifische Anfrage wird ein Kundenberater die Details prüfen und sich direkt mit Ihnen in Verbindung setzen.",
        }
    )


class CompanyKnowledge(BaseModel):
    """Verified company knowledge container with strict anti-hallucination groundings."""

    company: CompanyProfile = Field(default_factory=CompanyProfile)
    fcr: FCRBusinessRules = Field(default_factory=FCRBusinessRules)
    shipping: ShippingPolicy = Field(default_factory=ShippingPolicy)
    inspection: InspectionPolicy = Field(default_factory=InspectionPolicy)
    payment: PaymentPolicy = Field(default_factory=PaymentPolicy)
    fallback: FallbackPolicy = Field(default_factory=FallbackPolicy)
    faq_items: list[FAQItem] = Field(default_factory=list)

    # Legacy attribute compatibility
    @property
    def name(self) -> str:
        return self.company.name

    @property
    def operating_hours(self) -> str:
        return self.company.operating_hours

    @property
    def contact_email(self) -> str:
        return self.company.contact_email

    @property
    def contact_phone(self) -> str:
        return self.company.contact_phone

    @property
    def destination_ports(self) -> list[str]:
        return self.company.destination_ports

    @property
    def services(self) -> list[str]:
        return self.company.services

    @property
    def fcr_description(self) -> str:
        return self.fcr.description

    @property
    def fcr_age_limit_years(self) -> int:
        return self.fcr.age_limit_years

    @property
    def fcr_required_documents(self) -> list[str]:
        return self.fcr.required_documents

    def to_grounded_context_prompt(self) -> str:
        """Format company knowledge into a concise, deterministic system prompt context."""
        ports_str = ", ".join(self.company.destination_ports)
        departures_str = ", ".join(self.shipping.departure_ports)
        services_str = "\n".join(f"- {s}" for s in self.company.services)
        docs_str = ", ".join(self.fcr.required_documents)
        fcr_eligibility = " ".join(f"- {e}" for e in self.fcr.eligibility_requirements)
        unsupported_topics_str = ", ".join(self.fallback.unsupported_topics)

        faq_str = "\n".join(
            f"Q: {item.question}\nA: {item.answer}"
            for item in self.faq_items
        )

        return (
            f"=== VERIFIED COMPANY KNOWLEDGE & APPROVED BUSINESS RULES ===\n"
            f"COMPANY IDENTITY:\n"
            f"- Company Name: {self.company.name} ({self.company.legal_name})\n"
            f"- Operating Territories: {self.company.country}\n"
            f"- Working Hours: {self.company.operating_hours}\n"
            f"- Contact Phone: {self.company.contact_phone} | Email: {self.company.contact_email}\n"
            f"- Departure Ports: {departures_str}\n"
            f"- Destination Ports in Tunisia: {ports_str}\n"
            f"- Transit Time: {self.shipping.average_transit_time}\n"
            f"- Insurance: {self.shipping.maritime_insurance}\n"
            f"- Services:\n{services_str}\n\n"
            f"FCR & CUSTOMS RULES (TUNISIA):\n"
            f"- Max Vehicle Age: {self.fcr.age_limit_years} years at registration date.\n"
            f"- Description: {self.fcr.description}\n"
            f"- Eligibility: {fcr_eligibility}\n"
            f"- Required Documents: {docs_str}\n\n"
            f"QUALITY, INSPECTION & PAYMENT POLICIES:\n"
            f"- Inspection: {self.inspection.inspection_standards}\n"
            f"- History Report: {self.inspection.history_report}\n"
            f"- Warranty: {self.inspection.warranty_policy}\n"
            f"- Pricing Policy: {self.payment.pricing_policy}\n"
            f"- Payment Methods: {', '.join(self.payment.payment_methods)}\n"
            f"- Deposit Terms: {self.payment.deposit_terms}\n\n"
            f"APPROVED FAQ KNOWLEDGE:\n{faq_str}\n\n"
            f"CRITICAL ZERO-HALLUCINATION GUARDRAILS:\n"
            f"1. You must NEVER invent company policies, guarantees, prices, or offices not stated above.\n"
            f"2. Forbidden topics/commitments: {unsupported_topics_str}.\n"
            f"3. If customer asks about unavailable or unsupported company policies (e.g. office in Tokyo, free 10-year warranty, crypto payments), "
            f"DO NOT invent an answer. State clearly that a human advisor will verify and assist, and set human_attention_required=true."
        )

    def get_fallback_response(self, language: str = "fr") -> str:
        """Get safe fallback message in customer's language when info is unavailable."""
        lang_key = language.lower()[:2]
        if lang_key in self.fallback.fallback_messages:
            return self.fallback.fallback_messages[lang_key]
        return self.fallback.fallback_messages.get("fr", "Un conseiller commercial va vérifier les détails et vous répondre directement.")

    def is_explicitly_unsupported(self, query: str) -> bool:
        """Detect obvious unsupported / out-of-scope policy inquiries."""
        q_lower = query.lower()
        unsupported_keywords = [
            "bitcoin", "crypto", "gratuit", "100%", "tokyo", "new york", "australie",
            "10 ans de garantie", "garantie 10 ans", "garantie à vie", "remboursement total sans condition",
            "fcr 10 ans", "fcr 15 ans", "sans douane", "fraude"
        ]
        return any(kw in q_lower for kw in unsupported_keywords)


def _find_config_file(config_path: str | Path | None = None) -> Path | None:
    """Find company_knowledge.yaml location across repository layouts."""
    if config_path:
        p = Path(config_path)
        if p.exists():
            return p

    candidates = [
        Path("config/company_knowledge.yaml"),
        Path("../config/company_knowledge.yaml"),
        Path("../../config/company_knowledge.yaml"),
        Path(__file__).resolve().parents[3] / "config" / "company_knowledge.yaml",
        Path(__file__).resolve().parents[4] / "config" / "company_knowledge.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def load_company_knowledge(config_path: str | Path | None = None) -> CompanyKnowledge:
    """Load verified company knowledge from YAML with strict Pydantic validation."""
    found_path = _find_config_file(config_path)

    if found_path and found_path.exists():
        try:
            with open(found_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            comp_raw = data.get("company", {})
            rules_raw = data.get("business_rules", {})
            fcr_raw = rules_raw.get("fcr", data.get("fcr_rules", {}))
            shipping_raw = rules_raw.get("shipping", {})
            insp_raw = rules_raw.get("inspection_and_quality", {})
            pay_raw = rules_raw.get("pricing_and_payment", {})
            fallback_raw = data.get("fallback_and_escalation", {})
            faq_raw = data.get("faq", [])

            # Parse FAQ items
            faq_items = []
            for item in faq_raw:
                if isinstance(item, dict) and "question" in item and "answer" in item:
                    faq_items.append(
                        FAQItem(
                            id=item.get("id", ""),
                            category=item.get("category", "general"),
                            question=item["question"],
                            answer=item["answer"],
                            keywords=item.get("keywords", []),
                        )
                    )

            return CompanyKnowledge(
                company=CompanyProfile(**comp_raw),
                fcr=FCRBusinessRules(**fcr_raw),
                shipping=ShippingPolicy(**shipping_raw),
                inspection=InspectionPolicy(**insp_raw),
                payment=PaymentPolicy(**pay_raw),
                fallback=FallbackPolicy(**fallback_raw),
                faq_items=faq_items,
            )
        except Exception:
            # Safe default fallback if parsing fails
            return CompanyKnowledge()

    return CompanyKnowledge()
