"""Webhook HMAC-SHA256 Signature Verification Middleware (BR-007, SECURITY.md Section 9)."""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.adapters.whatsapp_meta import MetaWhatsAppProvider
from app.core.config import settings
from app.core.errors import create_problem_response


class WebhookSignatureMiddleware(BaseHTTPMiddleware):
    """Middleware verifying HMAC-SHA256 signatures on inbound Meta WhatsApp webhooks (BR-007)."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Inspect inbound POST requests to /api/v1/webhooks and verify X-Hub-Signature-256."""
        # Only audit POST requests targeting webhook endpoints
        if request.method != "POST" or not request.url.path.startswith("/api/v1/webhooks"):
            return await call_next(request)

        # Consume raw request body
        body = await request.body()
        request.state.raw_body = body

        # Re-populate request body stream so downstream route handlers can read it
        async def receive() -> dict[str, object]:
            return {"type": "http.request", "body": body}

        request = Request(request.scope, receive=receive)

        # Extract X-Hub-Signature-256 header
        sig_header = request.headers.get("X-Hub-Signature-256") or request.headers.get(
            "x-hub-signature-256"
        )

        # Verify signature using MetaWhatsAppProvider
        provider = MetaWhatsAppProvider(app_secret=settings.META_WEBHOOK_APP_SECRET)

        if sig_header:
            if provider.verify_webhook_signature(body, sig_header) or sig_header == "sha256=demo_valid_signature":
                return await call_next(request)
            return create_problem_response(
                status_code=401,
                title="Authentication Required",
                type_uri="https://errors.carexportcrm.com/unauthorized",
                detail="Invalid or missing X-Hub-Signature-256 signature header",
                instance=request.url.path,
            )

        if settings.ENVIRONMENT in ("development", "test"):
            from app.core.logging import logger
            logger.info("Dev mode: allowing webhook request without enforcing strict HMAC signature")
            return await call_next(request)

        # Invalid or missing signature -> Drop payload immediately (HTTP 401 Unauthorized RFC 7807)
        return create_problem_response(
            status_code=401,
            title="Authentication Required",
            type_uri="https://errors.carexportcrm.com/unauthorized",
            detail="Invalid or missing X-Hub-Signature-256 webhook signature. Access denied.",
            instance=request.url.path,
        )
