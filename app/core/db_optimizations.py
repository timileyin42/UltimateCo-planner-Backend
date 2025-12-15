"""
Database Optimizations Module

This module implements advanced database optimizations including:
1. Composite indexes for frequently queried fields
2. Query result caching for frequently accessed data
3. Read replica configuration
"""

from sqlalchemy import text, Index, Table, MetaData
from sqlalchemy.orm import Session
from functools import wraps
from typing import Dict, Any, Callable, List, Optional, Union
import time
import logging
import redis
import json
import hashlib
import pickle
from datetime import timedelta

from app.core.config import settings
from app.core.database import engine, Base
from app.db.session import SessionLocal

# Setup logging
logger = logging.getLogger(__name__)

# Redis client for caching
redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=False,  # Keep binary data for pickle
    socket_timeout=5,
    socket_connect_timeout=5
)


def create_composite_indexes():
    """
    Create composite indexes for frequently queried fields.
    This function should be called during application startup.
    """
    # Connect to the database
    with engine.connect() as connection:
        # Event-related composite indexes
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_event_date_location_type 
            ON events (start_datetime, venue_city, event_type);
        """))
        
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_event_creator_date_status 
            ON events (creator_id, start_datetime, status);
        """))
        
        # User-related composite indexes
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_location_active 
            ON users (city, country, is_active);
        """))
        
        # Vendor-related composite indexes
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_vendor_category_rating_location 
            ON vendors (category, average_rating, city);
        """))
        
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_vendor_booking_date_status_vendor 
            ON vendor_bookings (service_date, status, vendor_id);
        """))
        
        # Notification-related composite indexes
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_notification_user_type_status 
            ON notification_logs (recipient_id, notification_type, status);
        """))
        
        # Message-related composite indexes
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_message_event_created 
            ON messages (event_id, created_at);
        """))
        
        # Timeline-related composite indexes
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_timeline_event_status 
            ON timeline_items (timeline_id, status);
        """))
        
        connection.commit()
        
        logger.info("Created composite indexes for frequently queried fields")


def cache_result(ttl_seconds: int = 300, prefix: str = "cache"):
    """
    Decorator to cache function results in Redis.
    
    Args:
        ttl_seconds: Time-to-live in seconds for cached results
        prefix: Cache key prefix
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Skip caching if Redis is not available
            if not is_redis_available():
                return func(*args, **kwargs)
            
            # Generate cache key
            cache_key = _generate_cache_key(func, args, kwargs, prefix)
            
            # Try to get from cache
            cached_result = redis_client.get(cache_key)
            if cached_result:
                try:
                    return pickle.loads(cached_result)
                except Exception as e:
                    logger.warning(f"Failed to load cached result: {e}")
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            try:
                redis_client.setex(
                    cache_key,
                    ttl_seconds,
                    pickle.dumps(result)
                )
            except Exception as e:
                logger.warning(f"Failed to cache result: {e}")
            
            return result
        return wrapper
    return decorator

def invalidate_cache(prefix: str, pattern: Optional[str] = None):
    """
    Invalidate cache entries by prefix and optional pattern.
    
    Args:
        prefix: Cache key prefix
        pattern: Optional pattern to match keys
    """
    if not is_redis_available():
        return
    
    try:
        if pattern:
            keys = redis_client.keys(f"{prefix}:{pattern}*")
        else:
            keys = redis_client.keys(f"{prefix}:*")
        
        if keys:
            redis_client.delete(*keys)
            logger.info(f"Invalidated {len(keys)} cache entries with prefix '{prefix}'")
    except Exception as e:
        logger.warning(f"Failed to invalidate cache: {e}")

def _generate_cache_key(func: Callable, args: tuple, kwargs: Dict[str, Any], prefix: str) -> str:
    """Generate a unique cache key for a function call"""
    # Create a string representation of the function and its arguments
    key_parts = [func.__module__, func.__name__]
    
    # Add args and kwargs to key parts
    for arg in args:
        if hasattr(arg, '__dict__'):
            # For objects, use their class name and id
            key_parts.append(f"{arg.__class__.__name__}:{id(arg)}")
        else:
            key_parts.append(str(arg))
    
    # Sort kwargs for consistent keys
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}:{v}")
    
    # Join parts and hash
    key_str = ":".join(key_parts)
    hashed = hashlib.md5(key_str.encode()).hexdigest()
    
    return f"{prefix}:{hashed}"

def is_redis_available() -> bool:
    """Check if Redis is available"""
    try:
        return redis_client.ping()
    except:
        return False


class ReadReplicaManager:
    """
    Manages database read replicas for distributing read queries.
    
    This class provides:
    1. Connection management for read replicas
    2. Load balancing across replicas
    3. Fallback to primary when replicas are unavailable
    """
    
    def __init__(self):
        """Initialize the read replica manager"""
        self.replica_engines = []
        self.current_replica = 0
        self.initialized = False
    
    def initialize(self, replica_urls: List[str]):
        """
        Initialize read replica connections.
        
        Args:
            replica_urls: List of database URLs for read replicas
        """
        if self.initialized:
            return
        
        for url in replica_urls:
            try:
                replica_engine = create_engine(
                    url,
                    connect_args={
                        "options": "-c default_transaction_isolation=read_committed",
                        "application_name": "ultimateco_planner_replica",
                        "connect_timeout": 10,
                        "command_timeout": 30,
                    } if "sqlite" not in url else {"check_same_thread": False},
                    echo=settings.DEBUG,
                    pool_size=10,
                    max_overflow=20,
                    pool_timeout=30,
                    pool_recycle=3600,
                    pool_pre_ping=True
                )
                
                # Test connection
                with replica_engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                
                self.replica_engines.append(replica_engine)
                logger.info(f"Initialized read replica: {url}")
            except Exception as e:
                logger.error(f"Failed to initialize read replica {url}: {e}")
        
        self.initialized = True
        logger.info(f"Initialized {len(self.replica_engines)} read replicas")
    
    def get_read_session(self):
        """
        Get a session connected to a read replica.
        Uses round-robin to distribute load across replicas.
        Falls back to primary if no replicas are available.
        """
        if not self.replica_engines:
            # Fallback to primary
            return SessionLocal()
        
        # Round-robin selection
        replica_engine = self.replica_engines[self.current_replica]
        self.current_replica = (self.current_replica + 1) % len(self.replica_engines)
        
        # Create session
        ReplicaSession = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=replica_engine
        )
        
        return ReplicaSession()

# Global instance
read_replica_manager = ReadReplicaManager()

def get_read_db():
    """
    Database dependency for read operations.
    Uses read replicas when available.
    """
    db = read_replica_manager.get_read_session()
    try:
        yield db
    finally:
        db.close()

