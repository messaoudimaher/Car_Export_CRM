"""Unit Test Suite for Deterministic Agent State Machine & Confirmation Engine (Phase 1)."""

import pytest

from app.core.agent_state_machine import (
    ConversationMode,
    ConversationState,
    HandoffReason,
    can_ai_respond,
    compute_deterministic_state_transition,
    is_explicit_confirmation,
    is_explicit_rejection,
)


def test_state_enum_members_and_aliases():
    """Verify all mandatory state machine enum states are defined."""
    assert ConversationState.AI_ACTIVE == "AI_ACTIVE"
    assert ConversationState.WAITING_FOR_CUSTOMER == "WAITING_FOR_CUSTOMER"
    assert ConversationState.COLLECTING_REQUEST == "COLLECTING_REQUEST"
    assert ConversationState.AWAITING_REQUEST_CONFIRMATION == "AWAITING_REQUEST_CONFIRMATION"
    assert ConversationState.QUALIFIED_REQUEST == "QUALIFIED_REQUEST"
    assert ConversationState.NEW_VEHICLE_REQUEST == "QUALIFIED_REQUEST"
    assert ConversationState.HUMAN_ATTENTION == "HUMAN_ATTENTION"
    assert ConversationState.HUMAN_ACTIVE == "HUMAN_ACTIVE"
    assert ConversationState.CLOSED == "CLOSED"


def test_can_ai_respond_policy_isolation():
    """Verify AI automation authorization strictly blocks human takeover and closed threads."""
    # Active AI modes
    assert can_ai_respond(ConversationMode.AI, ConversationState.AI_ACTIVE) is True
    assert can_ai_respond(ConversationMode.AI, ConversationState.COLLECTING_REQUEST) is True
    assert can_ai_respond(ConversationMode.AI, ConversationState.AWAITING_REQUEST_CONFIRMATION) is True
    assert can_ai_respond("AI", "AI_ACTIVE") is True

    # Human Takeover / Active Human Modes MUST disable AI responses
    assert can_ai_respond(ConversationMode.HUMAN, ConversationState.AI_ACTIVE) is False
    assert can_ai_respond(ConversationMode.HUMAN, ConversationState.HUMAN_ACTIVE) is False
    assert can_ai_respond("HUMAN", "HUMAN_ACTIVE") is False
    assert can_ai_respond(ConversationMode.AI, ConversationState.HUMAN_ACTIVE) is False
    assert can_ai_respond(ConversationMode.AI, ConversationState.CLOSED) is False


@pytest.mark.parametrize(
    "text,expected",
    [
        # French confirmations
        ("Oui", True),
        ("oui c'est bon", True),
        ("exactement parfait", True),
        ("D'accord pour valider", True),
        ("Je confirme", True),
        ("tout a fait", True),
        ("absolument", True),
        # English confirmations
        ("yes", True),
        ("yes exactly", True),
        ("that's right, please confirm", True),
        ("sounds good", True),
        ("confirmed", True),
        ("perfect", True),
        # Arabic script confirmations
        ("نعم", True),
        ("صحيح", True),
        ("تمام يا باشا", True),
        ("موافق على المواصفات", True),
        ("ايوة مضبوط", True),
        ("أكيد", True),
        # Tunisian Derja / Arabizi confirmations
        ("ey sahiheh", True),
        ("eywah mrigla", True),
        ("behi d'accord", True),
        ("oumourha mfahem", True),
        ("c bon", True),
        ("mrigel", True),
        ("wadheh", True),
        # German confirmations
        ("ja", True),
        ("genau das passt", True),
        ("stimmt genau", True),
        ("alles klar", True),
        ("einverstanden", True),
        # Non-confirmations / negative / ambiguous phrases
        ("je ne sais pas", False),
        ("non", False),
        ("pas du tout", False),
        ("non c'est pas bon", False),
        ("la mouch heka", False),
        ("nein falsch", False),
        ("combien ça coûte ?", False),
        ("BMW X5 2023", False),
    ],
)
def test_multilingual_confirmation_detection(text: str, expected: bool):
    """Verify explicit confirmation keyword detector across 5 languages."""
    assert is_explicit_confirmation(text) is expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("non", True),
        ("pas du tout", True),
        ("faux", True),
        ("annuler ma demande", True),
        ("no wrong model", True),
        ("cancel", True),
        ("لا غير صحيح", True),
        ("خطأ", True),
        ("le mouch heka", True),
        ("nein falsch", True),
        ("oui c'est bon", False),
        ("yes", False),
        ("BMW X5", False),
    ],
)
def test_multilingual_rejection_detection(text: str, expected: bool):
    """Verify explicit rejection keyword detector across 5 languages."""
    assert is_explicit_rejection(text) is expected


