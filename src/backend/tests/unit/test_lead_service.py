"""Unit & service tests for Lead state machine (BR-011) and 90-day auto-reopen (BR-012)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.database import check_database_health, get_db_session
from app.core.errors import ValidationException
from app.models.customer import Customer
from app.models.lead import (
    Lead,
    LeadPriority,
    LeadStatus,
    LostReason,
)
from app.models.tenant import Tenant
from app.services.lead_service import LeadService, lead_service


def test_validate_stage_transition_valid_paths() -> None:
    """Verify valid state transitions allowed under BR-011 & BR-012 pipeline rules."""
    # Standard linear progression
    LeadService.validate_stage_transition(LeadStatus.NEW, LeadStatus.QUALIFIED)
    LeadService.validate_stage_transition(LeadStatus.QUALIFIED, LeadStatus.SOURCING)
    LeadService.validate_stage_transition(LeadStatus.SOURCING, LeadStatus.QUOTED)
    LeadService.validate_stage_transition(LeadStatus.QUOTED, LeadStatus.WON)

    # Transition to Lost from active states
    LeadService.validate_stage_transition(LeadStatus.NEW, LeadStatus.LOST)
    LeadService.validate_stage_transition(LeadStatus.QUALIFIED, LeadStatus.LOST)
    LeadService.validate_stage_transition(LeadStatus.SOURCING, LeadStatus.LOST)
    LeadService.validate_stage_transition(LeadStatus.QUOTED, LeadStatus.LOST)

    # Auto-reopen from Lost to New (BR-012)
    LeadService.validate_stage_transition(LeadStatus.LOST, LeadStatus.NEW)

    # No-op same state transition
    LeadService.validate_stage_transition(LeadStatus.NEW, LeadStatus.NEW)
    LeadService.validate_stage_transition(LeadStatus.QUALIFIED, LeadStatus.QUALIFIED)


def test_validate_stage_transition_invalid_jumps_raise_validation_exception() -> None:
    """Verify invalid stage jumps raise ValidationException (BR-011)."""
    # Direct jump New -> Won
    with pytest.raises(ValidationException) as exc_info:
        LeadService.validate_stage_transition(LeadStatus.NEW, LeadStatus.WON)
    assert "Invalid lead transition from 'New' to 'Won'." in str(exc_info.value)

    # Direct jump New -> Quoted
    with pytest.raises(ValidationException):
        LeadService.validate_stage_transition(LeadStatus.NEW, LeadStatus.QUOTED)

    # Direct jump New -> Sourcing
    with pytest.raises(ValidationException):
        LeadService.validate_stage_transition(LeadStatus.NEW, LeadStatus.SOURCING)

    # Direct jump Qualified -> Won
    with pytest.raises(ValidationException):
        LeadService.validate_stage_transition(LeadStatus.QUALIFIED, LeadStatus.WON)

    # Terminal state transition Won -> Qualified
    with pytest.raises(ValidationException):
        LeadService.validate_stage_transition(LeadStatus.WON, LeadStatus.QUALIFIED)

    # Invalid jump Lost -> Won
    with pytest.raises(ValidationException):
        LeadService.validate_stage_transition(LeadStatus.LOST, LeadStatus.WON)


def test_lead_is_eligible_for_reopen_logic() -> None:
    """Verify is_eligible_for_reopen correctly evaluates 90-day window (BR-012)."""
    now = datetime.now(UTC)

    # Closed 45 days ago -> eligible
    closed_45d = now - timedelta(days=45)
    lead_45d = Lead(
        tenant_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        status=LeadStatus.LOST.value,
        closed_at=closed_45d,
    )
    assert lead_45d.is_eligible_for_reopen(now) is True

    # Closed 89 days ago -> eligible
    closed_89d = now - timedelta(days=89)
    lead_89d = Lead(
        tenant_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        status=LeadStatus.LOST.value,
        closed_at=closed_89d,
    )
    assert lead_89d.is_eligible_for_reopen(now) is True

    # Closed 92 days ago -> expired (not eligible)
    closed_92d = now - timedelta(days=92)
    lead_92d = Lead(
        tenant_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        status=LeadStatus.LOST.value,
        closed_at=closed_92d,
    )
    assert lead_92d.is_eligible_for_reopen(now) is False

    # Active lead (not Lost) -> not eligible
    active_lead = Lead(
        tenant_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        status=LeadStatus.QUALIFIED.value,
    )
    assert active_lead.is_eligible_for_reopen(now) is False


@pytest.mark.asyncio
async def test_lead_service_create_and_transition_lifecycle() -> None:
    """Verify AsyncSession DB operations for lead creation and stage transitions."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    async for session in get_db_session():
        tenant = Tenant(name="Sourcing Hub TN", slug=f"sourcing-hub-{uuid.uuid4().hex[:8]}")
        session.add(tenant)
        await session.flush()

        customer = Customer(
            tenant_id=tenant.id,
            phone_e164=f"+2169{uuid.uuid4().int % 10000000:07d}",
            full_name="Anis Kallel",
            tenant=tenant,
        )
        session.add(customer)
        await session.flush()

        # 1. Create Lead (New)
        lead = await lead_service.create_lead(
            db=session,
            tenant_id=tenant.id,
            customer_id=customer.id,
            priority=LeadPriority.HIGH,
        )
        assert lead.id is not None
        assert lead.status == LeadStatus.NEW.value
        assert lead.priority == LeadPriority.HIGH.value
        assert lead.closed_at is None

        # 2. Transition New -> Qualified
        lead_qual = await lead_service.transition_lead_stage(
            db=session,
            tenant_id=tenant.id,
            lead_id=lead.id,
            target_status=LeadStatus.QUALIFIED,
        )
        assert lead_qual.status == LeadStatus.QUALIFIED.value
        assert lead_qual.closed_at is None

        # 3. Transition Qualified -> Sourcing
        lead_src = await lead_service.transition_lead_stage(
            db=session,
            tenant_id=tenant.id,
            lead_id=lead.id,
            target_status=LeadStatus.SOURCING,
        )
        assert lead_src.status == LeadStatus.SOURCING.value

        # 4. Transition Sourcing -> Lost (Out of Budget)
        lead_lost = await lead_service.transition_lead_stage(
            db=session,
            tenant_id=tenant.id,
            lead_id=lead.id,
            target_status=LeadStatus.LOST,
            lost_reason=LostReason.OUT_OF_BUDGET,
        )
        assert lead_lost.status == LeadStatus.LOST.value
        assert lead_lost.lost_reason == LostReason.OUT_OF_BUDGET.value
        assert lead_lost.closed_at is not None

        # 5. Auto-Reopen Lost -> New (BR-012 within 90 days)
        reopened = await lead_service.check_and_reopen_lost_lead(
            db=session,
            tenant_id=tenant.id,
            customer_id=customer.id,
        )
        assert reopened is not None
        assert reopened.id == lead.id
        assert reopened.status == LeadStatus.NEW.value
        assert reopened.closed_at is None
        assert reopened.lost_reason is None
        break


