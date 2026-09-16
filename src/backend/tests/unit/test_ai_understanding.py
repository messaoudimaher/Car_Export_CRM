"""Unit and DB integration tests for AIUnderstanding (WS-12, INV-003, ADR 0007)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.core.database import check_database_health, get_db_session
from app.models.ai_understanding import (
    AIUnderstanding,
    AIUnderstandingIntent,
    AIUnderstandingStatus,
)
from app.models.customer import Customer
from app.models.tenant import Tenant
from app.models.vehicle_request import VehicleRequest
from app.schemas.ai_extraction import (
    AIExtractionResult,
    CustomerIntent,
    DestinationPort,
    DetectedLanguage,
    FuelType,
    TransmissionType,
)
from app.schemas.ai_understanding import (
    AIUnderstandingCreate,
    AIUnderstandingRead,
    AIUnderstandingUpdateStatus,
)
from app.services.ai_understanding_service import AIUnderstandingService


def test_ai_understanding_model_in_memory_defaults() -> None:
    """Verify in-memory model instantiation sets expected defaults."""
    tenant_id = uuid.uuid4()
    understanding = AIUnderstanding(tenant_id=tenant_id)

    assert understanding.tenant_id == tenant_id
    assert understanding.status == AIUnderstandingStatus.PROVISIONAL.value
    assert understanding.intent == AIUnderstandingIntent.SOURCING_INQUIRY.value
    assert understanding.confidence_score == Decimal("0.000")
    assert understanding.detected_language == "fr"
    assert understanding.summary_fr == ""
    assert understanding.model_name == "gpt-4o-mini"
    assert understanding.prompt_version == "v1.0"
    assert understanding.extracted_data_jsonb == {}


def test_ai_understanding_pydantic_schemas() -> None:
    """Verify Pydantic DTO schemas serialize and validate expected fields."""
    tenant_id = uuid.uuid4()
    create_dto = AIUnderstandingCreate(
        tenant_id=tenant_id,
        intent="SOURCING_INQUIRY",
        extracted_data_jsonb={"make": "Volkswagen", "model": "Golf 7"},
        confidence_score=Decimal("0.950"),
        detected_language="fr",
        summary_fr="Recherche Golf 7 TDI",
    )

    assert create_dto.tenant_id == tenant_id
    assert create_dto.confidence_score == Decimal("0.950")
    assert create_dto.status == "Provisional"

    update_dto = AIUnderstandingUpdateStatus(status=AIUnderstandingStatus.CONFIRMED)
    assert update_dto.status == AIUnderstandingStatus.CONFIRMED

    read_dto = AIUnderstandingRead(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        conversation_id=None,
        message_id=None,
        customer_id=None,
        intent="SOURCING_INQUIRY",
        extracted_data_jsonb={"make": "Volkswagen"},
        confidence_score=Decimal("0.950"),
        status="Provisional",
        detected_language="fr",
        summary_fr="Recherche VW",
        model_name="gpt-4o-mini",
        prompt_version="v1.0",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert read_dto.intent == "SOURCING_INQUIRY"


@pytest.mark.asyncio
async def test_create_provisional_understanding_db_success() -> None:
    """Verify AIUnderstandingService persists provisional extraction and enforces INV-003."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    async for db in get_db_session():
        tenant = Tenant(name="Test AI Tenant", slug=f"t-{uuid.uuid4().hex[:8]}")
        customer = Customer(tenant_id=tenant.id, phone_e164="+21698765432", full_name="Sami Ben Ali")
        db.add_all([tenant, customer])
        await db.flush()

        extraction = AIExtractionResult(
            intent=CustomerIntent.SOURCING_INQUIRY,
            confidence_score=0.92,
            summary_fr="Demande Golf 7 TDI en FCR",
            detected_language=DetectedLanguage.FR,
            fcr_eligible_mentioned=True,
            destination_port=DestinationPort.RADES,
            make="Volkswagen",
            model="Golf 7",
            min_year=2019,
            budget_eur=18000.0,
            fuel_type=FuelType.DIESEL,
            transmission=TransmissionType.AUTOMATIC,
        )

        understanding = await AIUnderstandingService.create_provisional_understanding(
            db=db,
            tenant_id=tenant.id,
            extraction_result=extraction,
            customer_id=customer.id,
            model_name="gpt-4o-mini",
            prompt_version="v1.0",
        )

        assert understanding.id is not None
        assert understanding.tenant_id == tenant.id
        assert understanding.customer_id == customer.id
        assert understanding.status == AIUnderstandingStatus.PROVISIONAL.value
        assert understanding.confidence_score == Decimal("0.920")
        assert understanding.intent == "SOURCING_INQUIRY"
        assert understanding.summary_fr == "Demande Golf 7 TDI en FCR"
        assert understanding.extracted_data_jsonb["make"] == "Volkswagen"
        assert understanding.extracted_data_jsonb["model"] == "Golf 7"

        # Assert INV-003: No vehicle_requests record created directly
        from sqlalchemy import select

        vr_stmt = select(VehicleRequest).where(VehicleRequest.tenant_id == tenant.id)
        vr_records = (await db.execute(vr_stmt)).scalars().all()
        assert len(vr_records) == 0, (
            "INV-003 violation: Ground-truth vehicle_request created by AI service"
        )

        await db.rollback()
        break


