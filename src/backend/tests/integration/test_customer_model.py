"""Integration & unit tests for Customer declarative model and tenant relationships."""

import uuid

from sqlalchemy import Index, UniqueConstraint

from app.models.customer import Customer
from app.models.tenant import Tenant


def test_customer_model_instantiation() -> None:
    """Verify Customer model instantiates with default UUIDv7 ID and default attributes."""
    tenant_id = uuid.uuid4()
    customer = Customer(
        tenant_id=tenant_id,
        phone_e164="+21698123456",
        full_name="Mohamed Ben Ali",
        first_name="Mohamed",
        last_name="Ben Ali",
    )

    assert customer.id is not None
    assert isinstance(customer.id, uuid.UUID)
    assert customer.id.version == 7
    assert customer.tenant_id == tenant_id
    assert customer.phone_e164 == "+21698123456"
    assert customer.full_name == "Mohamed Ben Ali"
    assert customer.first_name == "Mohamed"
    assert customer.last_name == "Ben Ali"
    assert customer.preferred_language == "fr"
    assert customer.fcr_eligible is False
    assert customer.whatsapp_id is None
    assert customer.notes is None


def test_customer_tenant_relationship_navigation() -> None:
    """Verify in-memory relationship navigation between Tenant and Customer models."""
    tenant = Tenant(name="Gamma Export Auto", slug="gamma-export")
    customer = Customer(
        tenant_id=tenant.id,
        phone_e164="+33612345678",
        full_name="Jean Dupont",
        tenant=tenant,
    )

    assert customer.tenant is tenant
    assert customer in tenant.customers


def test_customer_table_constraints_and_indexes() -> None:
    """Verify Customer __table_args__ includes composite unique constraint and indexes."""
    table_args = Customer.__table_args__
    unique_constraints = [arg for arg in table_args if isinstance(arg, UniqueConstraint)]
    indexes = [arg for arg in table_args if isinstance(arg, Index)]

    # Assert composite unique constraint (tenant_id, phone_e164)
    uq_names = [uq.name for uq in unique_constraints]
    assert "uq_customers_tenant_id_phone_e164" in uq_names
    target_uq = next(
        uq for uq in unique_constraints if uq.name == "uq_customers_tenant_id_phone_e164"
    )
    column_names = [col if isinstance(col, str) else col.name for col in target_uq.columns]
    assert "tenant_id" in column_names
    assert "phone_e164" in column_names

    # Assert indexes
    index_names = [idx.name for idx in indexes]
    assert "ix_customers_tenant_id" in index_names
    assert "ix_customers_phone_e164" in index_names
