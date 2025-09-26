from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.core.security import verify_token
from app.core.errors import http_401_unauthorized, http_403_forbidden
from app.services.user_service import UserService
from app.models.user_models import User

# Security scheme
security = HTTPBearer()

def get_db() -> Generator:
    """Database dependency"""
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

def get_current_user_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Extract and verify JWT token"""
    token = credentials.credentials
    user_id = verify_token(token)
    if user_id is None:
        raise http_401_unauthorized("Invalid authentication credentials")
    return user_id

def get_current_user(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_token)
) -> User:
    """Get current authenticated user"""
    user_service = UserService(db)
    user = user_service.get_user_by_id(int(user_id))
    if not user:
        raise http_401_unauthorized("User not found")
    if not user.is_active:
        raise http_403_forbidden("Inactive user")
    return user

def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise http_403_forbidden("Inactive user")
    return current_user

def get_current_superuser(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current superuser"""
    if not current_user.is_superuser:
        raise http_403_forbidden("Not enough permissions")
    return current_user

def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """Get user service instance"""
    return UserService(db)

def get_optional_current_user(
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """Get current user if authenticated, otherwise None"""
    if not credentials:
        return None
    
    try:
        user_id = verify_token(credentials.credentials)
        if user_id is None:
            return None
        
        user_service = UserService(db)
        user = user_service.get_user_by_id(int(user_id))
        return user if user and user.is_active else None
    except Exception:
        return None


async def get_current_user_websocket(token: str, db: Session) -> Optional[User]:
    """Get current user for WebSocket connections using token string."""
    try:
        user_id = verify_token(token)
        if user_id is None:
            return None
        
        user_service = UserService(db)
        user = user_service.get_user_by_id(int(user_id))
        return user if user and user.is_active else None
    except Exception:
        return None