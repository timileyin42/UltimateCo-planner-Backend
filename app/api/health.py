from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.deps import get_db
from app.core.config import settings
from datetime import datetime
import psutil
import os

health_router = APIRouter()

@health_router.get("/")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "Plan et al API",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }

@health_router.get("/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """Detailed health check with system information"""
    try:
        # Test database connection
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # Get system information
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        "status": "healthy" if db_status == "healthy" else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "Plan et al API",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "checks": {
            "database": db_status,
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent
            },
            "disk": {
                "total": disk.total,
                "free": disk.free,
                "percent": (disk.used / disk.total) * 100
            }
        },
        "uptime": datetime.utcnow().isoformat(),
        "process_id": os.getpid()
    }

@health_router.get("/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """Readiness check for Kubernetes/Docker"""
    try:
        # Test database connection
        db.execute("SELECT 1")
        return {"status": "ready"}
    except Exception:
        return {"status": "not ready"}

@health_router.get("/live")
async def liveness_check():
    """Liveness check for Kubernetes/Docker"""
    return {"status": "alive"}