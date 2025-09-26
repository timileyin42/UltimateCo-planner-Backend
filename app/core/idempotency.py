"""
Idempotency key system for preventing duplicate operations.
Primarily used for payment processing and other critical operations.
"""

from typing import Any, Dict, Optional, Union
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, String, DateTime, Text, Boolean, select, Index, text
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
import uuid
import json
import hashlib
import logging
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

class IdempotencyKey(Base):
    """Model for storing idempotency keys and their results."""
    
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        # Composite index for efficient lookups by key and resource type
        Index('idx_idempotency_key_resource_type', 'key', 'resource_type'),
        # Index for cleanup operations (finding expired keys)
        Index('idx_idempotency_expires_at', 'expires_at'),
        # Index for status-based queries
        Index('idx_idempotency_completed_created', 'is_completed', 'created_at'),
        # Partial index for active (non-expired) keys
        Index('idx_idempotency_active_keys', 'key', 'resource_type', 
              postgresql_where=text('expires_at > NOW()')),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(255), unique=True, index=True, nullable=False)
    resource_type = Column(String(100), nullable=False)  # e.g., 'payment', 'subscription'
    resource_id = Column(String(255), nullable=True)  # ID of created resource
    request_hash = Column(String(64), nullable=False)  # Hash of request parameters
    response_data = Column(Text, nullable=True)  # JSON response data
    status_code = Column(String(10), nullable=False, default='200')
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    
    def __repr__(self):
        return f"<IdempotencyKey(key='{self.key}', resource_type='{self.resource_type}')>"

