"""Agent State Machine & Deterministic Handoff Policy Engine (Phase 1 Domain Foundation).

Governs deterministic conversation state transitions, mode isolation (AI vs HUMAN),
multilingual explicit confirmation checking, and human takeover / resume control loops.
"""

import re
from enum import Enum
from typing import Any


class ConversationMode(str, Enum):
    """Operational conversation mode controlling AI automation."""

    AI = "AI"
    HUMAN = "HUMAN"


class ConversationState(str, Enum):
    """Deterministic conversation lifecycle states."""

    AI_ACTIVE = "AI_ACTIVE"
    WAITING_FOR_CUSTOMER = "WAITING_FOR_CUSTOMER"
    COLLECTING_REQUEST = "COLLECTING_REQUEST"
    AWAITING_REQUEST_CONFIRMATION = "AWAITING_REQUEST_CONFIRMATION"
    QUALIFIED_REQUEST = "QUALIFIED_REQUEST"
    NEW_VEHICLE_REQUEST = "QUALIFIED_REQUEST"  # Backward-compatible alias
    HUMAN_ATTENTION = "HUMAN_ATTENTION"
    HUMAN_ACTIVE = "HUMAN_ACTIVE"
    CLOSED = "CLOSED"


class HandoffReason(str, Enum):
    """Specific reasons for human handoff escalation."""

    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    PRICE_REQUEST = "PRICE_REQUEST"
    CUSTOMER_REQUESTED_HUMAN = "CUSTOMER_REQUESTED_HUMAN"
    UNSUPPORTED_QUESTION = "UNSUPPORTED_QUESTION"
    COMPLAINT = "COMPLAINT"
    AMBIGUOUS_REQUEST = "AMBIGUOUS_REQUEST"
    BUSINESS_DECISION_REQUIRED = "BUSINESS_DECISION_REQUIRED"
    POLICY_UNCERTAINTY = "POLICY_UNCERTAINTY"
    TECHNICAL_ERROR = "TECHNICAL_ERROR"


# Multilingual confirmation keyword dictionary (FR, EN, AR, Derja, DE)
CONFIRMATION_KEYWORDS: dict[str, set[str]] = {
    "fr": {
        "oui",
        "correct",
        "d'accord",
        "exactement",
        "valider",
        "parfait",
        "c'est bon",
        "ok",
        "daccord",
        "confirme",
        "bon",
        "tout a fait",
        "tout à fait",
        "absolument",
        "bien sur",
        "bien sûr",
        "confirmer",
    },
    "en": {
        "yes",
        "correct",
        "confirm",
        "confirmed",
        "exactly",
        "right",
        "that's right",
        "ok",
        "sure",
        "sounds good",
        "perfect",
        "yep",
        "yeah",
        "affirmative",
    },
    "ar": {
        "نعم",
        "صحيح",
        "واضح",
        "موافق",
        "تأكيد",
        "باشا",
        "ايوة",
        "إيوه",
        "سليم",
        "تمام",
        "أكيد",
        "اكيد",
        "مضبوط",
        "تمام يا باشا",
    },
    "derja": {
        "oui",
        "sahiheh",
        "ey",
        "eywah",
        "oumourha",
        "mfahem",
        "behi",
        "mriyah",
        "d'accord",
        "ok",
        "tamam",
        "tmm",
        "c bon",
        "cbon",
        "marhba",
        "aywa",
        "mrigla",
        "mrigel",
        "wadheh",
    },
    "de": {
        "ja",
        "genau",
        "stimmt",
        "richtig",
        "einverstanden",
        "bestätigen",
        "bestätigt",
        "alles klar",
        "passt",
        "in ordnung",
    },
}

# Multilingual rejection / negative keywords
REJECTION_KEYWORDS: dict[str, set[str]] = {
    "fr": {
        "non",
        "pas du tout",
        "faux",
        "annuler",
        "incorrect",
        "arreter",
        "arrêter",
        "pas d'accord",
        "mauvais",
    },
    "en": {
        "no",
        "not right",
        "wrong",
        "cancel",
        "incorrect",
        "stop",
        "nope",
        "not really",
        "negative",
    },
    "ar": {
        "لا",
        "غير صحيح",
        "خطأ",
        "الغاء",
        "وقف",
        "مش مظبوط",
        "كلا",
    },
    "derja": {
        "le",
        "la",
        "mouch sahih",
        "batal",
        "ghalet",
        "mouch heka",
        "laa",
    },
    "de": {
        "nein",
        "falsch",
        "nicht",
        "abbrechen",
        "stop",
        "nicht korrekt",
    },
}


