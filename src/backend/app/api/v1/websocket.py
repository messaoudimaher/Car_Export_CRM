"""Real-Time WebSocket Inbox Endpoint & Authentication Guard (WS-07, TASK-0704)."""

from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.errors import UnauthorizedException
from app.core.logging import logger
from app.core.security import decode_access_token
from app.core.ws_manager import ws_manager

router = APIRouter(prefix="/ws", tags=["WebSocket"])


def authenticate_websocket_token(token: str | None) -> tuple[UUID, UUID]:
    """Authenticate WebSocket connection query token and return (user_id, tenant_id).

    Args:
        token: Base64 JWT access token string from query parameter.

    Raises:
        UnauthorizedException: If token is missing, invalid, or expired.

    Returns:
        tuple[UUID, UUID]: Authenticated (user_id, tenant_id) tuple.
    """
    if not token or not token.strip():
        raise UnauthorizedException("Missing required token parameter for WebSocket connection.")

    claims = decode_access_token(token.strip())
    try:
        user_id = UUID(claims["sub"])
        tenant_id = UUID(claims["tenant_id"])
        return user_id, tenant_id
    except (KeyError, ValueError) as err:
        raise UnauthorizedException("Invalid WebSocket authentication token payload.") from err


@router.websocket("/inbox")
async def websocket_inbox_endpoint(
    websocket: WebSocket,
    token: str | None = Query(None, description="Bearer JWT Access Token"),
) -> None:
    """Real-time operational inbox WebSocket connection endpoint.

    Authenticates token, scopes connection to tenant_id, and broadcasts inbox events.
    """
    try:
        user_id, tenant_id = authenticate_websocket_token(token)
    except UnauthorizedException as exc:
        logger.warning(
            "WEBSOCKET_AUTH_FAILED path=%s detail=%s",
            websocket.url.path,
            exc.detail,
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=exc.detail)
        return

    await ws_manager.connect(websocket, tenant_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data.strip().lower() == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, tenant_id)
    except Exception as err:
        logger.warning(
            "WEBSOCKET_ERROR tenant_id=%s user_id=%s error=%s",
            str(tenant_id),
            str(user_id),
            str(err),
        )
        await ws_manager.disconnect(websocket, tenant_id)