def test_transition_to_collecting_on_partial_criteria():
    """Verify transition from AI_ACTIVE to COLLECTING_REQUEST when criteria are incomplete."""
    res = compute_deterministic_state_transition(
        current_state=ConversationState.AI_ACTIVE,
        intent="VEHICLE_REQUEST",
        text_body="Je cherche une BMW",
        has_vehicle_criteria=True,
        missing_fields=["model", "year", "budget_eur"],
    )
    assert res.next_state == ConversationState.COLLECTING_REQUEST
    assert res.should_qualify_request is False
    assert res.handoff_reason is None


def test_transition_to_awaiting_confirmation_when_all_criteria_present():
    """Verify transition to AWAITING_REQUEST_CONFIRMATION when all required fields are provided."""
    res = compute_deterministic_state_transition(
        current_state=ConversationState.COLLECTING_REQUEST,
        intent="VEHICLE_REQUEST",
        text_body="Golf 8 2022 diesel budget 25000",
        has_vehicle_criteria=True,
        missing_fields=[],
    )
    assert res.next_state == ConversationState.AWAITING_REQUEST_CONFIRMATION
    assert res.should_qualify_request is False


def test_transition_to_qualified_on_explicit_confirmation():
    """Verify transition to QUALIFIED_REQUEST ONLY after explicit customer confirmation."""
    res = compute_deterministic_state_transition(
        current_state=ConversationState.AWAITING_REQUEST_CONFIRMATION,
        intent="CONFIRMATION",
        text_body="Oui tout à fait c'est correct",
        has_vehicle_criteria=True,
        missing_fields=[],
    )
    assert res.next_state == ConversationState.QUALIFIED_REQUEST
    assert res.should_qualify_request is True


def test_transition_rejection_returns_to_collecting():
    """Verify rejecting a summary returns the conversation to COLLECTING_REQUEST."""
    res = compute_deterministic_state_transition(
        current_state=ConversationState.AWAITING_REQUEST_CONFIRMATION,
        intent="REQUEST_UPDATE",
        text_body="Non je veux une Audi Q5 plutôt",
        has_vehicle_criteria=True,
        missing_fields=["budget_eur"],
    )
    assert res.next_state == ConversationState.COLLECTING_REQUEST
    assert res.should_qualify_request is False


def test_human_request_immediate_escalation():
    """Verify explicit human request transitions immediately to HUMAN_ATTENTION."""
    res = compute_deterministic_state_transition(
        current_state=ConversationState.COLLECTING_REQUEST,
        intent="HUMAN_REQUEST",
        text_body="Je veux parler à un conseiller SVP",
        has_vehicle_criteria=True,
        missing_fields=["budget_eur"],
        customer_requested_human=True,
    )
    assert res.next_state == ConversationState.HUMAN_ATTENTION
    assert res.handoff_reason == HandoffReason.CUSTOMER_REQUESTED_HUMAN
    assert res.should_qualify_request is False


def test_price_commitment_request_escalation():
    """Verify requesting binding price quote transitions to HUMAN_ATTENTION."""
    res = compute_deterministic_state_transition(
        current_state=ConversationState.AI_ACTIVE,
        intent="PRICE_REQUEST",
        text_body="Quel est votre prix final avec remise ?",
        has_vehicle_criteria=False,
        missing_fields=[],
        is_price_commitment_request=True,
    )
    assert res.next_state == ConversationState.HUMAN_ATTENTION
    assert res.handoff_reason == HandoffReason.PRICE_REQUEST
    assert res.should_qualify_request is False


def test_faq_preserves_active_collection_state():
    """Verify asking an FAQ in the middle of collection does not reset the collection state."""
    res = compute_deterministic_state_transition(
        current_state=ConversationState.COLLECTING_REQUEST,
        intent="FAQ",
        text_body="Comment fonctionne le FCR ?",
        has_vehicle_criteria=True,
        missing_fields=["budget_eur"],
    )
    assert res.next_state == ConversationState.COLLECTING_REQUEST
    assert res.should_qualify_request is False
