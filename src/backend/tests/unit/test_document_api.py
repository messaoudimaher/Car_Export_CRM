"""Unit tests for Document REST API endpoints (WS-15, TASK-1502)."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.api.v1.router import api_v1_router
from app.core.database import get_db_session
from app.core.errors import register_exception_handlers
from app.models.document import Document
from app.models.user import UserRole


@pytest.fixture
def test_app() -> FastAPI:
    """Create test FastAPI application with API v1 router attached."""
    app = FastAPI(title="Document Test App")
    register_exception_handlers(app)
    app.include_router(api_v1_router)
    return app


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """AsyncMock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_initiate_document_upload_endpoint_unsupported_mime(
    test_app: FastAPI,
    mock_db_session: AsyncMock,
) -> None:
    """Verify upload initialization rejects unsupported MIME types."""
    tenant_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    mock_user = CurrentUser(
        user_id=agent_id,
        tenant_id=tenant_id,
        role=UserRole.SALES_AGENT.value,
        email="agent@test.com",
        is_active=True,
    )

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield mock_db_session

    test_app.dependency_overrides[get_db_session] = override_db
    test_app.dependency_overrides[get_current_user] = lambda: mock_user

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/documents/upload-url",
            json={
                "file_name": "executable.exe",
                "mime_type": "application/x-msdownload",
                "file_size_bytes": 1024,
                "category": "General",
            },
            headers={"Authorization": "Bearer mock_token"},
        )

    test_app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "Unsupported MIME type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_initiate_document_upload_endpoint_success(
    test_app: FastAPI,
    mock_db_session: AsyncMock,
) -> None:
    """Verify upload initialization generates presigned URL response."""
    tenant_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_user = CurrentUser(
        user_id=agent_id,
        tenant_id=tenant_id,
        role=UserRole.SALES_AGENT.value,
        email="agent@test.com",
        is_active=True,
    )

    mock_doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        document_type="Customer_Export_Doc",
        category="Carte_Grise",
        object_key=f"tenants/{tenant_id}/docs/{doc_id}/carte_grise.pdf",
        file_name="carte_grise.pdf",
        file_size_bytes=4096,
        mime_type="application/pdf",
        status="Pending",
    )

    upload_info = {
        "upload_url": f"http://localhost:8000/api/v1/documents/upload-local?key={mock_doc.object_key}",
        "expires_in_seconds": "900",
    }

    mock_service_instance = AsyncMock()
    mock_service_instance.initiate_upload.return_value = (mock_doc, upload_info)

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield mock_db_session

    test_app.dependency_overrides[get_db_session] = override_db
    test_app.dependency_overrides[get_current_user] = lambda: mock_user

    with patch("app.api.v1.documents.DocumentService", return_value=mock_service_instance):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=test_app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/documents/upload-url",
                json={
                    "file_name": "carte_grise.pdf",
                    "mime_type": "application/pdf",
                    "file_size_bytes": 4096,
                    "category": "Carte_Grise",
                },
                headers={"Authorization": "Bearer mock_token"},
            )

    test_app.dependency_overrides.clear()
    assert response.status_code == 201
    data = response.json()
    assert data["document_id"] == str(doc_id)
    assert data["object_key"] == mock_doc.object_key
    assert "upload_url" in data
    assert data["expires_in_seconds"] == 900


@pytest.mark.asyncio
async def test_get_document_download_url_endpoint(
    test_app: FastAPI,
    mock_db_session: AsyncMock,
) -> None:
    """Verify presigned download URL endpoint returns access URL for available document."""
    tenant_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    now = datetime.now(UTC)

    mock_user = CurrentUser(
        user_id=agent_id,
        tenant_id=tenant_id,
        role=UserRole.SALES_AGENT.value,
        email="agent@test.com",
        is_active=True,
    )

    mock_doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        document_type="Customer_Export_Doc",
        category="Carte_Grise",
        object_key=f"tenants/{tenant_id}/docs/{doc_id}/carte_grise.pdf",
        file_name="carte_grise.pdf",
        file_size_bytes=4096,
        mime_type="application/pdf",
        status="Available",
        scan_status="Passed",
        created_at=now,
        updated_at=now,
    )

    access_url = "http://localhost:8000/download/presigned"
    mock_service_instance = AsyncMock()
    mock_service_instance.get_document_access_url.return_value = (mock_doc, access_url)

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield mock_db_session

    test_app.dependency_overrides[get_db_session] = override_db
    test_app.dependency_overrides[get_current_user] = lambda: mock_user

    with patch("app.api.v1.documents.DocumentService", return_value=mock_service_instance):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=test_app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/api/v1/documents/{doc_id}/download-url",
                headers={"Authorization": "Bearer mock_token"},
            )

    test_app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["access_url"] == access_url
    assert data["expires_in_seconds"] == 900
    assert data["document"]["id"] == str(doc_id)
