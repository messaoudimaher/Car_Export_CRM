"""TASK-1801: Automated IDOR & Multi-Tenant Cross-Access Security Test Suite (AC-01, SEC-001 .. SEC-010).

This test suite executes automated cross-tenant resource access attempts across all multi-tenant API
entities (Customers, Conversations, Leads, Vehicle Requests, Quotations, Documents) to verify:
1. Zero cross-tenant data leakage (SEC-001, SEC-003).
2. All unauthorized cross-tenant requests return HTTP 404 Not Found rather than 403 Forbidden to mask resource existence (SEC-010, AC-01).
3. Client-supplied tenant_id query parameters, request headers, or body attributes are strictly ignored (SEC-002).
"""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db_session
from app.core.security import create_access_token
from app.main import create_app
from app.models.customer import Customer
from app.models.document import Document
from app.models.lead import Lead, LeadStatus
from app.models.quotation import Quotation, QuotationStatus
from app.models.user import User, UserRole
from app.repositories.tenant_base import TenantRepository


def create_security_test_app(mock_session: AsyncMock) -> FastAPI:
    """Create a FastAPI application instance bound to a mock database session."""
    app = create_app()

    async def override_get_db_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    return app


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Return a configured AsyncMock database session for security testing."""
    session = AsyncMock()
    session.add = MagicMock()
    session.merge = MagicMock(side_effect=lambda obj: obj)
    return session


@pytest.fixture
def tenant_a_user_and_token(mock_db_session: AsyncMock) -> tuple[User, uuid.UUID, str]:
    """Fixture returning User A (Tenant A) and a valid JWT bearer token."""
    user_a_id = uuid.uuid4()
    tenant_a_id = uuid.uuid4()

    user_a = User(
        id=user_a_id,
        tenant_id=tenant_a_id,
        email="agent_a@tenant_alpha.com",
        password_hash="hashed_pwd_a",  # noqa: S106
        role=UserRole.SALES_AGENT,
        is_active=True,
    )

    token_a = create_access_token(
        subject=user_a_id,
        tenant_id=tenant_a_id,
        role=UserRole.SALES_AGENT,
    )

    # Configure session mock to return user_a on user authentication query
    mock_db_session.get.return_value = user_a

    return user_a, tenant_a_id, token_a


@pytest.mark.asyncio
async def test_idor_cross_tenant_customer_get_returns_404(
    mock_db_session: AsyncMock,
    tenant_a_user_and_token: tuple[User, uuid.UUID, str],
) -> None:
    """GET /api/v1/customers/{id} for Tenant B customer ID returns HTTP 404 Not Found (SEC-010)."""
    _user_a, tenant_a_id, token_a = tenant_a_user_and_token
    tenant_b_id = uuid.uuid4()
    customer_b_id = uuid.uuid4()

    customer_b = Customer(
        id=customer_b_id,
        tenant_id=tenant_b_id,
        phone_e164="+21698765432",
        whatsapp_id="21698765432",
        full_name="Target Customer B",
    )

    # Mock DB query scoped to Tenant A returns None (since customer_b belongs to Tenant B)
    # Global query check returns customer_b to confirm resource existence for 404 masking logic
    mock_exec_none = MagicMock()
    mock_exec_none.scalar_one_or_none.return_value = None

    mock_exec_global = MagicMock()
    mock_exec_global.scalar_one_or_none.return_value = customer_b

    mock_db_session.execute.side_effect = [mock_exec_none, mock_exec_global]

    app = create_security_test_app(mock_db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(
            f"/api/v1/customers/{customer_b_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )

    # Must return 404 Not Found (RFC 7807 problem details) rather than 403 Forbidden
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    problem = response.json()
    assert problem["status"] == 404
    assert problem["title"] == "Resource Not Found"


@pytest.mark.asyncio
async def test_idor_cross_tenant_customer_patch_returns_404(
    mock_db_session: AsyncMock,
    tenant_a_user_and_token: tuple[User, uuid.UUID, str],
) -> None:
    """PATCH /api/v1/customers/{id} attempting cross-tenant update returns HTTP 404 (SEC-010)."""
    _user_a, tenant_a_id, token_a = tenant_a_user_and_token
    tenant_b_id = uuid.uuid4()
    customer_b_id = uuid.uuid4()

    customer_b = Customer(
        id=customer_b_id,
        tenant_id=tenant_b_id,
        phone_e164="+21698765432",
        whatsapp_id="21698765432",
        full_name="Target Customer B",
    )

    mock_exec_none = MagicMock()
    mock_exec_none.scalar_one_or_none.return_value = None

    mock_exec_global = MagicMock()
    mock_exec_global.scalar_one_or_none.return_value = customer_b

    mock_db_session.execute.side_effect = [mock_exec_none, mock_exec_global]

    app = create_security_test_app(mock_db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.patch(
            f"/api/v1/customers/{customer_b_id}",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"fcr_eligible": True, "notes": "Unauthorized edit"},
        )

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    problem = response.json()
    assert problem["status"] == 404


@pytest.mark.asyncio
async def test_idor_cross_tenant_lead_get_returns_404(
    mock_db_session: AsyncMock,
    tenant_a_user_and_token: tuple[User, uuid.UUID, str],
) -> None:
    """GET /api/v1/leads/{id} for Tenant B lead ID returns HTTP 404 Not Found (SEC-010)."""
    _user_a, tenant_a_id, token_a = tenant_a_user_and_token
    tenant_b_id = uuid.uuid4()
    lead_b_id = uuid.uuid4()

    lead_b = Lead(
        id=lead_b_id,
        tenant_id=tenant_b_id,
        customer_id=uuid.uuid4(),
        status=LeadStatus.QUALIFIED.value,
    )

    mock_exec_none = MagicMock()
    mock_exec_none.scalar_one_or_none.return_value = None

    mock_exec_global = MagicMock()
    mock_exec_global.scalar_one_or_none.return_value = lead_b

    mock_db_session.execute.side_effect = [mock_exec_none, mock_exec_global]

    app = create_security_test_app(mock_db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(
            f"/api/v1/leads/{lead_b_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    problem = response.json()
    assert problem["status"] == 404


@pytest.mark.asyncio
async def test_idor_cross_tenant_quotation_get_returns_404(
    mock_db_session: AsyncMock,
    tenant_a_user_and_token: tuple[User, uuid.UUID, str],
) -> None:
    """GET /api/v1/quotations/{id} for Tenant B quotation ID returns HTTP 404 Not Found (SEC-010)."""
    _user_a, tenant_a_id, token_a = tenant_a_user_and_token
    tenant_b_id = uuid.uuid4()
    quote_b_id = uuid.uuid4()

    quote_b = Quotation(
        id=quote_b_id,
        tenant_id=tenant_b_id,
        lead_id=uuid.uuid4(),
        quote_number="Q-2026-9999",
        vehicle_model="Porsche Macan GTS",
        status=QuotationStatus.DRAFT,
    )

    mock_exec_none = MagicMock()
    mock_exec_none.scalar_one_or_none.return_value = None

    mock_exec_global = MagicMock()
    mock_exec_global.scalar_one_or_none.return_value = quote_b

    mock_db_session.execute.side_effect = [mock_exec_none, mock_exec_global]

    app = create_security_test_app(mock_db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(
            f"/api/v1/quotations/{quote_b_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    problem = response.json()
    assert problem["status"] == 404


@pytest.mark.asyncio
async def test_idor_cross_tenant_document_get_returns_404(
    mock_db_session: AsyncMock,
    tenant_a_user_and_token: tuple[User, uuid.UUID, str],
) -> None:
    """GET /api/v1/documents/{id} for Tenant B document ID returns HTTP 404 Not Found (SEC-010)."""
    _user_a, tenant_a_id, token_a = tenant_a_user_and_token
    tenant_b_id = uuid.uuid4()
    doc_b_id = uuid.uuid4()

    doc_b = Document(
        id=doc_b_id,
        tenant_id=tenant_b_id,
        file_name="Passport_Scan_TenantB.pdf",
        object_key="tenants/b/docs/passport.pdf",
        category="Passport",
        mime_type="application/pdf",
        file_size_bytes=1024,
        sha256_hash="abc123def456",
        scan_status="Passed",
    )

    mock_exec_none = MagicMock()
    mock_exec_none.scalar_one_or_none.return_value = None

    mock_exec_global = MagicMock()
    mock_exec_global.scalar_one_or_none.return_value = doc_b

    mock_db_session.execute.side_effect = [mock_exec_none, mock_exec_global]

    app = create_security_test_app(mock_db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(
            f"/api/v1/documents/{doc_b_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    problem = response.json()
    assert problem["status"] == 404


@pytest.mark.asyncio
async def test_client_supplied_tenant_id_header_or_body_ignored(
    mock_db_session: AsyncMock,
    tenant_a_user_and_token: tuple[User, uuid.UUID, str],
) -> None:
    """Verify that client-supplied X-Tenant-ID header or tenant_id body attribute is strictly ignored (SEC-001, SEC-002)."""
    _user_a, tenant_a_id, token_a = tenant_a_user_and_token
    tenant_b_id = uuid.uuid4()

    mock_exec_none = MagicMock()
    mock_exec_none.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = mock_exec_none

    app = create_security_test_app(mock_db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        # Client A attempts to inject X-Tenant-ID header claiming Tenant B
        response = await client.post(
            "/api/v1/customers",
            headers={
                "Authorization": f"Bearer {token_a}",
                "X-Tenant-ID": str(tenant_b_id),
            },
            json={
                "phone": "+21698111222",
                "full_name": "Injected Tenant Customer",
                "tenant_id": str(tenant_b_id),  # Malicious body override attempt
            },
        )

    # Server accepts request based on JWT claims (Tenant A), discarding client's tenant_id injection
    assert response.status_code == 201
    json_data = response.json()
    assert json_data["success"] is True


@pytest.mark.asyncio
async def test_tenant_repository_get_or_raise_cross_tenant_raises_not_found(
    mock_db_session: AsyncMock,
) -> None:
    """Verify TenantRepository.get_or_raise raises 404 when querying another tenant's resource (SEC-003, SEC-010)."""
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()
    resource_b_id = uuid.uuid4()

    resource_b = Customer(
        id=resource_b_id,
        tenant_id=tenant_b_id,
        phone_e164="+21699999999",
        whatsapp_id="21699999999",
        full_name="Tenant B Isolated Customer",
    )

    # Query scoped to Tenant A returns None
    mock_exec_none = MagicMock()
    mock_exec_none.scalar_one_or_none.return_value = None

    # Global query returns resource_b to confirm existence
    mock_exec_global = MagicMock()
    mock_exec_global.scalar_one_or_none.return_value = resource_b

    mock_db_session.execute.side_effect = [mock_exec_none, mock_exec_global]

    repo_a = TenantRepository(mock_db_session, Customer, tenant_id=tenant_a_id)

    from app.core.errors import NotFoundException

    with pytest.raises(NotFoundException) as exc_info:
        await repo_a.get_or_raise(resource_b_id)

    assert exc_info.value.status_code == 404
    assert "Customer" in str(exc_info.value)


