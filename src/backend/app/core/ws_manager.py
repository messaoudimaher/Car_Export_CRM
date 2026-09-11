"""WebSocket Connection Manager for multi-tenant real-time events (WS-07, TASK-0704)."""

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import WebSocket

from app.core.logging import logger


class ConnectionManager:
    """Manager tracking active WebSocket connections per tenant with strict isolation."""

    def __init__(self) -> None:
        """Initialize ConnectionManager with thread-safe tenant connection mapping."""
        self.active_connections: dict[UUID, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, tenant_id: UUID) -> None:
        """Accept WebSocket connection and register under specified tenant context.

        Args:
            websocket: Incoming FastAPI WebSocket connection.
            tenant_id: Authenticated tenant UUID context.
        """
        await websocket.accept()
        async with self._lock:
            if tenant_id not in self.active_connections:
                self.active_connections[tenant_id] = set()
            self.active_connections[tenant_id].add(websocket)

        logger.info(
            "WEBSOCKET_CONNECTED tenant_id=%s active_connections=%d",
            str(tenant_id),
            len(self.active_connections[tenant_id]),
        )

    async def disconnect(self, websocket: WebSocket, tenant_id: UUID) -> None:
        """Unregister and remove WebSocket connection from tenant pool.

        Args:
            websocket: Target WebSocket connection.
            tenant_id: Tenant UUID context.
        """
        async with self._lock:
            if tenant_id in self.active_connections:
                self.active_connections[tenant_id].discard(websocket)
                if not self.active_connections[tenant_id]:
                    del self.active_connections[tenant_id]

        logger.info("WEBSOCKET_DISCONNECTED tenant_id=%s", str(tenant_id))

    async def broadcast_to_tenant(
        self,
        tenant_id: UUID,
        event_type: str,
        data: dict[str, Any],
    ) -> int:
        """Broadcast real-time JSON event payload to all active tenant connections.

        Enforces strict multi-tenant boundary: connections outside tenant_id receive nothing.

        Args:
            tenant_id: Target tenant UUID.
            event_type: Event classification string (e.g. INBOX_MESSAGE_RECEIVED).
            data: Event data payload dictionary.

        Returns:
            int: Count of active tenant WebSocket clients notified.
        """
        async with self._lock:
            tenant_sockets = list(self.active_connections.get(tenant_id, set()))

        if not tenant_sockets:
            return 0

        payload = {
            "event": event_type,
            "data": data,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        stale_sockets: list[WebSocket] = []
        sent_count = 0

        for socket in tenant_sockets:
            try:
                await socket.send_json(payload)
                sent_count += 1
            except Exception as err:
                logger.warning(
                    "WEBSOCKET_BROADCAST_FAILED tenant_id=%s error=%s",
                    str(tenant_id),
                    str(err),
                )
                stale_sockets.append(socket)

        if stale_sockets:
            async with self._lock:
                for stale in stale_sockets:
                    if tenant_id in self.active_connections:
                        self.active_connections[tenant_id].discard(stale)

        logger.info(
            "WEBSOCKET_BROADCAST_COMPLETED tenant_id=%s event=%s sent_count=%d",
            str(tenant_id),
            event_type,
            sent_count,
        )
        return sent_count


ws_manager = ConnectionManager()
