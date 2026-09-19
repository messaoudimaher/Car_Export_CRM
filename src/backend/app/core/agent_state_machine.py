"""Agent State Machine & Handoff Policy Engine.

Governs deterministic conversation state transitions, mode isolation (AI vs HUMAN),
and human takeover / resume control loops.
"""

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
    NEW_VEHICLE_REQUEST = "NEW_VEHICLE_REQUEST"
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


CONFIRMATION_KEYWORDS = {
    "fr": {"oui", "correct", "d'accord", "exactement", "valider", "parfait", "c'est bon", "ok", "daccord", "confirme"},
    "en": {"yes", "correct", "confirm", "exactly", "that's right", "right", "ok", "sure", "sounds good"},
    "ar": {"نعم", "صحيح", "واضح", "موافق", "تأكيد", "باشا", "ايوة", "إيوه", "سليم"},
    "derja": {"oui", "sahiheh", "ey", "eywah", "oumourha", "mfahem", "behi", "mriyah", "d'accord", "ok"},
}


def is_explicit_confirmation(text: str) -> bool:
    """Check if customer response constitutes explicit confirmation of summarized requirements."""
    cleaned = text.strip().lower()
    # Check for direct keyword matches or contains
    for lang_set in CONFIRMATION_KEYWORDS.values():
        for kw in lang_set:
            if kw == cleaned or cleaned.startswith(kw) or cleaned.endswith(kw):
                return True
    return False


def can_ai_respond(mode: str | ConversationMode, state: str | ConversationState) -> bool:
    """Check if AI auto-reply is authorized for current conversation mode and state."""
    mode_str = mode.value if isinstance(mode, ConversationMode) else str(mode)
    state_str = state.value if isinstance(state, ConversationState) else str(state)

    if mode_str == ConversationMode.HUMAN.value or state_str == ConversationState.HUMAN_ACTIVE.value:
        return False
    return True