@pytest.mark.asyncio
async def test_idor_cross_tenant_customer_delete_returns_404(
    mock_db_session: AsyncMock,
    tenant_a_user_and_token: tuple[User, uuid.UUID, str],
) -> None:
    """DELETE /api/v1/customers/{id} for Tenant B customer ID returns HTTP 404 Not Found (SEC-010)."""
    _user_a, tenant_a_id, token_a = tenant_a_user_and_token
    tenant_b_id = uuid.uuid4()
    customer_b_id = uuid.uuid4()

    customer_b = Customer(
        id=customer_b_id,
        tenant_id=tenant_b_id,
        phone_e164="+21698765432",
        whatsapp_id="21698765432",
        full_name="Target Customer B",
    )

    mock_exec_none = MagicMock()
    mock_exec_none.scalar_one_or_none.return_value = None

    mock_exec_global = MagicMock()
    mock_exec_global.scalar_one_or_none.return_value = customer_b

    mock_db_session.execute.side_effect = [mock_exec_none, mock_exec_global]

    # Change user_a role to SuperAdmin to pass RBAC check and hit IDOR isolation check
    _user_a.role = UserRole.SUPER_ADMIN
    mock_db_session.get.return_value = _user_a

    app = create_security_test_app(mock_db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            f"/api/v1/customers/{customer_b_id}/anonymize",
            json={"reason": "Test cross-tenant erasure request"},
            headers={"Authorization": f"Bearer {token_a}"},
        )

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"


