"""Integration & unit tests for Tenant & User declarative models and RBAC UserRole enum."""

import uuid

from app.models.tenant import Tenant
from app.models.user import User, UserRole


def test_user_role_enum_values() -> None:
    """Verify UserRole enum contains expected RBAC role string values."""
    assert UserRole.SUPER_ADMIN.value == "SuperAdmin"
    assert UserRole.TENANT_ADMIN.value == "TenantAdmin"
    assert UserRole.SALES_AGENT.value == "SalesAgent"
    assert UserRole.LOGISTICS_AGENT.value == "LogisticsAgent"


def test_tenant_model_instantiation() -> None:
    """Verify Tenant model instantiates with UUIDv7 default ID and attributes."""
    tenant = Tenant(name="Alpha Motors Export", slug="alpha-motors")
    assert tenant.id is not None
    assert isinstance(tenant.id, uuid.UUID)
    assert tenant.id.version == 7
    assert tenant.name == "Alpha Motors Export"
    assert tenant.slug == "alpha-motors"
    assert tenant.is_active is True


def test_user_model_instantiation() -> None:
    """Verify User model instantiates with UUIDv7 default ID and RBAC role."""
    tenant_id = uuid.uuid4()
    user = User(
        tenant_id=tenant_id,
        email="agent@alphamotors.de",
        hashed_password="$argon2id$v=19$m=65536,t=2,p=8$mockhash",  # noqa: S106
        full_name="Jane Doe",
        role=UserRole.SALES_AGENT,
    )
    assert user.id is not None
    assert isinstance(user.id, uuid.UUID)
    assert user.id.version == 7
    assert user.tenant_id == tenant_id
    assert user.email == "agent@alphamotors.de"
    assert user.full_name == "Jane Doe"
    assert user.role == UserRole.SALES_AGENT
    assert user.is_active is True


def test_tenant_user_relationship_navigation() -> None:
    """Verify in-memory relationship navigation between Tenant and User models."""
    tenant = Tenant(name="Beta Auto GmbH", slug="beta-auto")
    user = User(
        tenant_id=tenant.id,
        email="admin@betaauto.de",
        hashed_password="$argon2id$v=19$m=65536,t=2,p=8$mockhash",  # noqa: S106
        full_name="Admin User",
        role=UserRole.TENANT_ADMIN,
        tenant=tenant,
    )

    assert user.tenant is tenant
    assert user in tenant.users
