from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.db.user_database import UserDatabase
from app.models.user_models import User, UserProfile
from app.schemas.user import (
    UserCreate, UserUpdate, UserPasswordUpdate, UserProfileCreate, UserProfileUpdate
)
from app.core.errors import NotFoundError, ValidationError, ConflictError
from app.core.security import verify_password, get_password_hash

class UserService:
    """Service for user-related business logic"""
    
    def __init__(self, db: Session):
        self.db = db
        self.user_db = UserDatabase(db)
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return self.user_db.get_user_by_id(user_id)
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return self.user_db.get_user_by_email(email)
    
    def get_users(
        self, 
        skip: int = 0, 
        limit: int = 100, 
        active_only: bool = True
    ) -> List[User]:
        """Get list of users with pagination"""
        query = self.db.query(User)
        
        if active_only:
            query = query.filter(User.is_active == True)
        
        return query.offset(skip).limit(limit).all()
    
    def create_user(self, user_data: UserCreate) -> User:
        """Create a new user"""
        # Validate passwords match
        if user_data.password != user_data.confirm_password:
            raise ValidationError("Passwords do not match")
        
        # Check if user already exists
        existing_user = self.user_db.get_user_by_email(user_data.email)
        if existing_user:
            raise ConflictError("User with this email already exists")
        
        # Check if username is taken (if provided)
        if user_data.username:
            existing_username = self.db.query(User).filter(
                User.username == user_data.username
            ).first()
            if existing_username:
                raise ConflictError("Username is already taken")
        
        # Create user
        return self.user_db.create_user(
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
            username=user_data.username,
            bio=user_data.bio,
            phone_number=user_data.phone_number,
            city=user_data.city,
            country=user_data.country,
            timezone=user_data.timezone,
            is_public_profile=user_data.is_public_profile
        )
    
    def update_user(self, user_id: int, user_data: UserUpdate) -> User:
        """Update user information"""
        user = self.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        
        # Check if username is taken (if being updated)
        if user_data.username and user_data.username != user.username:
            existing_username = self.db.query(User).filter(
                and_(
                    User.username == user_data.username,
                    User.id != user_id
                )
            ).first()
            if existing_username:
                raise ConflictError("Username is already taken")
        
        # Update user fields
        update_data = user_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(user, field):
                setattr(user, field, value)
        
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def update_user_password(self, user_id: int, password_data: UserPasswordUpdate) -> bool:
        """Update user password"""
        user = self.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        
        # Validate passwords match
        if password_data.new_password != password_data.confirm_new_password:
            raise ValidationError("New passwords do not match")
        
        # Verify current password
        if not verify_password(password_data.current_password, user.hashed_password):
            raise ValidationError("Current password is incorrect")
        
        # Update password
        user.hashed_password = get_password_hash(password_data.new_password)
        self.db.commit()
        
        return True
    
    def deactivate_user(self, user_id: int) -> User:
        """Deactivate user account"""
        user = self.user_db.deactivate_user(user_id)
        if not user:
            raise NotFoundError("User not found")
        return user
    
    def activate_user(self, user_id: int) -> User:
        """Activate user account"""
        user = self.user_db.activate_user(user_id)
        if not user:
            raise NotFoundError("User not found")
        return user
    
    def delete_user(self, user_id: int) -> bool:
        """Delete user (soft delete)"""
        return self.user_db.delete_user(user_id)
    
    def search_users(
        self, 
        query: str, 
        skip: int = 0, 
        limit: int = 100,
        current_user_id: Optional[int] = None
    ) -> List[User]:
        """Search users by name or email"""
        users = self.user_db.search_users(query, skip, limit)
        
        # Filter out current user from results
        if current_user_id:
            users = [user for user in users if user.id != current_user_id]
        
        return users
    
    def get_user_stats(self, user_id: int) -> dict:
        """Get user statistics"""
        user = self.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        
        # Count events created
        total_events_created = len(user.created_events)
        
        # Count events attended (accepted invitations)
        total_events_attended = len([
            inv for inv in user.event_invitations 
            if inv.rsvp_status == "accepted"
        ])
        
        # Count completed tasks
        total_tasks_completed = len([
            task for task in user.assigned_tasks 
            if task.status == "completed"
        ])
        
        # Count friends
        total_friends = len(user.friends)
        
        return {
            "total_events_created": total_events_created,
            "total_events_attended": total_events_attended,
            "total_tasks_completed": total_tasks_completed,
            "total_friends": total_friends,
            "member_since": user.created_at
        }
    
    # User Profile methods
    def get_user_profile(self, user_id: int) -> Optional[UserProfile]:
        """Get user profile"""
        return self.db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()
    
    def create_user_profile(self, user_id: int, profile_data: UserProfileCreate) -> UserProfile:
        """Create user profile"""
        # Check if user exists
        user = self.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        
        # Check if profile already exists
        existing_profile = self.get_user_profile(user_id)
        if existing_profile:
            raise ConflictError("User profile already exists")
        
        # Create profile
        profile = UserProfile(
            user_id=user_id,
            **profile_data.model_dump()
        )
        
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        
        return profile
    
    def update_user_profile(self, user_id: int, profile_data: UserProfileUpdate) -> UserProfile:
        """Update user profile"""
        profile = self.get_user_profile(user_id)
        if not profile:
            raise NotFoundError("User profile not found")
        
        # Update profile fields
        update_data = profile_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(profile, field):
                setattr(profile, field, value)
        
        self.db.commit()
        self.db.refresh(profile)
        
        return profile
    
    # Friend management methods
    def add_friend(self, user_id: int, friend_id: int) -> bool:
        """Add friend relationship"""
        if user_id == friend_id:
            raise ValidationError("Cannot add yourself as a friend")
        
        user = self.get_user_by_id(user_id)
        friend = self.get_user_by_id(friend_id)
        
        if not user or not friend:
            raise NotFoundError("User not found")
        
        # Check if already friends
        if user.is_friend_with(friend_id):
            raise ConflictError("Users are already friends")
        
        # Add friendship (bidirectional)
        user.friends.append(friend)
        friend.friends.append(user)
        
        self.db.commit()
        return True
    
    def remove_friend(self, user_id: int, friend_id: int) -> bool:
        """Remove friend relationship"""
        user = self.get_user_by_id(user_id)
        friend = self.get_user_by_id(friend_id)
        
        if not user or not friend:
            raise NotFoundError("User not found")
        
        # Check if they are friends
        if not user.is_friend_with(friend_id):
            raise ValidationError("Users are not friends")
        
        # Remove friendship (bidirectional)
        user.friends.remove(friend)
        friend.friends.remove(user)
        
        self.db.commit()
        return True
    
    def get_user_friends(self, user_id: int, skip: int = 0, limit: int = 100) -> List[User]:
        """Get user's friends list"""
        user = self.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        
        # Get friends with pagination
        friends = user.friends[skip:skip + limit]
        return friends
    
    def get_mutual_friends(self, user_id: int, other_user_id: int) -> List[User]:
        """Get mutual friends between two users"""
        user = self.get_user_by_id(user_id)
        other_user = self.get_user_by_id(other_user_id)
        
        if not user or not other_user:
            raise NotFoundError("User not found")
        
        # Find mutual friends
        user_friend_ids = {friend.id for friend in user.friends}
        other_friend_ids = {friend.id for friend in other_user.friends}
        
        mutual_friend_ids = user_friend_ids.intersection(other_friend_ids)
        
        # Get mutual friends
        mutual_friends = self.db.query(User).filter(
            User.id.in_(mutual_friend_ids)
        ).all()
        
        return mutual_friends
    
    def suggest_friends(self, user_id: int, limit: int = 10) -> List[User]:
        """Suggest potential friends based on mutual connections"""
        user = self.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        
        # Get friends of friends who are not already friends
        current_friend_ids = {friend.id for friend in user.friends}
        current_friend_ids.add(user_id)  # Exclude self
        
        # Find users who are friends with current user's friends
        suggested_users = self.db.query(User).join(
            User.friends
        ).filter(
            User.friends.any(User.id.in_([friend.id for friend in user.friends])),
            ~User.id.in_(current_friend_ids),
            User.is_active == True
        ).distinct().limit(limit).all()
        
        return suggested_users
    
    def get_users_count(self, active_only: bool = True) -> int:
        """Get total count of users"""
        query = self.db.query(User)
        
        if active_only:
            query = query.filter(User.is_active == True)
        
        return query.count()