class IdempotencyManager:
    """Manager for handling idempotency keys and preventing duplicate operations."""
    
    DEFAULT_EXPIRY_HOURS = 24
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    @staticmethod
    def generate_request_hash(request_data: Dict[str, Any]) -> str:
        """
        Generate a hash of the request data for comparison.
        
        Args:
            request_data: Dictionary of request parameters
            
        Returns:
            SHA-256 hash of the request data
        """
        # Sort the dictionary to ensure consistent hashing
        sorted_data = json.dumps(request_data, sort_keys=True, default=str)
        return hashlib.sha256(sorted_data.encode()).hexdigest()
    
    async def get_or_create_key(
        self,
        idempotency_key: str,
        resource_type: str,
        request_data: Dict[str, Any],
        expiry_hours: int = DEFAULT_EXPIRY_HOURS
    ) -> tuple[IdempotencyKey, bool]:
        """
        Get existing idempotency key or create a new one.
        
        Args:
            idempotency_key: The idempotency key string
            resource_type: Type of resource being created
            request_data: Request parameters for hashing
            expiry_hours: Hours until the key expires
            
        Returns:
            Tuple of (IdempotencyKey, is_new)
        """
        request_hash = self.generate_request_hash(request_data)
        
        # Check if key already exists
        stmt = select(IdempotencyKey).where(IdempotencyKey.key == idempotency_key)
        result = await self.db.execute(stmt)
        existing_key = result.scalar_one_or_none()
        
        if existing_key:
            # Check if the request data matches
            if existing_key.request_hash != request_hash:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "Idempotency key mismatch",
                        "message": "The same idempotency key was used with different request parameters"
                    }
                )
            
            # Check if key has expired
            if existing_key.expires_at < datetime.utcnow():
                # Remove expired key
                await self.db.delete(existing_key)
                await self.db.commit()
                existing_key = None
            else:
                return existing_key, False
        
        # Create new key if none exists or expired
        new_key = IdempotencyKey(
            key=idempotency_key,
            resource_type=resource_type,
            request_hash=request_hash,
            expires_at=datetime.utcnow() + timedelta(hours=expiry_hours)
        )
        
        self.db.add(new_key)
        await self.db.commit()
        await self.db.refresh(new_key)
        
        return new_key, True
    
    async def complete_operation(
        self,
        idempotency_key: str,
        resource_id: str,
        response_data: Dict[str, Any],
        status_code: int = 200
    ) -> bool:
        """
        Mark an idempotency key as completed with the operation result.
        
        Args:
            idempotency_key: The idempotency key string
            resource_id: ID of the created resource
            response_data: Response data to store
            status_code: HTTP status code
            
        Returns:
            True if successfully completed
        """
        stmt = select(IdempotencyKey).where(IdempotencyKey.key == idempotency_key)
        result = await self.db.execute(stmt)
        key_record = result.scalar_one_or_none()
        
        if not key_record:
            logger.error(f"Idempotency key not found: {idempotency_key}")
            return False
        
        key_record.resource_id = resource_id
        key_record.response_data = json.dumps(response_data, default=str)
        key_record.status_code = str(status_code)
        key_record.is_completed = True
        
        await self.db.commit()
        logger.info(f"Completed idempotency key: {idempotency_key}")
        return True
    
    async def get_completed_operation(
        self,
        idempotency_key: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the result of a completed operation.
        
        Args:
            idempotency_key: The idempotency key string
            
        Returns:
            Dictionary with operation result or None if not completed
        """
        stmt = select(IdempotencyKey).where(
            IdempotencyKey.key == idempotency_key,
            IdempotencyKey.is_completed == True
        )
        result = await self.db.execute(stmt)
        key_record = result.scalar_one_or_none()
        
        if not key_record:
            return None
        
        return {
            'resource_id': key_record.resource_id,
            'response_data': json.loads(key_record.response_data) if key_record.response_data else {},
            'status_code': int(key_record.status_code),
            'created_at': key_record.created_at.isoformat()
        }
    
    async def cleanup_expired_keys(self) -> int:
        """
        Clean up expired idempotency keys.
        
        Returns:
            Number of keys cleaned up
        """
        from sqlalchemy import delete
        
        stmt = delete(IdempotencyKey).where(
            IdempotencyKey.expires_at < datetime.utcnow()
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        
        cleaned_count = result.rowcount
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired idempotency keys")
        
        return cleaned_count

def validate_idempotency_key(key: str) -> bool:
    """
    Validate idempotency key format.
    
    Args:
        key: The idempotency key to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not key or not isinstance(key, str):
        return False
    
    # Key should be between 1 and 255 characters
    if len(key) < 1 or len(key) > 255:
        return False
    
    # Key should contain only alphanumeric characters, hyphens, and underscores
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', key):
        return False
    
    return True

def generate_idempotency_key(prefix: str = "") -> str:
    """
    Generate a new idempotency key.
    
    Args:
        prefix: Optional prefix for the key
        
    Returns:
        Generated idempotency key
    """
    key_uuid = str(uuid.uuid4())
    if prefix:
        return f"{prefix}_{key_uuid}"
    return key_uuid

# Decorator for idempotent operations
def idempotent_operation(resource_type: str, expiry_hours: int = 24):
    """
    Decorator to make operations idempotent.
    
    Args:
        resource_type: Type of resource being created
        expiry_hours: Hours until the key expires
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract idempotency key from kwargs
            idempotency_key = kwargs.pop('idempotency_key', None)
            db = kwargs.get('db')
            
            if not idempotency_key or not db:
                # If no idempotency key or db session, proceed normally
                return await func(*args, **kwargs)
            
            if not validate_idempotency_key(idempotency_key):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid idempotency key format"
                )
            
            manager = IdempotencyManager(db)
            
            # Check if operation already completed
            completed_result = await manager.get_completed_operation(idempotency_key)
            if completed_result:
                logger.info(f"Returning cached result for idempotency key: {idempotency_key}")
                return completed_result['response_data']
            
            # Get or create idempotency key
            request_data = {k: v for k, v in kwargs.items() if k != 'db'}
            key_record, is_new = await manager.get_or_create_key(
                idempotency_key, resource_type, request_data, expiry_hours
            )
            
            if not is_new and key_record.is_completed:
                # Return existing result
                return json.loads(key_record.response_data) if key_record.response_data else {}
            
            # Execute the operation
            try:
                result = await func(*args, **kwargs)
                
                # Store the result
                resource_id = result.get('id') if isinstance(result, dict) else str(result)
                await manager.complete_operation(
                    idempotency_key, resource_id, result if isinstance(result, dict) else {'result': result}
                )
                
                return result
            except Exception as e:
                logger.error(f"Operation failed for idempotency key {idempotency_key}: {e}")
                raise
        
        return wrapper
    return decorator