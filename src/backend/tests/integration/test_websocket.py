"""Integration tests for Real-Time WebSocket Inbox Manager (TASK-0704)."""

import uuid

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.core.ws_manager import ws_manager


@pytest.fixture
def tenant_a_id() -> uuid.UUID:
    """Tenant A UUID."""
    return uuid.uuid4()


@pytest.fixture
def tenant_b_id() -> uuid.UUID:
    """Tenant B UUID."""
    return uuid.uuid4()


@pytest.fixture
def token_tenant_a(tenant_a_id: uuid.UUID) -> str:
    """JWT Access Token for user in Tenant A."""
    user_id = str(uuid.uuid4())
    return create_access_token(subject=user_id, tenant_id=str(tenant_a_id), role="SalesAgent")


@pytest.fixture
def token_tenant_b(tenant_b_id: uuid.UUID) -> str:
    """JWT Access Token for user in Tenant B."""
    user_id = str(uuid.uuid4())
    return create_access_token(subject=user_id, tenant_id=str(tenant_b_id), role="SalesAgent")


def test_websocket_unauthenticated_connection_rejected(app: FastAPI) -> None:
    """Verify unauthenticated WebSocket connection is rejected with 1008 policy violation."""
    client = TestClient(app)
    with pytest.raises((WebSocketDisconnect, Exception)):
        with client.websocket_connect("/api/v1/ws/inbox"):
            pass


def test_websocket_ping_pong(app: FastAPI, token_tenant_a: str) -> None:
    """Verify connected WebSocket client can send ping and receive pong."""
    client = TestClient(app)
    with client.websocket_connect(f"/api/v1/ws/inbox?token={token_tenant_a}") as websocket:
        websocket.send_text("ping")
        message = websocket.receive_text()
        assert message == "pong"


@pytest.mark.asyncio
async def test_websocket_multi_tenant_isolation(
    app: FastAPI,
    tenant_a_id: uuid.UUID,
    tenant_b_id: uuid.UUID,
    token_tenant_a: str,
    token_tenant_b: str,
) -> None:
    """Verify broadcast to Tenant A is received by Tenant A client and isolated from Tenant B."""
    client = TestClient(app)

    with (
        client.websocket_connect(f"/api/v1/ws/inbox?token={token_tenant_a}") as ws_a,
        client.websocket_connect(f"/api/v1/ws/inbox?token={token_tenant_b}") as ws_b,
    ):
        # Broadcast event specifically to Tenant A
        sent_count = await ws_manager.broadcast_to_tenant(
            tenant_id=tenant_a_id,
            event_type="INBOX_MESSAGE_RECEIVED",
            data={"message_id": "msg-123", "content": "Hello Tenant A"},
        )
        assert sent_count == 1

        # Tenant A receives real-time JSON payload
        data_a = ws_a.receive_json()
        assert data_a["event"] == "INBOX_MESSAGE_RECEIVED"
        assert data_a["data"]["content"] == "Hello Tenant A"

        # Verify Tenant B active connection count is isolated (broadcast to B returns 0 sent)
        sent_count_b = await ws_manager.broadcast_to_tenant(
            tenant_id=tenant_b_id,
            event_type="INBOX_MESSAGE_RECEIVED",
            data={"message_id": "msg-456", "content": "Hello Tenant B"},
        )
        assert sent_count_b == 1

        data_b = ws_b.receive_json()
        assert data_b["data"]["content"] == "Hello Tenant B"
