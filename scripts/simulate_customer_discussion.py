"""Simulate realistic customer WhatsApp discussion with live AI understanding and suggestion.

Usage:
  cd src/backend
  uv run python ../../scripts/simulate_customer_discussion.py
"""

import asyncio
import json
from pathlib import Path
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "backend"))

import httpx
from sqlalchemy import select

from app.adapters.llm_gemini import GeminiAdapter
from app.core.database import async_session_factory
from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
from app.models.message import Message
from app.models.tenant import Tenant
from app.models.whatsapp_account import WhatsAppAccount
from app.ports.llm import LLMCompletionRequest
from app.schemas.vehicle_request_extraction import VehicleRequestExtraction, validate_vehicle_request
from app.utils.uuid import generate_uuidv7


async def simulate_live_discussion() -> None:
    print("\n" + "=" * 80)
    print("SIMULATING REALISTIC WHATSAPP CUSTOMER DISCUSSION & AI PROCESSING")
    print("=" * 80)

    customer_phone = "+21698765432"
    customer_name = "Tarek Mansour"
    phone_number_id = "104829104819"

    # Step 1: Ensure tenant, whatsapp_account, customer and conversation exist in DB
    async with async_session_factory() as db:
        # Get or create tenant
        stmt_tenant = select(Tenant).limit(1)
        tenant = (await db.scalars(stmt_tenant)).first()
        if not tenant:
            tenant = Tenant(
                id=generate_uuidv7(),
                name="Car Export Tunisia",
                slug="car-export-tn",
                is_active=True,
            )
            db.add(tenant)
            await db.flush()

        # Get or create WhatsAppAccount
        stmt_wa = select(WhatsAppAccount).where(WhatsAppAccount.tenant_id == tenant.id).limit(1)
        wa_account = (await db.scalars(stmt_wa)).first()
        if not wa_account:
            wa_account = WhatsAppAccount(
                id=generate_uuidv7(),
                tenant_id=tenant.id,
                phone_number_id=phone_number_id,
                display_phone_number="+21671000000",
                verified_name="Car Export CRM",
                is_active=True,
            )
            db.add(wa_account)
            await db.flush()

        # Get or create Customer
        stmt_cust = select(Customer).where(Customer.phone_e164 == customer_phone).limit(1)
        customer = (await db.scalars(stmt_cust)).first()
        if not customer:
            customer = Customer(
                id=generate_uuidv7(),
                tenant_id=tenant.id,
                phone_e164=customer_phone,
                whatsapp_id="21698765432",
                full_name=customer_name,
                first_name="Tarek",
                last_name="Mansour",
                fcr_eligible=True,
                preferred_language="fr",
            )
            db.add(customer)
            await db.flush()

        # Get or create Conversation
        stmt_conv = select(WhatsAppConversation).where(WhatsAppConversation.customer_id == customer.id).limit(1)
        conv = (await db.scalars(stmt_conv)).first()
        if not conv:
            conv = WhatsAppConversation(
                id=generate_uuidv7(),
                tenant_id=tenant.id,
                customer_id=customer.id,
                status="Active",
                last_activity_at=time.strftime("%Y-%m-%d %H:%M:%S+00"),
                unread_count=1,
            )
            db.add(conv)
            await db.flush()

        await db.commit()
        tenant_id = tenant.id
        conv_id = conv.id

    # Realistic 3-turn discussion
    dialogue = [
        {
            "sender": "CUSTOMER",
            "from": customer_phone,
            "text": "Salam alaykom, nheb nechri Peugeot 3008 Allure model 2022 diesel fcr tounes budget 24000 EUR. Est-ce que fama dispo f l'Allemagne ?",
        },
        {
            "sender": "AGENT",
            "from": "+21671000000",
            "text": "Bonjour M. Mansour ! Nous avons plusieurs Peugeot 3008 Allure 2022 diesel disponibles en Allemagne avec TVA déductible (Netto), parfaites pour le régime FCR.",
        },
        {
            "sender": "CUSTOMER",
            "from": customer_phone,
            "text": "Parfait ! 3andi droit FCR kemel, w nheb devis complet avec frais de douane et transport maritime vers le Port de Radès svp.",
        },
    ]

    print("\n--- INJECTING DISCUSSION MESSAGES ---")
    async with async_session_factory() as db:
        for turn in dialogue:
            print(f"[{turn['sender']}] ({turn['from']}): {turn['text']}")
            msg = Message(
                id=generate_uuidv7(),
                tenant_id=tenant_id,
                conversation_id=conv_id,
                direction="Inbound" if turn["sender"] == "CUSTOMER" else "Outbound",
                sender_type="Customer" if turn["sender"] == "CUSTOMER" else "Agent",
                message_type="text",
                content=turn["text"],
                delivery_status="Read" if turn["sender"] == "CUSTOMER" else "Delivered",
                provider_message_id=f"wamid.sim.{generate_uuidv7()}",
            )
            db.add(msg)
        await db.commit()

    # Step 2: Send the latest customer message to live Gemini AI
    latest_customer_msg = dialogue[-1]["text"]
    full_context_msg = dialogue[0]["text"] + "\n" + dialogue[2]["text"]

    print("\n" + "=" * 80)
    print("STEP 2: RUNNING LIVE GEMINI AI ON CUSTOMER INQUIRY")
    print("=" * 80)

    adapter = GeminiAdapter()

    # 1. Structured Vehicle Extraction
    extract_req = LLMCompletionRequest(
        prompt=(
            f"Customer Conversation Context:\n<untrusted_user_message>\n{full_context_msg}\n</untrusted_user_message>\n\n"
            "Extract in strict JSON: intent, make, model, year, budget_eur, language, fcr_eligible."
        ),
        model="gemini-3.6-flash",
    )
    raw_extracted, meta_ext = await adapter.generate_structured_output(extract_req, VehicleRequestExtraction)
    validated_extraction = validate_vehicle_request(raw_extracted.model_dump())

    print("\n[1. AI Vehicle Specification Extraction]:")
    print(json.dumps(validated_extraction.model_dump(), indent=2, ensure_ascii=False))
    print(f"Extraction Latency: {round(meta_ext.latency_ms, 2)} ms")

    # 2. Draft Commercial Reply (HITL)
    suggest_req = LLMCompletionRequest(
        prompt=(
            f"Client: {customer_name}\n"
            f"Vehicle: Peugeot 3008 Allure (2022)\n"
            f"Budget: 24 000 EUR\n"
            f"Regime: FCR Exonéré\n"
            f"Port: Radès\n"
            f"Dernier message client:\n\"{latest_customer_msg}\"\n\n"
            "Rédige une proposition commerciale WhatsApp professionnelle, chaleureuse et concise en français. "
            "Confirme la faisabilité du devis FCR avec transport vers Radès et propose l'envoi d'une simulation tarifaire PDF détaillée."
        ),
        system_prompt="Tu es un conseiller commercial senior en export automobile Europe vers Tunisie. Ton ton est professionnel, accueillant et efficace.",
        model="gemini-3.6-flash",
    )
    suggest_res = await adapter.generate_text(suggest_req)

    print("\n[2. AI Suggested Commercial WhatsApp Reply (HITL)]:")
    print("-" * 60)
    print(suggest_res.content.strip())
    print("-" * 60)
    print(f"Drafting Latency: {round(suggest_res.latency_ms, 2)} ms | Model: {suggest_res.model}")

    print("\n" + "=" * 80)
    print("DISCUSSION & AI DRAFT READY IN CRM INBOX: http://localhost:5173/inbox")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(simulate_live_discussion())