# Multilingual human representative keywords
HUMAN_REQUEST_KEYWORDS: dict[str, set[str]] = {
    "fr": {
        "parler a un humain",
        "parler à un humain",
        "parler a un conseiller",
        "parler à un conseiller",
        "parler a un agent",
        "parler à un agent",
        "agent humain",
        "humain",
        "conseiller",
        "responsable",
        "telephone",
        "téléphone",
        "appeler",
        "contactez moi",
        "joindre quelqu'un",
    },
    "en": {
        "human",
        "human agent",
        "real person",
        "talk to human",
        "speak to a person",
        "representative",
        "customer service",
        "call me",
        "support agent",
    },
    "ar": {
        "انسان",
        "بشري",
        "موظف",
        "خدمة العملاء",
        "مسؤول",
        "اتصل بي",
        "مكالمة",
        "تحدث مع شخص",
        "مندوب",
    },
    "derja": {
        "rajil",
        "wehed",
        "mouch robot",
        "kallamni",
        "aayetli",
        "responsable",
        "conseiller",
        "khadem",
    },
    "de": {
        "mensch",
        "berater",
        "mitarbeiter",
        "kundenservice",
        "anrufen",
        "telefon",
        "menschlicher support",
    },
}

# Multilingual complaint / dispute keywords
COMPLAINT_KEYWORDS: dict[str, set[str]] = {
    "fr": {
        "plainte",
        "reclamation",
        "réclamation",
        "mécontent",
        "mecontent",
        "arnaque",
        "escroquerie",
        "voleur",
        "mauvais service",
        "inacceptable",
        "scandale",
    },
    "en": {
        "complaint",
        "scam",
        "fraud",
        "unhappy",
        "terrible service",
        "horrible",
        "awful",
        "bad experience",
        "cheat",
        "lawyer",
    },
    "ar": {
        "شكوى",
        "نصب",
        "احتيال",
        "خدمة سيئة",
        "غير راض",
        "سرقة",
        "كذاب",
        "نصاب",
    },
    "derja": {
        "khayba",
        "sarqa",
        "qelleb",
        "ghachech",
        "service zero",
        "mouch behya",
    },
    "de": {
        "beschwerde",
        "betrug",
        "unzufrieden",
        "schlechter service",
        "abzocke",
        "anwalt",
    },
}


def is_human_requested(text: str) -> bool:
    """Check if customer message contains an explicit request for human assistance."""
    cleaned = text.strip().lower()
    if not cleaned:
        return False
    for lang_set in HUMAN_REQUEST_KEYWORDS.values():
        for kw in lang_set:
            if kw in cleaned:
                return True
    return False


def is_complaint_message(text: str) -> bool:
    """Check if customer message indicates a complaint or serious dissatisfaction."""
    cleaned = text.strip().lower()
    if not cleaned:
        return False
    for lang_set in COMPLAINT_KEYWORDS.values():
        for kw in lang_set:
            if kw in cleaned:
                return True
    return False


def is_explicit_confirmation(text: str) -> bool:
    """Check if customer response constitutes explicit confirmation of summarized requirements."""
    cleaned = text.strip().lower()
    if not cleaned:
        return False

    # Check for direct word presence across all supported languages
    for lang_set in CONFIRMATION_KEYWORDS.values():
        for kw in lang_set:
            pattern = r"(?:\b|^)" + re.escape(kw) + r"(?:\b|$)"
            if re.search(pattern, cleaned, flags=re.IGNORECASE):
                # Ensure it is not a negative phrase like "non ce n'est pas bon"
                if not is_explicit_rejection(cleaned):
                    return True
    return False


def is_explicit_rejection(text: str) -> bool:
    """Check if customer response explicitly rejects or negates the summarized requirements."""
    cleaned = text.strip().lower()
    if not cleaned:
        return False

    for lang_set in REJECTION_KEYWORDS.values():
        for kw in lang_set:
            pattern = r"(?:\b|^)" + re.escape(kw) + r"(?:\b|$)"
            if re.search(pattern, cleaned, flags=re.IGNORECASE):
                return True
    return False


def can_ai_respond(mode: str | ConversationMode, state: str | ConversationState) -> bool:
    """Check if AI auto-reply is authorized for current conversation mode and state."""
    mode_str = mode.value if isinstance(mode, ConversationMode) else str(mode)
    state_str = state.value if isinstance(state, ConversationState) else str(state)

    if mode_str == ConversationMode.HUMAN.value:
        return False
    if state_str in (ConversationState.HUMAN_ACTIVE.value, ConversationState.CLOSED.value):
        return False
    return True


class StateTransitionResult:
    """Encapsulates outcome of a deterministic state machine transition."""

    def __init__(
        self,
        next_state: ConversationState,
        handoff_reason: HandoffReason | None = None,
        should_qualify_request: bool = False,
        summary_note: str | None = None,
    ) -> None:
        self.next_state = next_state
        self.handoff_reason = handoff_reason
        self.should_qualify_request = should_qualify_request
        self.summary_note = summary_note


