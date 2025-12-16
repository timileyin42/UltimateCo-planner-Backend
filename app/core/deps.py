from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.core.security import verify_token
from app.core.errors import http_401_unauthorized, http_403_forbidden
from app.services.user_service import UserService
from app.models.user_models import User
from app.core.config import settings

# OAuth2 scheme for Swagger UI login
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token", auto_error=False)

def get_db() -> Generator:
    """Database dependency"""
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

def get_current_user_token(
    token: str = Depends(oauth2_scheme)
) -> str:
    """Extract and verify JWT token from OAuth2 scheme"""
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
    if not user.is_verified:
        method = "email" if user.signup_method == "email" else "phone number"
        raise http_403_forbidden(
            f"Account verification required. Please verify your {method} to access this feature."
        )
    return user

def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user"""
    return current_user

def get_current_verified_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current verified user - requires account verification via email (Resend) or SMS (Termii)"""
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
    token: Optional[str] = Depends(oauth2_scheme)
) -> Optional[User]:
    """Get current user if authenticated, otherwise None"""
    if not token:
        return None
    
    try:
        user_id = verify_token(token)
        if user_id is None:
            return None
        
        user_service = UserService(db)
        user = user_service.get_user_by_id(int(user_id))
        return user if user and user.is_active and user.is_verified else None
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