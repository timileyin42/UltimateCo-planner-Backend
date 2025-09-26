from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, select
from fastapi import HTTPException
from app.models.user_models import User
from app.schemas.user import UserCreate
from app.core.security import get_password_hash, verify_password

class UserDatabase:
    """Domain-specific database helper for users"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_user(self, user_data: UserCreate) -> User:
        """Create a new user"""
        # Check if user already exists by email or phone
        if user_data.email:
            existing_user = self.get_user_by_email(user_data.email)
            if existing_user:
                raise HTTPException(
                    status_code=400,
                    detail="User with this email already exists"
                )
        
        if user_data.phone_number:
            existing_user = self.get_user_by_phone(user_data.phone_number)
            if existing_user:
                raise HTTPException(
                    status_code=400,
                    detail="User with this phone number already exists"
                )
        
        # Hash the password
        hashed_password = get_password_hash(user_data.password)
        
        # Determine signup method based on provided data
        signup_method = "phone" if user_data.phone_number and not user_data.email else "email"
        
        # Create user object
        db_user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            phone_number=user_data.phone_number,
            signup_method=signup_method,
            is_active=True
        )
        
        # Add to database
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        
        return db_user
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return self.db.query(User).filter(User.email == email).first()
    
    def get_user_by_phone(self, phone_number: str) -> Optional[User]:
        """Get user by phone number"""
        return self.db.query(User).filter(User.phone_number == phone_number).first()
    
    def get_user_by_email_or_phone(self, email: Optional[str] = None, phone_number: Optional[str] = None) -> Optional[User]:
        """Get user by email or phone number"""
        if email:
            return self.get_user_by_email(email)
        elif phone_number:
            return self.get_user_by_phone(phone_number)
        return None
    
    def get_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Get list of users with pagination"""
        return self.db.query(User).offset(skip).limit(limit).all()
    
    def update_user(self, user_id: int, **kwargs) -> Optional[User]:
        """Update user information"""
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def update_user_password(self, user_id: int, new_password: str) -> Optional[User]:
        """Update user password"""
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        
        user.hashed_password = get_password_hash(new_password)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def authenticate_user(self, identifier: str, password: str) -> Optional[User]:
        """Authenticate user by email/phone and password"""
        # Try to determine if identifier is email or phone
        if "@" in identifier:
            user = self.get_user_by_email(identifier)
        else:
            user = self.get_user_by_phone(identifier)
        
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
    
    def authenticate_user_by_phone(self, phone_number: str, password: str) -> Optional[User]:
        """Authenticate user by phone number and password"""
        user = self.get_user_by_phone(phone_number)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
    
    def deactivate_user(self, user_id: int) -> Optional[User]:
        """Deactivate user account"""
        return self.update_user(user_id, is_active=False)
    
    def activate_user(self, user_id: int) -> Optional[User]:
        """Activate user account"""
        return self.update_user(user_id, is_active=True)
    
    def delete_user(self, user_id: int) -> bool:
        """Delete user (soft delete by deactivating)"""
        user = self.deactivate_user(user_id)
        return user is not None
    
    def search_users(self, query: str, skip: int = 0, limit: int = 100) -> List[User]:
        """Search users by name, email, or phone number"""
        search_filter = or_(
            User.full_name.ilike(f"%{query}%"),
            User.email.ilike(f"%{query}%"),
            User.phone_number.ilike(f"%{query}%")
        )
        return (
            self.db.query(User)
            .filter(and_(User.is_active == True, search_filter))
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_active_users_count(self) -> int:
        """Get count of active users"""
        return self.db.query(User).filter(User.is_active == True).count()