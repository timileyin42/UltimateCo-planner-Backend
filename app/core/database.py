"""
Database configuration and dependencies.
This module provides database session management and utilities.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from app.core.config import settings
from app.core.logger import get_logger

# Setup logging
logger = get_logger(__name__)

# Create Base class for models
Base = declarative_base()

# Configure connect_args based on database type
if "sqlite" in settings.DATABASE_URL:
    connect_args = {"check_same_thread": False}
else:
    # PostgreSQL-specific connection arguments
    connect_args = {
        "application_name": "ultimateco_planner",
        "connect_timeout": 10,
    }

# Synchronous database setup
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=40,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Asynchronous database setup
async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=30,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True
)

AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Database dependency for write operations (uses primary database)
def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Async database dependency
async def get_async_db():
    """Get async database session"""
    async with AsyncSessionLocal() as session:
        yield session
        
# Read replica configuration will be imported from db_optimizations.py
# This avoids circular imports while making the read replica functionality available