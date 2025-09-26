from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.api_router import api_router
from app.api.health import health_router
from app.core.config import settings

# Create FastAPI instance
app = FastAPI(
    title="Plan et al - Event Planning API",
    description="The Ultimate co-planner backend API",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

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

@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    print("Starting Plan et al API...")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    print("Shutting down Plan et al API...")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)