"""Bounded Multi-Turn Conversation Memory Manager (Phase 3 & Phase 5 Autonomous Agent).

Assembles sliding message window, customer profile, accumulated vehicle specifications,
and explicit missing field directives for conversational collection.
"""

import json
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
from app.models.message import Message
from app.schemas.vehicle_request_state import validate_vehicle_criteria


class ConversationMemoryContext:
    """Bounded conversation memory context container."""

    def __init__(
        self,
        conversation_id: str,
        customer_name: str | None,
        customer_phone: str,
        preferred_language: str,
        fcr_eligible: bool,
        current_state: str,
        draft_criteria: dict[str, Any],
        chat_turns: list[dict[str, str]],
        turn_count: int,
        has_previous_outbound: bool,
    ) -> None:
        self.conversation_id = conversation_id
        self.customer_name = customer_name
        self.customer_phone = customer_phone
        self.preferred_language = preferred_language
        self.fcr_eligible = fcr_eligible
        self.current_state = current_state
        self.draft_criteria = draft_criteria
        self.chat_turns = chat_turns
        self.turn_count = turn_count
        self.has_previous_outbound = has_previous_outbound

    @property
    def is_first_turn(self) -> bool:
        """True if this is the very first inbound message from the customer."""
        return not self.has_previous_outbound and self.turn_count <= 1

    def to_system_prompt_context(self) -> str:
        """Format structured customer profile and active draft criteria for LLM prompt."""
        draft = self.draft_criteria or {}
        validation = validate_vehicle_criteria(draft)
        known_criteria = {k: v for k, v in draft.items() if v is not None and v != "" and k != "missing_fields"}
        known_json = json.dumps(known_criteria, ensure_ascii=False) if known_criteria else "{}"
        missing_list = ", ".join(validation.missing_fields) if validation.missing_fields else "None (All required fields present)"

        greeting_instruction = (
            "CONVERSATION STAGE: INITIAL INCOMING MESSAGE (Turn #1).\n"
            "Provide a warm, polite opening greeting and welcome the customer."
            if self.is_first_turn
            else (
                f"CONVERSATION STAGE: ONGOING DIALOG (Turn #{self.turn_count}).\n"
                "CRITICAL ANTI-GREETING DIRECTIVE: Greetings (Bonjour, Salem, Marhba, Hello) were ALREADY EXCHANGED. "
                "DO NOT START WITH ANY GREETING! Reply DIRECTLY to the customer's message or question."
            )
        )

        collection_directive = (
            "VEHICLE CRITERIA GATHERING DIRECTIVE:\n"
            f"- Known / Already Provided Criteria: {known_json}\n"
            f"- Missing Required Fields Still Needed: [{missing_list}]\n"
            "RULES FOR COLLECTION:\n"
            "1. NEVER re-ask for information that is already present in 'Known Criteria'.\n"
            "2. If the customer updates or corrects a known field (e.g. changes budget, transmission, or model), accept and acknowledge the correction immediately.\n"
            "3. If missing required fields remain, ask conversationally for the next missing piece of information.\n"
            "4. When all required fields are known (Missing Required Fields is None), present a clean, concise structured summary of the criteria and ask the customer to confirm."
        )

        return (
            f"{greeting_instruction}\n\n"
            f"CUSTOMER PROFILE & CONVERSATION STATE:\n"
            f"- Customer Phone: {self.customer_phone}\n"
            f"- Customer Name: {self.customer_name or 'Unspecified'}\n"
            f"- Detected Language: {self.preferred_language}\n"
            f"- FCR Eligible: {'Yes' if self.fcr_eligible else 'Not specified'}\n"
            f"- Current Conversation State: {self.current_state}\n\n"
            f"{collection_directive}\n"
        )


async def load_bounded_conversation_memory(
    db: AsyncSession,
    conversation_id: Any,
    max_recent_messages: int = 15,
    preloaded_conversation: WhatsAppConversation | None = None,
    preloaded_customer: Customer | None = None,
) -> ConversationMemoryContext:
    """Retrieve bounded sliding window of recent messages, customer profile, and active vehicle draft.

    Optimized for high-throughput execution by accepting preloaded entities and limiting DB scans.
    """
    # 1. Fetch conversation if not already in memory
    if preloaded_conversation is not None:
        conv = preloaded_conversation
    else:
        stmt_conv = select(WhatsAppConversation).where(WhatsAppConversation.id == conversation_id)
        conv_res = await db.execute(stmt_conv)
        conv = conv_res.scalar_one_or_none()
        if not conv:
            raise ValueError(f"Conversation '{conversation_id}' not found.")

    # 2. Fetch customer if not already in memory
    if preloaded_customer is not None:
        cust = preloaded_customer
    elif conv.customer_id:
        stmt_cust = select(Customer).where(Customer.id == conv.customer_id)
        cust_res = await db.execute(stmt_cust)
        cust = cust_res.scalar_one_or_none()
    else:
        cust = None

    # 3. Fetch ONLY the recent bounded message window directly via SQL limit
    stmt_msgs = (
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at.desc())
        .limit(max_recent_messages)
    )
    recent_msgs_desc = list((await db.execute(stmt_msgs)).scalars().all())
    # Reverse to chronological order
    recent_msgs = list(reversed(recent_msgs_desc))

    chat_turns: list[dict[str, str]] = []
    turn_count = 0
    has_previous_outbound = False

    for m in recent_msgs:
        is_inbound = m.direction == "Inbound" or str(m.sender_type).lower() == "customer"
        if is_inbound:
            turn_count += 1
            role = "user"
        else:
            has_previous_outbound = True
            role = "model"

        if m.content and m.content.strip():
            chat_turns.append({"role": role, "content": m.content.strip()})

    draft = conv.draft_data or {}

    return ConversationMemoryContext(
        conversation_id=str(conv.id),
        customer_name=cust.full_name if cust else None,
        customer_phone=cust.phone_e164 if cust else "",
        preferred_language=cust.preferred_language if cust else "fr",
        fcr_eligible=cust.fcr_eligible if cust else False,
        current_state=conv.conversation_state or "AI_ACTIVE",
        draft_criteria=draft,
        chat_turns=chat_turns,
        turn_count=turn_count,
        has_previous_outbound=has_previous_outbound,
    )