@pytest.mark.asyncio
async def test_lead_service_reopen_expired_lost_lead_returns_none() -> None:
    """Verify check_and_reopen_lost_lead returns None for leads closed > 90 days ago."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    async for session in get_db_session():
        tenant = Tenant(name="Auto Sourcing Sarl", slug=f"auto-sourcing-{uuid.uuid4().hex[:8]}")
        session.add(tenant)
        await session.flush()

        customer = Customer(
            tenant_id=tenant.id,
            phone_e164=f"+2162{uuid.uuid4().int % 10000000:07d}",
            full_name="Mehdi Ben Youssef",
            tenant=tenant,
        )
        session.add(customer)
        await session.flush()

        # Create lead and manually backdate closed_at to 100 days ago
        closed_100d = datetime.now(UTC) - timedelta(days=100)
        old_lead = Lead(
            tenant_id=tenant.id,
            customer_id=customer.id,
            status=LeadStatus.LOST.value,
            lost_reason=LostReason.UNRESPONSIVE.value,
            closed_at=closed_100d,
        )
        session.add(old_lead)
        await session.commit()

        # Check reopen -> should return None because 100 > 90 days
        reopened = await lead_service.check_and_reopen_lost_lead(
            db=session,
            tenant_id=tenant.id,
            customer_id=customer.id,
        )
        assert reopened is None
        break
