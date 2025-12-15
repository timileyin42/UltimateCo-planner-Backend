from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
import asyncio
import logging

from app.api.v1.api_router import api_router
from app.api.health import health_router
from app.core.config import settings
from app.services.redis_subscriber import start_redis_listener, stop_redis_listener
from app.core.db_optimizations import create_composite_indexes, read_replica_manager

logger = logging.getLogger(__name__)

# Create FastAPI instance
app = FastAPI(
    title="Plan et al - Event Planning API",
    description="The Ultimate co-planner backend API",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Custom OpenAPI schema to configure OAuth2 password flow
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Plan et al - Event Planning API",
        version="1.0.0",
        description="The Ultimate co-planner backend API",
        routes=app.routes,
    )
    
    # Add OAuth2 password flow security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "OAuth2PasswordBearer": {
            "type": "oauth2",
            "flows": {
                "password": {
                    "tokenUrl": f"{settings.API_V1_STR}/auth/token",
                    "scopes": {}
                }
            }
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(api_router, prefix=settings.API_V1_STR)

# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """Root endpoint - Welcome message"""
    return {
        "app_name": settings.PROJECT_NAME,
        "version": "1.0.0",
        "status": "running",
        "message": "Welcome to Plan et al - The Ultimate Co-planner Backend API",
        "docs": f"{settings.API_V1_STR.rstrip('/api/v1')}/docs",
        "health": "/health"
    }

@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    logger.info("Starting Plan et al API...")
    
    # Start Redis pub/sub listener in background
    try:
        asyncio.create_task(start_redis_listener())
        logger.info("Started Redis pub/sub listener for real-time updates")
    except Exception as e:
        logger.error(f"Failed to start Redis listener: {str(e)}")
    
    # Create composite indexes
    try:
        create_composite_indexes()
        logger.info("Successfully created composite indexes")
    except Exception as e:
        logger.error(f"Failed to create composite indexes: {e}")
    
    # Initialize read replicas if configured
    if hasattr(settings, "READ_REPLICA_URLS") and settings.READ_REPLICA_URLS:
        try:
            read_replica_manager.initialize(settings.READ_REPLICA_URLS)
            logger.info(f"Initialized {len(settings.READ_REPLICA_URLS)} read replicas")
        except Exception as e:
            logger.error(f"Failed to initialize read replicas: {e}")
    else:
        logger.info("No read replicas configured")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    logger.info("Shutting down Plan et al API...")
    
    # Stop Redis pub/sub listener
    try:
        await stop_redis_listener()
        logger.info("Stopped Redis pub/sub listener")
    except Exception as e:
        logger.error(f"Error stopping Redis listener: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
