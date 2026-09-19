import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')

from app.core.database import async_session_factory
from sqlalchemy import select
from app.models.conversation import WhatsAppConversation
from app.models.message import Message

async def check():
    async with async_session_factory() as session:
        result = await session.execute(
            select(WhatsAppConversation).order_by(WhatsAppConversation.updated_at.desc()).limit(5)
        )
        convs = result.scalars().all()
        print(f"=== RECENT CONVERSATIONS ({len(convs)}) ===")
        for c in convs:
            print(f"ID: {c.id} | Mode: {c.mode} | State: {c.conversation_state} | Updated: {c.updated_at}")
            msg_res = await session.execute(
                select(Message)
                .where(Message.conversation_id == c.id)
                .order_by(Message.created_at.desc())
                .limit(5)
            )
            msgs = msg_res.scalars().all()
            for m in msgs:
                print(f"   -> [Msg {m.id}] Dir: {m.direction} | Status: {m.delivery_status} | ProviderID: {m.provider_message_id} | Meta: {m.metadata_payload} | Text: {repr(m.content[:80])}")

if __name__ == "__main__":
    asyncio.run(check())
