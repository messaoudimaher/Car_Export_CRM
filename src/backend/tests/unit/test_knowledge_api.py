"""Unit and API integration tests for Knowledge Base Endpoints (WS-13, TASK-1303, ADR 0011)."""

import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, get_embedding_provider
from app.api.v1.router import api_v1_router
from app.core.database import get_db_session
from app.models.knowledge import KnowledgeEmbedding
from app.models.user import UserRole
from app.ports.embedding import EmbeddingProvider, EmbeddingResponse


@pytest.fixture
def test_app() -> FastAPI:
    """Create test FastAPI application with API v1 router attached."""
    app = FastAPI(title="Knowledge Base Test App")
    app.include_router(api_v1_router)
    return app


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """AsyncMock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def mock_embedding_provider() -> AsyncMock:
    """Mock EmbeddingProvider returning fixed float vectors."""
    provider = AsyncMock(spec=EmbeddingProvider)
    provider.generate_embeddings.return_value = EmbeddingResponse(
        embeddings=[[0.02] * 1536, [0.03] * 1536],
        model="text-embedding-3-small",
        dimensions=1536,
        prompt_tokens=40,
    )
    return provider


@pytest.mark.asyncio
async def test_knowledge_ingest_endpoint(
    test_app: FastAPI,
    mock_db_session: AsyncMock,
    mock_embedding_provider: AsyncMock,
) -> None:
    """Verify POST /api/v1/knowledge/ingest chunks document and stores embeddings."""
    tenant_id = uuid.uuid4()
    admin_id = uuid.uuid4()

    admin_user = CurrentUser(
        user_id=admin_id,
        tenant_id=tenant_id,
        role=UserRole.TENANT_ADMIN.value,
        email="admin@test.com",
        is_active=True,
    )

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield mock_db_session

    test_app.dependency_overrides[get_db_session] = override_db
    test_app.dependency_overrides[get_current_user] = lambda: admin_user
    test_app.dependency_overrides[get_embedding_provider] = lambda: mock_embedding_provider

    payload = {
        "document_name": "Test_Customs_Guide.pdf",
        "document_text": (
            "Paragraph 1: Tunisian car import regulations require vehicle age under 5 years.\n\n"
            "Paragraph 2: FCR privilege allows tax-free import for returning expats."
        ),
        "chunk_size": 200,
        "chunk_overlap": 30,
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/knowledge/ingest",
            json=payload,
            headers={"Authorization": "Bearer mock_token"},
        )

    test_app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["document_name"] == "Test_Customs_Guide.pdf"
    assert data["total_chunks"] > 0
    assert len(data["chunk_ids"]) == data["total_chunks"]


@pytest.mark.asyncio
async def test_knowledge_search_endpoint(
    test_app: FastAPI,
    mock_db_session: AsyncMock,
    mock_embedding_provider: AsyncMock,
) -> None:
    """Verify POST /api/v1/knowledge/search executes vector retrieval under tenant context."""
    tenant_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    agent_user = CurrentUser(
        user_id=agent_id,
        tenant_id=tenant_id,
        role=UserRole.SALES_AGENT.value,
        email="agent@test.com",
        is_active=True,
    )

    mock_chunk = KnowledgeEmbedding(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        document_name="FCR_Rules.txt",
        chunk_index=0,
        chunk_content="FCR allows duty exemption.",
        metadata_jsonb={},
    )
    mock_result = MagicMock()
    mock_result.all.return_value = [(mock_chunk, 0.88)]
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield mock_db_session

    test_app.dependency_overrides[get_db_session] = override_db
    test_app.dependency_overrides[get_current_user] = lambda: agent_user
    test_app.dependency_overrides[get_embedding_provider] = lambda: mock_embedding_provider

    search_payload = {
        "query_text": "FCR duty rules",
        "top_k": 5,
        "min_similarity": 0.5,
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/knowledge/search",
            json=search_payload,
            headers={"Authorization": "Bearer mock_token"},
        )

    test_app.dependency_overrides.clear()

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["document_name"] == "FCR_Rules.txt"
    assert results[0]["similarity_score"] == pytest.approx(0.88, abs=1e-2)


@pytest.mark.asyncio
async def test_knowledge_delete_chunk_endpoint(
    test_app: FastAPI,
    mock_db_session: AsyncMock,
) -> None:
    """Verify DELETE /api/v1/knowledge/{chunk_id} deletes specified chunk record."""
    tenant_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    admin_user = CurrentUser(
        user_id=admin_id,
        tenant_id=tenant_id,
        role=UserRole.TENANT_ADMIN.value,
        email="admin@test.com",
        is_active=True,
    )

    mock_chunk = KnowledgeEmbedding(
        id=chunk_id,
        tenant_id=tenant_id,
        document_name="Draft.pdf",
        chunk_content="Old draft text",
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_chunk
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    async def override_db() -> AsyncIterator[AsyncSession]:
        yield mock_db_session

    test_app.dependency_overrides[get_db_session] = override_db
    test_app.dependency_overrides[get_current_user] = lambda: admin_user

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        response = await client.delete(
            f"/api/v1/knowledge/{chunk_id}",
            headers={"Authorization": "Bearer mock_token"},
        )

    test_app.dependency_overrides.clear()

    assert response.status_code == 204
    mock_db_session.delete.assert_called_once_with(mock_chunk)
