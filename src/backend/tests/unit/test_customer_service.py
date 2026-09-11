"""Unit & integration tests for CustomerService (BR-014)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import ConflictException, NotFoundException
from app.models.customer import Customer
from app.services.customer_service import CustomerService


@pytest.mark.asyncio
async def test_customer_service_get_or_create_new_customer() -> None:
    """Verify get_or_create_by_phone creates new customer record when not found."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    tenant_id = uuid.uuid4()

    service = CustomerService(mock_session, tenant_id)
    service.repo.find_one = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service.repo.create = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda cust: cust
    )

    customer, created = await service.get_or_create_by_phone(
        phone="098123456",
        full_name="Anis Trabelsi",
    )

    assert created is True
    assert customer.tenant_id == tenant_id
    assert customer.phone_e164 == "+21698123456"
    assert customer.whatsapp_id == "21698123456"
    assert customer.full_name == "Anis Trabelsi"


@pytest.mark.asyncio
async def test_customer_service_get_or_create_existing_customer() -> None:
    """Verify get_or_create_by_phone returns existing customer record when found."""
    mock_session = AsyncMock()
    tenant_id = uuid.uuid4()
    existing_customer = Customer(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        phone_e164="+21698123456",
        whatsapp_id="21698123456",
        full_name="Anis Trabelsi",
    )

    service = CustomerService(mock_session, tenant_id)
    service.repo.find_one = AsyncMock(return_value=existing_customer)  # type: ignore[method-assign]

    customer, created = await service.get_or_create_by_phone(phone="+21698123456")

    assert created is False
    assert customer is existing_customer


@pytest.mark.asyncio
async def test_customer_service_create_duplicate_phone_raises_conflict() -> None:
    """Verify create_customer raises ConflictException if phone already registered for tenant."""
    mock_session = AsyncMock()
    tenant_id = uuid.uuid4()
    existing_customer = Customer(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        phone_e164="+33612345678",
    )

    service = CustomerService(mock_session, tenant_id)
    service.repo.find_one = AsyncMock(return_value=existing_customer)  # type: ignore[method-assign]

    with pytest.raises(ConflictException, match="already exists for this tenant"):
        await service.create_customer(phone="0612345678", default_region="FR")


@pytest.mark.asyncio
async def test_customer_service_get_by_id_success_and_not_found() -> None:
    """Verify get_by_id fetches customer or raises NotFoundException."""
    mock_session = AsyncMock()
    tenant_id = uuid.uuid4()
    cust_id = uuid.uuid4()
    existing_customer = Customer(id=cust_id, tenant_id=tenant_id, phone_e164="+21698123456")

    service = CustomerService(mock_session, tenant_id)
    service.repo.get_or_raise = AsyncMock(return_value=existing_customer)  # type: ignore[method-assign]

    customer = await service.get_by_id(cust_id)
    assert customer is existing_customer

    service.repo.get_or_raise = AsyncMock(  # type: ignore[method-assign]
        side_effect=NotFoundException("Customer not found.")
    )
    with pytest.raises(NotFoundException):
        await service.get_by_id(uuid.uuid4())
