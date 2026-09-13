"""Unit and DB integration tests for FollowUp model and FollowUpService (WS-14, TASK-1401)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.database import check_database_health, get_db_session
from app.models.customer import Customer
from app.models.followup import FollowUp, FollowUpStatus
from app.models.lead import Lead, LeadStatus
from app.models.tenant import Tenant
from app.schemas.followup import FollowUpCreate, FollowUpRead, FollowUpUpdate
from app.services.followup_service import FollowUpService


def test_followup_model_in_memory_defaults() -> None:
    """Verify FollowUp model instantiation sets expected defaults."""
    tenant_id = uuid.uuid4()
    lead_id = uuid.uuid4()
    due_at = datetime.now(UTC) + timedelta(days=1)

    task = FollowUp(
        tenant_id=tenant_id,
        lead_id=lead_id,
        title="Call customer regarding Golf 7 quote",
        due_at=due_at,
    )

    assert task.tenant_id == tenant_id
    assert task.lead_id == lead_id
    assert task.title == "Call customer regarding Golf 7 quote"
    assert task.status == FollowUpStatus.PENDING.value
    assert task.reminder_sent is False
    assert task.completed_at is None


def test_followup_pydantic_schemas() -> None:
    """Verify FollowUp Pydantic DTO schemas validate expected attributes."""
    lead_id = uuid.uuid4()
    due_at = datetime.now(UTC) + timedelta(hours=5)

    create_dto = FollowUpCreate(
        lead_id=lead_id,
        title="Verify FCR certificate eligibility",
        description="Check client residence card date",
        due_at=due_at,
    )
    assert create_dto.lead_id == lead_id
    assert create_dto.title == "Verify FCR certificate eligibility"

    update_dto = FollowUpUpdate(status=FollowUpStatus.COMPLETED)
    assert update_dto.status == FollowUpStatus.COMPLETED

    task_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    now = datetime.now(UTC)

    read_dto = FollowUpRead(
        id=task_id,
        tenant_id=tenant_id,
        lead_id=lead_id,
        title="Check status",
        due_at=due_at,
        status="Pending",
        reminder_sent=False,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )
    assert read_dto.id == task_id
    assert read_dto.status == "Pending"


def test_followup_lifecycle_methods() -> None:
    """Verify mark_completed and mark_cancelled lifecycle transition helpers and validations."""
    task = FollowUp(
        tenant_id=uuid.uuid4(),
        lead_id=uuid.uuid4(),
        title="Test Task",
        due_at=datetime.now(UTC),
    )
    assert task.status == FollowUpStatus.PENDING.value

    task.mark_completed()
    assert task.status == FollowUpStatus.COMPLETED.value
    assert task.completed_at is not None

    # Cannot cancel a completed task
    with pytest.raises(ValueError, match="Cannot cancel a completed follow-up task"):
        task.mark_cancelled()

    task_cancelled = FollowUp(
        tenant_id=uuid.uuid4(),
        lead_id=uuid.uuid4(),
        title="Cancelled Task",
        due_at=datetime.now(UTC),
    )
    task_cancelled.mark_cancelled()
    assert task_cancelled.status == FollowUpStatus.CANCELLED.value

    # Cannot complete a cancelled task
    with pytest.raises(ValueError, match="Cannot complete a cancelled follow-up task"):
        task_cancelled.mark_completed()


@pytest.mark.asyncio
async def test_followup_service_db_persistence() -> None:
    """Integration test persisting, completing, and querying FollowUp records from PostgreSQL."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database unavailable for integration test.")

    async for session in get_db_session():
        tenant = Tenant(
            name=f"FollowUp Test Org {uuid.uuid4().hex[:6]}",
            slug=f"followup-{uuid.uuid4().hex[:6]}",
        )
        session.add(tenant)
        await session.flush()

        customer = Customer(
            tenant_id=tenant.id,
            first_name="Tarak",
            last_name="Mansour",
            phone_number=f"+21697{uuid.uuid4().int % 1000000:06d}",
        )
        session.add(customer)
        await session.flush()

        lead = Lead(
            tenant_id=tenant.id,
            customer_id=customer.id,
            status=LeadStatus.NEW.value,
        )
        session.add(lead)
        await session.commit()

        service = FollowUpService(session=session)

        due_at = datetime.now(UTC) + timedelta(days=2)
        create_payload = FollowUpCreate(
            lead_id=lead.id,
            title="Follow up on shipping quotation details",
            description="Call customer after quote generation.",
            due_at=due_at,
        )

        followup = await service.create_followup(tenant_id=tenant.id, payload=create_payload)

        assert followup.id is not None
        assert followup.tenant_id == tenant.id
        assert followup.lead_id == lead.id
        assert followup.status == FollowUpStatus.PENDING.value

        # Complete follow-up task
        completed_task = await service.complete_followup(
            tenant_id=tenant.id, followup_id=followup.id
        )
        assert completed_task.status == FollowUpStatus.COMPLETED.value
        assert completed_task.completed_at is not None

        # List follow-ups for tenant
        tasks = await service.list_followups(tenant_id=tenant.id, lead_id=lead.id)
        assert len(tasks) == 1
        assert tasks[0].id == followup.id

        break
