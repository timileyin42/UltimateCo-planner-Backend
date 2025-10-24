from fastapi import APIRouter
from app.api.v1.routers.auth import auth_router
from app.api.v1.routers.users import users_router
from app.api.v1.routers.events import events_router
from app.api.v1.routers.ai import ai_router
from app.api.v1.routers.ai_chat import ai_chat_router
from app.api.v1.routers.messages import messages_router
from app.api.v1.routers.creative import creative_router
from app.api.v1.routers.timeline import timeline_router
from app.api.v1.routers.notifications import notifications_router
from app.api.v1.routers.vendors import vendors_router
from app.api.v1.routers.subscription import subscription_router
from app.api.v1.routers.invites import router as invites_router
from app.api.v1.routers.calendar import router as calendar_router
from app.api.v1.routers.contacts import router as contacts_router
from app.api.v1.routers.biometric import router as biometric_router
from app.api.v1.devices import router as devices_router
from app.api.v1.routers.websocket import websocket_router
from app.api.v1.webhooks import router as webhooks_router

api_router = APIRouter()

# Include all routers with their prefixes and tags
api_router.include_router(
    auth_router,
    prefix="/auth",
    tags=["authentication"]
)

api_router.include_router(
    users_router,
    prefix="/users",
    tags=["users"]
)

api_router.include_router(
    events_router,
    prefix="/events",
    tags=["events"]
)

api_router.include_router(
    ai_router,
    prefix="/ai",
    tags=["ai"]
)

api_router.include_router(
    ai_chat_router,
    prefix="/ai-chat",
    tags=["ai-chat"]
)

api_router.include_router(
    messages_router,
    prefix="/messages",
    tags=["messages"]
)

api_router.include_router(
    creative_router,
    prefix="/creative",
    tags=["creative"]
)

api_router.include_router(
    timeline_router,
    prefix="/timeline",
    tags=["timeline"]
)

api_router.include_router(
    notifications_router,
    prefix="/notifications",
    tags=["notifications"]
)

api_router.include_router(
    vendors_router,
    prefix="/vendors",
    tags=["vendors"]
)

api_router.include_router(
    subscription_router,
    prefix="/subscription",
    tags=["subscription"]
)

api_router.include_router(
    calendar_router,
    prefix="/calendar",
    tags=["calendar"]
)

api_router.include_router(
    invites_router,
    tags=["invites"]
)

api_router.include_router(
    contacts_router,
    prefix="/contacts",
    tags=["contacts"]
)

api_router.include_router(
    biometric_router,
    prefix="/biometric",
    tags=["biometric"]
)

api_router.include_router(
    devices_router,
    tags=["devices"]
)

api_router.include_router(
    websocket_router,
    prefix="/ws",
    tags=["websocket"]
)

api_router.include_router(
    webhooks_router,
    prefix="/webhooks",
    tags=["webhooks"]
)

# Root endpoint for API version info
@api_router.get("/")
async def api_info():
    """Get API version information"""
    return {
        "name": "Plan et al API",
        "version": "1.0.0",
        "description": "The Ultimate co-planner backend API",
        "endpoints": {
            "authentication": "/auth",
            "users": "/users",
            "events": "/events",
            "messages": "/messages",
            "creative": "/creative",
            "timeline": "/timeline",
            "notifications": "/notifications",
            "vendors": "/vendors",
            "subscription": "/subscription",
            "calendar": "/calendar",
            "invites": "/invites",
            "contacts": "/contacts",
            "biometric": "/biometric",
            "devices": "/devices",
            "ai": "/ai",
            "ai-chat": "/ai-chat",
            "health": "/health"
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        }
    }