def compute_deterministic_state_transition(
    current_state: ConversationState | str,
    intent: str,
    text_body: str,
    has_vehicle_criteria: bool,
    missing_fields: list[str],
    customer_requested_human: bool = False,
    is_price_commitment_request: bool = False,
    has_active_unconfirmed_summary: bool = False,
    is_unsupported_question: bool = False,
    is_complaint: bool = False,
    is_ambiguous: bool = False,
    is_technical_error: bool = False,
    is_business_decision: bool = False,
) -> StateTransitionResult:
    """Compute the next conversation state deterministically based on verified backend business rules.

    The LLM outputs are treated as proposals; the backend determines the authoritative state transition.
    """
    state_enum = (
        current_state
        if isinstance(current_state, ConversationState)
        else ConversationState(str(current_state))
    )

    # 1. Immediate human escalation triggers (Strictly for exceptions)
    if is_technical_error:
        return StateTransitionResult(
            next_state=ConversationState.HUMAN_ATTENTION,
            handoff_reason=HandoffReason.TECHNICAL_ERROR,
            summary_note="Technical processing failure; escalated for manual advisor review.",
        )

    if is_unsupported_question:
        return StateTransitionResult(
            next_state=ConversationState.HUMAN_ATTENTION,
            handoff_reason=HandoffReason.UNSUPPORTED_QUESTION,
            summary_note="Inquiry outside approved company knowledge base or policy rules.",
        )

    if customer_requested_human:
        return StateTransitionResult(
            next_state=ConversationState.HUMAN_ATTENTION,
            handoff_reason=HandoffReason.CUSTOMER_REQUESTED_HUMAN,
            summary_note="Customer explicitly requested human sales representative.",
        )

    if is_complaint:
        return StateTransitionResult(
            next_state=ConversationState.HUMAN_ATTENTION,
            handoff_reason=HandoffReason.COMPLAINT,
            summary_note="Customer complaint or serious dispute detected.",
        )

    if is_price_commitment_request:
        return StateTransitionResult(
            next_state=ConversationState.HUMAN_ATTENTION,
            handoff_reason=HandoffReason.PRICE_REQUEST,
            summary_note="Customer requested binding pricing or discount commitment.",
        )

    if is_business_decision:
        return StateTransitionResult(
            next_state=ConversationState.HUMAN_ATTENTION,
            handoff_reason=HandoffReason.BUSINESS_DECISION_REQUIRED,
            summary_note="Inquiry requires business approval or custom financing.",
        )

    if is_ambiguous:
        return StateTransitionResult(
            next_state=ConversationState.HUMAN_ATTENTION,
            handoff_reason=HandoffReason.AMBIGUOUS_REQUEST,
            summary_note="Unresolved ambiguity or repetitive incomprehensible input.",
        )

    # 2. Check for explicit confirmation or rejection
    customer_confirmed = is_explicit_confirmation(text_body)
    customer_rejected = is_explicit_rejection(text_body)

    if state_enum == ConversationState.AWAITING_REQUEST_CONFIRMATION:
        if customer_confirmed:
            return StateTransitionResult(
                next_state=ConversationState.QUALIFIED_REQUEST,
                should_qualify_request=True,
                summary_note="Customer explicitly confirmed vehicle request summary.",
            )
        if customer_rejected:
            return StateTransitionResult(
                next_state=ConversationState.COLLECTING_REQUEST,
                should_qualify_request=False,
                summary_note="Customer rejected summary; returning to criteria collection.",
            )

    # Also handle confirmation if criteria are complete and user explicitly confirms
    if customer_confirmed and has_vehicle_criteria and not missing_fields:
        return StateTransitionResult(
            next_state=ConversationState.QUALIFIED_REQUEST,
            should_qualify_request=True,
            summary_note="Customer confirmed complete vehicle criteria.",
        )

    # 3. Vehicle request collection lifecycle
    if intent in ("VEHICLE_REQUEST", "REQUEST_UPDATE") or has_vehicle_criteria:
        if not missing_fields:
            # All required fields are present -> present summary and await confirmation
            return StateTransitionResult(
                next_state=ConversationState.AWAITING_REQUEST_CONFIRMATION,
                should_qualify_request=False,
                summary_note="All vehicle specifications gathered; awaiting explicit confirmation.",
            )
        # Criteria incomplete -> keep collecting
        return StateTransitionResult(
            next_state=ConversationState.COLLECTING_REQUEST,
            should_qualify_request=False,
            summary_note=f"Gathering missing criteria: {missing_fields}",
        )

    # 4. FAQ / General Conversation
    if intent == "FAQ":
        # Preserve existing collection state if customer asked an FAQ mid-flow
        if state_enum in (
            ConversationState.COLLECTING_REQUEST,
            ConversationState.AWAITING_REQUEST_CONFIRMATION,
        ):
            return StateTransitionResult(
                next_state=state_enum,
                should_qualify_request=False,
                summary_note="Customer asked FAQ during vehicle collection; preserved state.",
            )
        return StateTransitionResult(
            next_state=ConversationState.AI_ACTIVE,
            should_qualify_request=False,
        )

    # 5. Default fallback
    return StateTransitionResult(
        next_state=state_enum,
        should_qualify_request=False,
    )
