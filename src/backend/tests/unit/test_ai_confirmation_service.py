"""Unit tests for AIConfirmationService enforcing Human-in-the-Loop boundary (INV-003, ADR 0012)."""

import uuid
from decimal import Decimal

import pytest

from app.core.database import check_database_health, get_db_session
from app.models.customer import Customer
from app.models.lead import LeadStatus
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.schemas.lead import ConfirmAIVehicleRequest
from app.services.ai_confirmation_service import ai_confirmation_service
from app.services.lead_service import lead_service


@pytest.mark.asyncio
async def test_confirm_ai_vehicle_request_creates_authoritative_truth() -> None:
    """Verify confirm_ai_vehicle_request persists VehicleRequest (INV-003)."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    async for session in get_db_session():
        tenant = Tenant(name="HITL Auto Sarl", slug=f"hitl-auto-{uuid.uuid4().hex[:8]}")
        session.add(tenant)
        await session.flush()

        customer = Customer(
            tenant_id=tenant.id,
            phone_e164=f"+2169{uuid.uuid4().int % 10000000:07d}",
            full_name="Firas Ben Salem",
            tenant=tenant,
        )
        session.add(customer)
        await session.flush()

        agent = User(
            tenant_id=tenant.id,
            email=f"agent_{uuid.uuid4().hex[:6]}@hitl.tn",
            hashed_password="hashed_pw_secret",  # noqa: S106
            full_name="Sales Rep Firas",
            role=UserRole.SALES_AGENT,
        )
        session.add(agent)
        await session.flush()

        lead = await lead_service.create_lead(
            db=session,
            tenant_id=tenant.id,
            customer_id=customer.id,
            assigned_agent_id=agent.id,
        )
        assert lead.status == LeadStatus.NEW.value
        assert lead.vehicle_request_id is None

        # Confirm AI Extraction (Layer 5 HITL)
        payload = ConfirmAIVehicleRequest(
            ai_understanding_id=uuid.uuid4(),
            make="BMW",
            model="Series 3",
            min_year=2022,
            max_year=2024,
            fuel_type="Diesel",
            transmission="Automatic",
            max_mileage_km=60000,
            budget_eur="23500.00",
            destination_port="Rades",
        )

        vreq, updated_lead = await ai_confirmation_service.confirm_ai_vehicle_request(
            db=session,
            tenant_id=tenant.id,
            lead_id=lead.id,
            user_id=agent.id,
            payload=payload,
        )

        # Assert authoritative ground truth persistence (INV-003, ADR 0012)
        assert vreq.id is not None
        assert vreq.is_human_validated is True
        assert vreq.confirmed_by_user_id == agent.id
        assert vreq.confirmed_at is not None
        assert vreq.make == "BMW"
        assert vreq.model == "Series 3"
        assert vreq.budget_eur == Decimal("23500.00")
        assert vreq.fcr_compatible is True

        # Assert Lead updated to Qualified stage & linked to VehicleRequest
        assert updated_lead.vehicle_request_id == vreq.id
        assert updated_lead.status == LeadStatus.QUALIFIED.value
        break