@pytest.mark.asyncio
async def test_get_and_list_understandings_db() -> None:
    """Verify querying and listing AI understandings filtered by tenant and status."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    async for db in get_db_session():
        tenant = Tenant(name="Test AI List Tenant", slug=f"t-{uuid.uuid4().hex[:8]}")
        db.add(tenant)
        await db.flush()

        ext1 = AIExtractionResult(intent=CustomerIntent.SOURCING_INQUIRY, confidence_score=0.85)
        ext2 = AIExtractionResult(intent=CustomerIntent.PRICE_CHECK, confidence_score=0.90)

        u1 = await AIUnderstandingService.create_provisional_understanding(
            db=db,
            tenant_id=tenant.id,
            extraction_result=ext1,
        )
        u2 = await AIUnderstandingService.create_provisional_understanding(
            db=db,
            tenant_id=tenant.id,
            extraction_result=ext2,
        )
        assert u2.id is not None

        fetched_u1 = await AIUnderstandingService.get_understanding_by_id(
            db=db,
            tenant_id=tenant.id,
            understanding_id=u1.id,
        )
        assert fetched_u1 is not None
        assert fetched_u1.id == u1.id

        # Isolated tenant lookup returns None
        other_tenant_id = uuid.uuid4()
        iso_fetch = await AIUnderstandingService.get_understanding_by_id(
            db=db,
            tenant_id=other_tenant_id,
            understanding_id=u1.id,
        )
        assert iso_fetch is None

        # List understandings
        list_all = await AIUnderstandingService.list_understandings(db=db, tenant_id=tenant.id)
        assert len(list_all) == 2

        list_prov = await AIUnderstandingService.list_understandings(
            db=db,
            tenant_id=tenant.id,
            status=AIUnderstandingStatus.PROVISIONAL.value,
        )
        assert len(list_prov) == 2

        await db.rollback()
        break


@pytest.mark.asyncio
async def test_update_status_db() -> None:
    """Verify status transition from Provisional to Confirmed and Rejected."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    async for db in get_db_session():
        tenant = Tenant(name="Test AI Status Tenant", slug=f"t-{uuid.uuid4().hex[:8]}")
        db.add(tenant)
        await db.flush()

        ext = AIExtractionResult(intent=CustomerIntent.SOURCING_INQUIRY, confidence_score=0.90)
        u = await AIUnderstandingService.create_provisional_understanding(
            db=db,
            tenant_id=tenant.id,
            extraction_result=ext,
        )

        # Confirm status
        confirmed = await AIUnderstandingService.update_status(
            db=db,
            tenant_id=tenant.id,
            understanding_id=u.id,
            new_status=AIUnderstandingStatus.CONFIRMED,
        )
        assert confirmed.status == AIUnderstandingStatus.CONFIRMED.value

        # Reject status
        rejected = await AIUnderstandingService.update_status(
            db=db,
            tenant_id=tenant.id,
            understanding_id=u.id,
            new_status=AIUnderstandingStatus.REJECTED,
        )
        assert rejected.status == AIUnderstandingStatus.REJECTED.value

        # Invalid status raises ValueError
        with pytest.raises(ValueError, match="Invalid AIUnderstandingStatus value"):
            await AIUnderstandingService.update_status(
                db=db,
                tenant_id=tenant.id,
                understanding_id=u.id,
                new_status="InvalidStatus",
            )

        await db.rollback()
        break