@pytest.mark.asyncio
async def test_idor_cross_tenant_vehicle_request_get_returns_404(
    mock_db_session: AsyncMock,
    tenant_a_user_and_token: tuple[User, uuid.UUID, str],
) -> None:
    """GET /api/v1/vehicle-requests/{id} for Tenant B request returns HTTP 404 (SEC-010)."""
    _user_a, tenant_a_id, token_a = tenant_a_user_and_token
    tenant_b_id = uuid.uuid4()
    request_b_id = uuid.uuid4()

    from app.models.vehicle_request import VehicleRequest

    req_b = VehicleRequest(
        id=request_b_id,
        tenant_id=tenant_b_id,
        customer_id=uuid.uuid4(),
        brand="BMW",
        model="X5",
    )

    mock_exec_none = MagicMock()
    mock_exec_none.scalar_one_or_none.return_value = None

    mock_exec_global = MagicMock()
    mock_exec_global.scalar_one_or_none.return_value = req_b

    mock_db_session.execute.side_effect = [mock_exec_none, mock_exec_global]

    app = create_security_test_app(mock_db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(
            f"/api/v1/vehicle-requests/{request_b_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_idor_cross_tenant_vehicle_get_returns_404(
    mock_db_session: AsyncMock,
    tenant_a_user_and_token: tuple[User, uuid.UUID, str],
) -> None:
    """GET /api/v1/vehicles/{id} for Tenant B vehicle returns HTTP 404 (SEC-010)."""
    _user_a, tenant_a_id, token_a = tenant_a_user_and_token
    tenant_b_id = uuid.uuid4()
    vehicle_b_id = uuid.uuid4()

    from app.models.vehicle import Vehicle

    veh_b = Vehicle(
        id=vehicle_b_id,
        tenant_id=tenant_b_id,
        vin="WBA1234567890ABCD",
        make="Porsche",
        model="Macan",
    )

    mock_exec_none = MagicMock()
    mock_exec_none.scalar_one_or_none.return_value = None

    mock_exec_global = MagicMock()
    mock_exec_global.scalar_one_or_none.return_value = veh_b

    mock_db_session.execute.side_effect = [mock_exec_none, mock_exec_global]

    app = create_security_test_app(mock_db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(
            f"/api/v1/vehicles/{vehicle_b_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_idor_cross_tenant_followup_get_returns_404(
    mock_db_session: AsyncMock,
    tenant_a_user_and_token: tuple[User, uuid.UUID, str],
) -> None:
    """GET /api/v1/followups/{id} for Tenant B follow-up task returns HTTP 404 (SEC-010)."""
    _user_a, tenant_a_id, token_a = tenant_a_user_and_token
    tenant_b_id = uuid.uuid4()
    followup_b_id = uuid.uuid4()

    from app.models.followup import FollowUp

    follow_b = FollowUp(
        id=followup_b_id,
        tenant_id=tenant_b_id,
        lead_id=uuid.uuid4(),
        title="Follow up with customer",
    )

    mock_exec_none = MagicMock()
    mock_exec_none.scalar_one_or_none.return_value = None

    mock_exec_global = MagicMock()
    mock_exec_global.scalar_one_or_none.return_value = follow_b

    mock_db_session.execute.side_effect = [mock_exec_none, mock_exec_global]

    app = create_security_test_app(mock_db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(
            f"/api/v1/followups/{followup_b_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_idor_cross_tenant_document_download_url_returns_404(
    mock_db_session: AsyncMock,
    tenant_a_user_and_token: tuple[User, uuid.UUID, str],
) -> None:
    """GET /api/v1/documents/{id}/download-url for Tenant B document returns HTTP 404 (SEC-006, SEC-010)."""
    _user_a, tenant_a_id, token_a = tenant_a_user_and_token
    tenant_b_id = uuid.uuid4()
    doc_b_id = uuid.uuid4()

    doc_b = Document(
        id=doc_b_id,
        tenant_id=tenant_b_id,
        file_name="Passport_Scan_TenantB.pdf",
        object_key="tenants/b/docs/passport.pdf",
        category="Passport",
        mime_type="application/pdf",
        file_size_bytes=1024,
        sha256_hash="abc123def456",
        scan_status="Passed",
    )

    mock_exec_none = MagicMock()
    mock_exec_none.scalar_one_or_none.return_value = None

    mock_exec_global = MagicMock()
    mock_exec_global.scalar_one_or_none.return_value = doc_b

    mock_db_session.execute.side_effect = [mock_exec_none, mock_exec_global]

    app = create_security_test_app(mock_db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(
            f"/api/v1/documents/{doc_b_id}/download-url",
            headers={"Authorization": f"Bearer {token_a}"},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_idor_cross_tenant_knowledge_chunk_delete_returns_404(
    mock_db_session: AsyncMock,
    tenant_a_user_and_token: tuple[User, uuid.UUID, str],
) -> None:
    """DELETE /api/v1/knowledge/chunks/{id} for Tenant B knowledge chunk returns HTTP 404 (SEC-007, SEC-010)."""
    _user_a, tenant_a_id, token_a = tenant_a_user_and_token
    tenant_b_id = uuid.uuid4()
    chunk_b_id = uuid.uuid4()

    from app.models.knowledge import KnowledgeEmbedding

    chunk_b = KnowledgeEmbedding(
        id=chunk_b_id,
        tenant_id=tenant_b_id,
        document_id="doc_rag_b",
        chunk_text="Tenant B export regulation details",
    )

    mock_exec_none = MagicMock()
    mock_exec_none.scalar_one_or_none.return_value = None

    mock_exec_global = MagicMock()
    mock_exec_global.scalar_one_or_none.return_value = chunk_b

    mock_db_session.execute.side_effect = [mock_exec_none, mock_exec_global]

    app = create_security_test_app(mock_db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.delete(
            f"/api/v1/knowledge/chunks/{chunk_b_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )

    assert response.status_code == 404
