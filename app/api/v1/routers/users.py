from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from app.core.deps import get_db, get_current_user, get_current_active_user
from app.core.errors import (
    http_400_bad_request, http_404_not_found, http_409_conflict
)
from app.services.user_service import UserService
from app.schemas.user import (
    UserResponse, UserPublicResponse, UserSummary, UserUpdate, 
    UserPasswordUpdate, UserProfileCreate, UserProfileUpdate, UserProfileResponse,
    UserSearchQuery, UserListResponse, UserStatsResponse, FriendRequest, 
    FriendResponse, FriendListResponse
)
from app.schemas.pagination import PaginatedResponse, PaginationParams
from app.models.user_models import User

users_router = APIRouter()

@users_router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user's full profile"""
    return current_user

@users_router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile"""
    try:
        user_service = UserService(db)
        updated_user = user_service.update_user(current_user.id, user_data)
        return updated_user
    except Exception as e:
        if "already taken" in str(e).lower():
            raise http_409_conflict(str(e))
        else:
            raise http_400_bad_request("Failed to update user profile")

@users_router.put("/me/password")
async def update_current_user_password(
    password_data: UserPasswordUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update current user's password"""
    try:
        user_service = UserService(db)
        success = user_service.update_user_password(current_user.id, password_data)
        return {
            "message": "Password updated successfully",
            "success": success
        }
    except Exception as e:
        if "do not match" in str(e).lower():
            raise http_400_bad_request("Passwords do not match")
        elif "incorrect" in str(e).lower():
            raise http_400_bad_request("Current password is incorrect")
        else:
            raise http_400_bad_request("Failed to update password")

