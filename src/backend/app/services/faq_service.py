"""Grounded FAQ Answering Service with Strict Human Handoff Fallback (Step 2)."""

from typing import Any
from pydantic import BaseModel, Field

from app.ports.llm import LLMCompletionRequest, LLMProvider

# Approved Knowledge Base FAQ Dataset
APPROVED_FAQ_KNOWLEDGE = [
    {
        "topic": "How does vehicle import work?",
        "question_variants": [
            "How does vehicle import work?",
            "Comment fonctionne l'importation de véhicule ?",
            "Kifech l'importation mtaa les voitures?",
            "كيفاش تصير عملية التوريد؟",
        ],
        "approved_answer": (
            "Vehicle import from Europe to Tunisia follows 4 steps: "
            "1. Sourcing and vehicle technical inspection in Europe (Germany/France/Italy). "
            "2. Secure European purchase with VAT deduction (Netto). "
            "3. Ro-Ro shipping to Port of Rades or La Goulette. "
            "4. Customs clearance assistance (standard regime or FCR tax exemption)."
        ),
    },
    {
        "topic": "What information is needed for a request?",
        "question_variants": [
            "What information is needed for a request?",
            "Quelles informations sont nécessaires pour une demande ?",
            "Chnouma les informations elli lezem naatihom?",
            "شنية المعلومات اللازمة لطلب سيارة؟",
        ],
        "approved_answer": (
            "To process your vehicle request, we need: "
            "1. Desired vehicle Make and Model. "
            "2. Production year preference (minimum/maximum). "
            "3. Fuel type (Diesel, Petrol, Hybrid, Electric). "
            "4. Target budget in EUR or TND. "
            "5. Whether you benefit from the FCR customs privilege."
        ),
    },
    {
        "topic": "Do you offer delivery?",
        "question_variants": [
            "Do you offer delivery?",
            "Proposez-vous la livraison ?",
            "Fama livraison f tounes?",
            "هل توفرون خدمة التوصيل؟",
        ],
        "approved_answer": (
            "Yes, we organize insured maritime shipping directly to the Port of Rades or Port of La Goulette. "
            "Optional flatbed transporter delivery to your city or showroom in Tunisia is also available upon customs clearance."
        ),
    },
    {
        "topic": "How can I contact a human agent?",
        "question_variants": [
            "How can I contact a human agent?",
            "Comment puis-je contacter un conseiller humain ?",
            "Nheb nahki maa conseiller?",
            "كيف يمكنني التحدث مع مستشار بشري؟",
        ],
        "approved_answer": (
            "You can contact our human commercial advisors directly via WhatsApp on +216 71 000 000, "
            "or simply ask in this chat and an advisor will be assigned to your conversation immediately."
        ),
    },
    {
        "topic": "What documents may be required?",
        "question_variants": [
            "What documents may be required?",
            "Quels documents peuvent être requis ?",
            "Chnouma les papiers elli lezemhom?",
            "ماهي الوثائق المطلوبة؟",
        ],
        "approved_answer": (
            "Required documents typically include: "
            "1. Copy of National Identity Card (CIN) or Passport. "
            "2. Proof of residence / Consular card (for FCR eligibility if applicable). "
            "3. Customs power of attorney for port clearance. "
            "4. Signed purchase order."
        ),
    },
]

FAQ_GROUNDING_SYSTEM_PROMPT = """You are a strict, grounded FAQ support assistant for a B2B car export CRM.

CRITICAL POLICY & GROUNDING RULES:
1. You MUST answer customer questions ONLY using the facts explicitly provided in the APPROVED FAQ KNOWLEDGE BASE below.
2. If the user question is NOT answered in the Approved FAQ Knowledge Base (e.g. asking about unrelated topics, speculative pricing, cryptocurrency, or unapproved policies), you MUST NOT invent or speculate an answer.
3. If information is missing or out of scope, you MUST reply:
   "Un conseiller humain prendra contact avec vous sous peu pour répondre précisément à votre demande." (or in English: "A human advisor will contact you shortly to answer your request precisely.")
4. NEVER commit to specific car prices or guarantee instant vehicle availability.

APPROVED FAQ KNOWLEDGE BASE:
{faq_context}
"""


class FAQAnswerResult(BaseModel):
    """Structured result of grounded FAQ query."""

    question: str
    answer: str
    is_grounded_in_faq: bool
    human_handoff_triggered: bool
    model: str
    latency_ms: float


class FAQService:
    """Service answering customer queries strictly from approved FAQ knowledge."""

    def __init__(self, llm_provider: LLMProvider) -> None:
        self.llm = llm_provider
        self.faq_context = self._build_faq_context()

    def _build_faq_context(self) -> str:
        blocks = []
        for idx, item in enumerate(APPROVED_FAQ_KNOWLEDGE, start=1):
            blocks.append(f"FAQ #{idx}: {item['topic']}\nApproved Fact: {item['approved_answer']}")
        return "\n\n".join(blocks)

    async def answer_question(self, user_question: str) -> FAQAnswerResult:
        """Answer question strictly based on approved knowledge, falling back to human handoff."""
        system_prompt = FAQ_GROUNDING_SYSTEM_PROMPT.format(faq_context=self.faq_context)
        req = LLMCompletionRequest(
            prompt=f"Customer Inquiry: {user_question}\nAnswer:",
            system_prompt=system_prompt,
            temperature=0.0,
        )
        res = await self.llm.generate_text(req)
        answer_text = res.content.strip()

        # Check if response triggered human handoff
        handoff_keywords = [
            "conseiller humain",
            "human advisor",
            "human agent",
            "advisor will contact",
            "agent will contact",
            "مستشار",
            "follow up",
            "suivi",
            "shortly to answer",
        ]
        lower_ans = answer_text.lower()
        human_handoff = any(kw in lower_ans for kw in handoff_keywords)
        is_grounded = not human_handoff

        return FAQAnswerResult(
            question=user_question,
            answer=answer_text,
            is_grounded_in_faq=is_grounded,
            human_handoff_triggered=human_handoff,
            model=res.model,
            latency_ms=res.latency_ms,
        )
