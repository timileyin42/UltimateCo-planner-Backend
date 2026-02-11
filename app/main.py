from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import asyncio
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.api_router import api_router
from app.api.public_routes import router as public_router
from app.api.health import health_router
from app.core.config import settings
from app.services.redis_subscriber import start_redis_listener, stop_redis_listener
from app.core.db_optimizations import create_composite_indexes, read_replica_manager
from app.core.rate_limiter import limiter, rate_limit_exceeded_handler
from app.core.logger import get_logger

logger = get_logger(__name__)

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

# Rate limiting middleware and handlers
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Custom validation error handler to return simple string messages
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return simple string error messages for validation errors"""
    errors = exc.errors()
    if errors:
        # Get the first error message
        first_error = errors[0]
        error_msg = first_error.get('msg', 'Validation error')
        
        # If it's a ValueError from model_validator, extract the actual message
        if 'Value error' in error_msg and 'ctx' in first_error:
            ctx = first_error.get('ctx', {})
            if 'error' in ctx:
                error_obj = ctx['error']
                if hasattr(error_obj, 'args') and error_obj.args:
                    error_msg = str(error_obj.args[0])
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": error_msg}
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error"}
    )

# Include routers
app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(public_router)
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

    if settings.GEOAPIFY_API_KEY:
        logger.info("Geoapify Places API configured")
    else:
        logger.warning("Geoapify Places API key missing")

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