@users_router.delete("/me")
async def deactivate_current_user(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Deactivate current user's account"""
    try:
        user_service = UserService(db)
        user_service.deactivate_user(current_user.id)
        return {
            "message": "Account deactivated successfully"
        }
    except Exception:
        raise http_400_bad_request("Failed to deactivate account")

@users_router.get("/me/stats", response_model=UserStatsResponse)
async def get_current_user_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's statistics"""
    try:
        user_service = UserService(db)
        stats = user_service.get_user_stats(current_user.id)
        return stats
    except Exception:
        raise http_400_bad_request("Failed to retrieve user statistics")

@users_router.get("/search", response_model=UserListResponse)
async def search_users(
    q: str = Query(..., min_length=1, max_length=100, description="Search query"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Search users by name, email, or username"""
    try:
        user_service = UserService(db)
        users = user_service.search_users(
            query=q,
            skip=offset,
            limit=limit,
            current_user_id=current_user.id
        )
        
        # Convert to public response format
        public_users = [UserPublicResponse.model_validate(user) for user in users]
        
        return UserListResponse(
            users=public_users,
            total=len(public_users),
            limit=limit,
            offset=offset
        )
    except Exception:
        raise http_400_bad_request("Search failed")

@users_router.get("/{user_id}", response_model=UserPublicResponse)
async def get_user_by_id(
    user_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user by ID (public information only)"""
    try:
        user_service = UserService(db)
        user = user_service.get_user_by_id(user_id)
        
        if not user:
            raise http_404_not_found("User not found")
        
        # Only return public information
        return UserPublicResponse.model_validate(user)
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("User not found")
        else:
            raise http_400_bad_request("Failed to retrieve user")

@users_router.get("/{user_id}/stats", response_model=UserStatsResponse)
async def get_user_stats(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user statistics (public stats only)"""
    try:
        user_service = UserService(db)
        user = user_service.get_user_by_id(user_id)
        
        if not user:
            raise http_404_not_found("User not found")
        
        # Only show public stats if not the current user
        if user_id != current_user.id and not user.is_public_profile:
            raise http_400_bad_request("User profile is private")
        
        stats = user_service.get_user_stats(user_id)
        return stats
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("User not found")
        elif "private" in str(e).lower():
            raise http_400_bad_request("User profile is private")
        else:
            raise http_400_bad_request("Failed to retrieve user statistics")

# User Profile endpoints
@users_router.get("/me/profile", response_model=UserProfileResponse)
async def get_current_user_profile_details(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's detailed profile"""
    try:
        user_service = UserService(db)
        profile = user_service.get_user_profile(current_user.id)
        
        if not profile:
            raise http_404_not_found("User profile not found")
        
        return profile
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("User profile not found")
        else:
            raise http_400_bad_request("Failed to retrieve user profile")

@users_router.post("/me/profile", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_current_user_profile(
    profile_data: UserProfileCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create current user's detailed profile"""
    try:
        user_service = UserService(db)
        profile = user_service.create_user_profile(current_user.id, profile_data)
        return profile
    except Exception as e:
        if "already exists" in str(e).lower():
            raise http_409_conflict("User profile already exists")
        else:
            raise http_400_bad_request("Failed to create user profile")

@users_router.put("/me/profile", response_model=UserProfileResponse)
async def update_current_user_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update current user's detailed profile"""
    try:
        user_service = UserService(db)
        profile = user_service.update_user_profile(current_user.id, profile_data)
        return profile
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("User profile not found")
        else:
            raise http_400_bad_request("Failed to update user profile")

# Friend management endpoints
@users_router.get("/me/friends", response_model=FriendListResponse)
async def get_current_user_friends(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's friends list"""
    try:
        user_service = UserService(db)
        friends = user_service.get_user_friends(
            current_user.id,
            skip=offset,
            limit=limit
        )
        
        # Convert to friend response format
        friend_responses = []
        for friend in friends:
            friend_responses.append(FriendResponse(
                id=friend.id,
                full_name=friend.full_name,
                username=friend.username,
                avatar_url=friend.avatar_url,
                is_verified=friend.is_verified,
                friendship_date=friend.created_at  # This would need proper friendship date tracking
            ))
        
        return FriendListResponse(
            friends=friend_responses,
            total=len(friend_responses)
        )
    except Exception:
        raise http_400_bad_request("Failed to retrieve friends list")

@users_router.post("/me/friends", status_code=status.HTTP_201_CREATED)
async def add_friend(
    friend_request: FriendRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Add a friend"""
    try:
        user_service = UserService(db)
        success = user_service.add_friend(current_user.id, friend_request.friend_id)
        
        return {
            "message": "Friend added successfully",
            "success": success
        }
    except Exception as e:
        if "yourself" in str(e).lower():
            raise http_400_bad_request("Cannot add yourself as a friend")
        elif "not found" in str(e).lower():
            raise http_404_not_found("User not found")
        elif "already friends" in str(e).lower():
            raise http_409_conflict("Users are already friends")
        else:
            raise http_400_bad_request("Failed to add friend")

@users_router.delete("/me/friends/{friend_id}")
async def remove_friend(
    friend_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Remove a friend"""
    try:
        user_service = UserService(db)
        success = user_service.remove_friend(current_user.id, friend_id)
        
        return {
            "message": "Friend removed successfully",
            "success": success
        }
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("User not found")
        elif "not friends" in str(e).lower():
            raise http_400_bad_request("Users are not friends")
        else:
            raise http_400_bad_request("Failed to remove friend")

@users_router.get("/me/friends/mutual/{user_id}", response_model=List[UserSummary])
async def get_mutual_friends(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get mutual friends with another user"""
    try:
        user_service = UserService(db)
        mutual_friends = user_service.get_mutual_friends(current_user.id, user_id)
        
        return [UserSummary.model_validate(friend) for friend in mutual_friends]
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("User not found")
        else:
            raise http_400_bad_request("Failed to retrieve mutual friends")

@users_router.get("/me/friends/suggestions", response_model=List[UserSummary])
async def get_friend_suggestions(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get friend suggestions for current user"""
    try:
        user_service = UserService(db)
        suggestions = user_service.suggest_friends(current_user.id, limit)
        
        return [UserSummary.model_validate(user) for user in suggestions]
    except Exception:
        raise http_400_bad_request("Failed to retrieve friend suggestions")

@users_router.get("/", response_model=UserListResponse)
async def get_users(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of users (public profiles only)"""
    try:
        user_service = UserService(db)
        users = user_service.get_users(skip=offset, limit=limit, active_only=True)
        
        # Filter to only public profiles and convert to public response
        public_users = []
        for user in users:
            if user.is_public_profile:
                public_users.append(UserPublicResponse.model_validate(user))
        
        total = user_service.get_users_count(active_only=True)
        
        return UserListResponse(
            users=public_users,
            total=total,
            limit=limit,
            offset=offset
        )
    except Exception:
        raise http_400_bad_request("Failed to retrieve users")