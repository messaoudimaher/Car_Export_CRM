"""Conversation & Inbox REST API v1 Endpoints (ADR 0008, ADR 0009, TASK-0703)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentUser,
    get_current_tenant_id,
    get_whatsapp_provider,
    require_roles,
)
from app.core.database import get_db_session
from app.core.errors import ValidationException
from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
from app.models.message import Message
from app.models.user import UserRole
from app.ports.whatsapp import WhatsAppProvider
from app.schemas.conversation import (
    ConversationAssignRequest,
    ConversationEnvelope,
    ConversationListEnvelope,
    ConversationListMeta,
    ConversationResponse,
    MessageCreateRequest,
    MessageEnvelope,
    MessageListEnvelope,
    MessageListMeta,
    MessageResponse,
)
from app.services.conversation_service import (
    ConversationService,
    MessageDeliveryStatus,
    MessageDirection,
    MessageSenderType,
)

router = APIRouter(prefix="/conversations", tags=["Conversations"])

ALLOWED_CONVERSATION_QUERY_PARAMS = {
    "status",
    "assigned_agent_id",
    "cursor",
    "limit",
}

ALLOWED_MESSAGE_QUERY_PARAMS = {
    "cursor",
    "limit",
}


@router.get("", response_model=ConversationListEnvelope, status_code=status.HTTP_200_OK)
async def list_conversations(
    request: Request,
    status_param: str | None = Query(None, alias="status", description="Status filter"),
    assigned_agent_id: str | None = Query(None, description="Agent UUID filter or 'unassigned'"),
    cursor: str | None = Query(None, description="Base64 cursor"),
    limit: int = Query(25, ge=1, le=100, description="Page limit (1-100)"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(
        require_roles(
            UserRole.SUPER_ADMIN,
            UserRole.TENANT_ADMIN,
            UserRole.SALES_AGENT,
            UserRole.LOGISTICS_AGENT,
        )
    ),
) -> ConversationListEnvelope:
    """List operational inbox conversations with status/assignment filters and cursor pagination."""
    unrecognized = set(request.query_params.keys()) - ALLOWED_CONVERSATION_QUERY_PARAMS
    if unrecognized:
        raise ValidationException(f"Unrecognized query parameter(s): {sorted(list(unrecognized))}.")

    base_stmt = select(WhatsAppConversation).where(WhatsAppConversation.tenant_id == tenant_id)

    if status_param:
        base_stmt = base_stmt.where(WhatsAppConversation.status == status_param)

    if assigned_agent_id:
        if assigned_agent_id.lower() == "unassigned":
            base_stmt = base_stmt.where(WhatsAppConversation.assigned_agent_id.is_(None))
        else:
            try:
                agent_uuid = UUID(assigned_agent_id)
                base_stmt = base_stmt.where(WhatsAppConversation.assigned_agent_id == agent_uuid)
            except ValueError as e:
                raise ValidationException("Invalid assigned_agent_id parameter format.") from e

    total_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_count = await session.scalar(total_stmt) or 0

    query_stmt = base_stmt
    if cursor:
        from app.utils.pagination import decode_cursor

        cursor_last_msg_at, cursor_id = decode_cursor(cursor)
        query_stmt = query_stmt.where(
            or_(
                WhatsAppConversation.last_message_at < cursor_last_msg_at,
                (WhatsAppConversation.last_message_at == cursor_last_msg_at)
                & (WhatsAppConversation.id < cursor_id),
            )
        )

    query_stmt = query_stmt.order_by(
        WhatsAppConversation.last_message_at.desc(), WhatsAppConversation.id.desc()
    ).limit(limit + 1)
    results = list((await session.execute(query_stmt)).scalars().all())

    has_next = len(results) > limit
    items = results[:limit]

    next_cursor = None
    if has_next and items:
        from app.utils.pagination import encode_cursor

        next_cursor = encode_cursor(items[-1].last_message_at, items[-1].id)

    data: list[ConversationResponse] = []
    for c in items:
        resp = ConversationResponse.model_validate(c)
        # Fetch customer info
        cust = await session.get(Customer, c.customer_id)
        if cust:
            resp.customer_name = cust.full_name
            resp.customer_phone_e164 = cust.phone_e164

        # Fetch latest message snippet
        last_msg_stmt = (
            select(Message)
            .where(Message.conversation_id == c.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        last_msg = (await session.execute(last_msg_stmt)).scalars().first()
        if last_msg:
            resp.last_message_content = last_msg.content

        # Fetch active AI understanding & suggestion
        from app.models.ai_understanding import AIUnderstanding
        from app.models.ai_suggestion import AISuggestion
        und_stmt = (
            select(AIUnderstanding)
            .where(AIUnderstanding.conversation_id == c.id)
            .order_by(AIUnderstanding.created_at.desc())
            .limit(1)
        )
        und = (await session.execute(und_stmt)).scalars().first()
        if und:
            ext = und.extracted_data_jsonb or {}
            resp.active_ai_understanding = {
                "id": str(und.id),
                "intent": und.intent,
                "confidenceScore": float(und.confidence_score or 0.95),
                "extractedVehicleModel": f"{ext.get('make', '')} {ext.get('model', '')}".strip() or None,
                "extractedYearMin": ext.get("year"),
                "extractedYearMax": ext.get("year"),
                "extractedBudgetMinEur": ext.get("budget_eur"),
                "extractedBudgetMaxEur": ext.get("budget_eur"),
                "extractedFcrEligible": ext.get("fcr_eligible", True),
                "summaryFr": und.summary_fr,
                "status": und.status,
            }

        sug_stmt = (
            select(AISuggestion)
            .where(AISuggestion.conversation_id == c.id)
            .order_by(AISuggestion.created_at.desc())
            .limit(1)
        )
        sug = (await session.execute(sug_stmt)).scalars().first()
        if sug:
            resp.active_ai_suggestion = {
                "id": str(sug.id),
                "suggestedText": sug.suggested_text,
                "confidenceScore": 0.92,
                "status": sug.status,
            }

        data.append(resp)

    meta = ConversationListMeta(
        limit=limit,
        has_next=has_next,
        next_cursor=next_cursor,
        total=total_count,
    )
    return ConversationListEnvelope(success=True, data=data, meta=meta)


@router.get("/{id}", response_model=ConversationEnvelope, status_code=status.HTTP_200_OK)
async def get_conversation(
    id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(
        require_roles(
            UserRole.SUPER_ADMIN,
            UserRole.TENANT_ADMIN,
            UserRole.SALES_AGENT,
            UserRole.LOGISTICS_AGENT,
        )
    ),
) -> ConversationEnvelope:
    """Fetch conversation thread details strictly scoped to tenant context."""
    service = ConversationService(session, tenant_id)
    updated_conv = await service.mark_as_read(id)
    return ConversationEnvelope(
        success=True, data=ConversationResponse.model_validate(updated_conv)
    )


@router.get("/human-attention", response_model=ConversationListEnvelope, status_code=status.HTTP_200_OK)
async def list_human_attention_conversations(
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(
        require_roles(
            UserRole.SUPER_ADMIN,
            UserRole.TENANT_ADMIN,
            UserRole.SALES_AGENT,
            UserRole.LOGISTICS_AGENT,
        )
    ),
) -> ConversationListEnvelope:
    """Retrieve all conversations requiring human attention or active human takeover."""
    stmt = (
        select(WhatsAppConversation)
        .where(
            WhatsAppConversation.tenant_id == tenant_id,
            or_(
                WhatsAppConversation.conversation_state == "HUMAN_ATTENTION",
                WhatsAppConversation.mode == "HUMAN",
                WhatsAppConversation.conversation_state == "HUMAN_ACTIVE",
            ),
        )
        .order_by(WhatsAppConversation.last_message_at.desc())
    )
    results = list((await session.execute(stmt)).scalars().all())

    data: list[ConversationResponse] = []
    for c in results:
        resp = ConversationResponse.model_validate(c)
        cust = await session.get(Customer, c.customer_id)
        if cust:
            resp.customer_name = cust.full_name
            resp.customer_phone_e164 = cust.phone_e164

        last_msg_stmt = (
            select(Message)
            .where(Message.conversation_id == c.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        last_msg = (await session.execute(last_msg_stmt)).scalars().first()
        if last_msg:
            resp.last_message_content = last_msg.content

        data.append(resp)

    meta = ConversationListMeta(
        limit=len(data),
        has_next=False,
        next_cursor=None,
        total=len(data),
    )
    return ConversationListEnvelope(success=True, data=data, meta=meta)


@router.post("/{id}/takeover", response_model=ConversationEnvelope, status_code=status.HTTP_200_OK)
async def takeover_conversation(
    id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(
        require_roles(
            UserRole.SUPER_ADMIN,
            UserRole.TENANT_ADMIN,
            UserRole.SALES_AGENT,
        )
    ),
) -> ConversationEnvelope:
    """Admin human takeover action. Halts automatic AI replies completely (mode=HUMAN)."""
    stmt = select(WhatsAppConversation).where(
        WhatsAppConversation.id == id, WhatsAppConversation.tenant_id == tenant_id
    )
    conv = (await session.execute(stmt)).scalar_one_or_none()
    if not conv:
        raise ValidationException("Conversation not found under current tenant context.")

    conv.mode = "HUMAN"
    conv.conversation_state = "HUMAN_ACTIVE"
    conv.assigned_agent_id = current_user.user_id
    await session.commit()
    await session.refresh(conv)

    from app.core.ws_manager import ws_manager
    await ws_manager.broadcast_to_tenant(
        tenant_id=tenant_id,
        event_type="CONVERSATION_TAKEOVER",
        data={"conversation_id": str(id), "mode": "HUMAN", "agent_id": str(current_user.user_id)},
    )

    resp = ConversationResponse.model_validate(conv)
    cust = await session.get(Customer, conv.customer_id)
    if cust:
        resp.customer_name = cust.full_name
        resp.customer_phone_e164 = cust.phone_e164

    return ConversationEnvelope(success=True, data=resp)


@router.post("/{id}/resume-ai", response_model=ConversationEnvelope, status_code=status.HTTP_200_OK)
async def resume_ai_conversation(
    id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(
        require_roles(
            UserRole.SUPER_ADMIN,
            UserRole.TENANT_ADMIN,
            UserRole.SALES_AGENT,
        )
    ),
) -> ConversationEnvelope:
    """Admin action to resume autonomous AI handling for conversation (mode=AI)."""
    stmt = select(WhatsAppConversation).where(
        WhatsAppConversation.id == id, WhatsAppConversation.tenant_id == tenant_id
    )
    conv = (await session.execute(stmt)).scalar_one_or_none()
    if not conv:
        raise ValidationException("Conversation not found under current tenant context.")

    conv.mode = "AI"
    conv.conversation_state = "AI_ACTIVE"
    conv.handoff_reason = None
    conv.handoff_summary = None
    await session.commit()
    await session.refresh(conv)

    from app.core.ws_manager import ws_manager
    await ws_manager.broadcast_to_tenant(
        tenant_id=tenant_id,
        event_type="CONVERSATION_RESUME_AI",
        data={"conversation_id": str(id), "mode": "AI"},
    )

    resp = ConversationResponse.model_validate(conv)
    cust = await session.get(Customer, conv.customer_id)
    if cust:
        resp.customer_name = cust.full_name
        resp.customer_phone_e164 = cust.phone_e164

    return ConversationEnvelope(success=True, data=resp)


@router.post("/{id}/assign", response_model=ConversationEnvelope, status_code=status.HTTP_200_OK)
async def assign_conversation(
    id: UUID,
    payload: ConversationAssignRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(
        require_roles(
            UserRole.SUPER_ADMIN,
            UserRole.TENANT_ADMIN,
            UserRole.SALES_AGENT,
        )
    ),
) -> ConversationEnvelope:
    """Claim or reassign a conversation thread to a sales representative (FR-INBOX-002)."""
    service = ConversationService(session, tenant_id)
    updated = await service.assign_agent(
        conversation_id=id,
        agent_id=payload.agent_id,
        assigned_by_user_id=current_user.user_id,
    )
    return ConversationEnvelope(success=True, data=ConversationResponse.model_validate(updated))


@router.get(
    "/{id}/messages",
    response_model=MessageListEnvelope,
    status_code=status.HTTP_200_OK,
)
async def get_messages(
    id: UUID,
    request: Request,
    cursor: str | None = Query(None, description="Base64 cursor"),
    limit: int = Query(50, ge=1, le=100, description="Page limit (1-100)"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(
        require_roles(
            UserRole.SUPER_ADMIN,
            UserRole.TENANT_ADMIN,
            UserRole.SALES_AGENT,
            UserRole.LOGISTICS_AGENT,
        )
    ),
) -> MessageListEnvelope:
    """Retrieve chronologically ordered message history timeline for a conversation thread."""
    unrecognized = set(request.query_params.keys()) - ALLOWED_MESSAGE_QUERY_PARAMS
    if unrecognized:
        raise ValidationException(f"Unrecognized query parameter(s): {sorted(list(unrecognized))}.")

    service = ConversationService(session, tenant_id)
    await service.get_conversation(id)

    base_stmt = (
        select(Message).where(Message.tenant_id == tenant_id).where(Message.conversation_id == id)
    )

    total_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_count = await session.scalar(total_stmt) or 0

    query_stmt = base_stmt
    if cursor:
        from app.utils.pagination import decode_cursor

        cursor_created_at, cursor_id = decode_cursor(cursor)
        query_stmt = query_stmt.where(
            or_(
                Message.created_at < cursor_created_at,
                (Message.created_at == cursor_created_at) & (Message.id < cursor_id),
            )
        )

    query_stmt = query_stmt.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1)
    results = list((await session.execute(query_stmt)).scalars().all())

    has_next = len(results) > limit
    items = results[:limit]

    next_cursor = None
    if has_next and items:
        from app.utils.pagination import encode_cursor

        next_cursor = encode_cursor(items[-1].created_at, items[-1].id)

    # Convert items to ASC timeline order for frontend rendering
    timeline_items = list(reversed(items))
    data = [MessageResponse.model_validate(m) for m in timeline_items]

    meta = MessageListMeta(
        limit=limit,
        has_next=has_next,
        next_cursor=next_cursor,
        total=total_count,
    )
    return MessageListEnvelope(success=True, data=data, meta=meta)


@router.post(
    "/{id}/messages",
    response_model=MessageEnvelope,
    status_code=status.HTTP_201_CREATED,
)
async def post_message(
    id: UUID,
    payload: MessageCreateRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    provider: WhatsAppProvider = Depends(get_whatsapp_provider),
    current_user: CurrentUser = Depends(
        require_roles(
            UserRole.SUPER_ADMIN,
            UserRole.TENANT_ADMIN,
            UserRole.SALES_AGENT,
        )
    ),
) -> MessageEnvelope:
    """Dispatch an outbound WhatsApp message to the customer (FR-MSG-001)."""
    service = ConversationService(session, tenant_id)
    conversation = await service.get_conversation(id)

    # Retrieve customer profile to get E.164 phone number
    customer = await session.get(Customer, conversation.customer_id)
    if not customer:
        raise ValidationException("Associated customer profile not found.")

    # Retrieve WhatsAppAccount for tenant to obtain phone_number_id
    from app.core.config import settings
    from app.models.whatsapp_account import WhatsAppAccount

    wa_account_stmt = select(WhatsAppAccount).where(WhatsAppAccount.tenant_id == tenant_id)
    wa_account = (await session.execute(wa_account_stmt)).scalars().first()
    phone_number_id = (
        settings.META_WHATSAPP_PHONE_NUMBER_ID
        or (wa_account.phone_number_id if wa_account else "default_phone_number_id")
    )

    # Dispatch message via WhatsAppProvider adapter
    send_result = await provider.send_text_message(
        phone_number_id=phone_number_id,
        recipient_e164=customer.phone_e164,
        text_body=payload.content,
    )

    created_message = await service.add_message(
        conversation_id=id,
        direction=MessageDirection.OUTBOUND,
        sender_type=MessageSenderType.AGENT,
        content=payload.content,
        message_type=payload.message_type,
        provider_message_id=send_result.wamid,
        sender_user_id=current_user.user_id,
        media_url=payload.media_url,
        delivery_status=MessageDeliveryStatus.SENT,
        metadata={
            "idempotency_key": idempotency_key,
            "provider_result": send_result.model_dump(),
        },
    )

    msg_response = MessageResponse.model_validate(created_message)

    from app.core.ws_manager import ws_manager

    await ws_manager.broadcast_to_tenant(
        tenant_id=tenant_id,
        event_type="INBOX_MESSAGE_RECEIVED",
        data=msg_response.model_dump(mode="json"),
    )

    return MessageEnvelope(success=True, data=msg_response)
