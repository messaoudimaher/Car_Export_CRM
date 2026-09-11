"""API v1 Main Router."""

from fastapi import APIRouter

from app.api.v1.conversations import router as conversations_router
from app.api.v1.customers import router as customers_router
from app.api.v1.health import router as health_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.websocket import router as websocket_router

api_v1_router = APIRouter(prefix="/api/v1")

# Include sub-routers
api_v1_router.include_router(health_router)
api_v1_router.include_router(customers_router)
api_v1_router.include_router(conversations_router)
api_v1_router.include_router(webhooks_router)
api_v1_router.include_router(websocket_router)
