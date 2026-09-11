"""Integration & unit tests for Lead declarative model, indexes, and relationships."""

import uuid

from sqlalchemy import Index

from app.models.customer import Customer
from app.models.lead import Lead, LeadPriority, LeadStatus
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.vehicle_request import VehicleRequest


def test_lead_model_instantiation() -> None:
    """Verify Lead model instantiates with UUIDv7 ID and default attributes."""
    tenant_id = uuid.uuid4()
    customer_id = uuid.uuid4()

    lead = Lead(
        tenant_id=tenant_id,
        customer_id=customer_id,
    )

    assert lead.id is not None
    assert isinstance(lead.id, uuid.UUID)
    assert lead.id.version == 7
    assert lead.tenant_id == tenant_id
    assert lead.customer_id == customer_id
    assert lead.status == LeadStatus.NEW.value
    assert lead.priority == LeadPriority.MEDIUM.value
    assert lead.vehicle_request_id is None
    assert lead.assigned_agent_id is None
    assert lead.lost_reason is None
    assert lead.closed_at is None


def test_lead_model_relationships_in_memory() -> None:
    """Verify in-memory relationship navigation between Tenant, Customer, User, VReq & Lead."""
    tenant = Tenant(name="Enterprise Auto", slug="enterprise-auto")
    customer = Customer(
        tenant_id=tenant.id,
        phone_e164="+21671123456",
        full_name="Karem Trabelsi",
        tenant=tenant,
    )
    agent = User(
        tenant_id=tenant.id,
        email="agent@enterpriseauto.tn",
        hashed_password="secret_password_hash",  # noqa: S106
        full_name="Agent Karem",
        role=UserRole.SALES_AGENT,
    )
    vreq = VehicleRequest(
        tenant_id=tenant.id,
        customer_id=customer.id,
        make="Mercedes-Benz",
        model="C200",
        min_year=2023,
    )

    lead = Lead(
        tenant_id=tenant.id,
        customer_id=customer.id,
        tenant=tenant,
        customer=customer,
        assigned_agent=agent,
        vehicle_request=vreq,
        status=LeadStatus.QUALIFIED.value,
    )

    assert lead.tenant is tenant
    assert lead.customer is customer
    assert lead.assigned_agent is agent
    assert lead.vehicle_request is vreq
    assert lead in tenant.leads
    assert lead in customer.leads
    assert lead in agent.assigned_leads
    assert lead in vreq.leads


def test_lead_table_indexes() -> None:
    """Verify Lead __table_args__ includes expected indexes."""
    table_args = Lead.__table_args__
    indexes = [arg for arg in table_args if isinstance(arg, Index)]
    index_names = [idx.name for idx in indexes]

    assert "ix_leads_tenant_id" in index_names
    assert "ix_leads_customer_id" in index_names
    assert "ix_leads_tenant_status" in index_names
    assert "ix_leads_assigned_agent_id" in index_names
    assert "ix_leads_created_at" in index_names
