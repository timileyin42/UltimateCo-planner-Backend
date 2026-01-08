from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, asc
from app.models.user_models import User, UserProfile, UserSession
from app.schemas.pagination import PaginationParams, SortParams
from datetime import datetime, timedelta

class UserRepository:
    """Repository for user data access operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, user_id: int, include_profile: bool = False) -> Optional[User]:
        """Get user by ID with optional profile loading"""
        query = self.db.query(User).filter(User.id == user_id)
        
        if include_profile:
            query = query.options(joinedload(User.profile))
        
        return query.first()
    
    def get_by_email(self, email: str, include_profile: bool = False) -> Optional[User]:
        """Get user by email with optional profile loading"""
        query = self.db.query(User).filter(User.email == email)
        
        if include_profile:
            query = query.options(joinedload(User.profile))
        
        return query.first()
    
    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        return self.db.query(User).filter(User.username == username).first()
    
    def get_multiple(
        self,
        user_ids: List[int],
        include_profile: bool = False
    ) -> List[User]:
        """Get multiple users by IDs"""
        query = self.db.query(User).filter(User.id.in_(user_ids))
        
        if include_profile:
            query = query.options(joinedload(User.profile))
        
        return query.all()
    
    def get_all(
        self,
        pagination: PaginationParams,
        sort: SortParams,
        filters: Optional[Dict[str, Any]] = None,
        include_profile: bool = False
    ) -> tuple[List[User], int]:
        """Get all users with pagination, sorting, and filtering"""
        query = self.db.query(User)
        
        # Apply filters
        if filters:
            query = self._apply_filters(query, filters)
        
        # Get total count before pagination
        total = query.count()
        
        # Apply sorting
        query = self._apply_sorting(query, sort)
        
        # Apply pagination
        query = query.offset(pagination.offset).limit(pagination.limit)
        
        # Include profile if requested
        if include_profile:
            query = query.options(joinedload(User.profile))
        
        users = query.all()
        
        return users, total
    
    def search(
        self,
        search_term: str,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> tuple[List[User], int]:
        """Search users by name, email, or username"""
        search_filter = or_(
            User.full_name.ilike(f"%{search_term}%"),
            User.email.ilike(f"%{search_term}%"),
            User.username.ilike(f"%{search_term}%")
        )
        
        query = self.db.query(User).filter(search_filter)
        
        # Apply additional filters
        if filters:
            query = self._apply_filters(query, filters)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        query = query.offset(pagination.offset).limit(pagination.limit)
        
        users = query.all()
        
        return users, total
    
    def create(self, user_data: Dict[str, Any]) -> User:
        """Create a new user"""
        user = User(**user_data)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def update(self, user_id: int, update_data: Dict[str, Any]) -> Optional[User]:
        """Update user by ID"""
        user = self.get_by_id(user_id)
        if not user:
            return None
        
        for field, value in update_data.items():
            if hasattr(user, field):
                setattr(user, field, value)
        
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def delete(self, user_id: int) -> bool:
        """Soft delete user by ID"""
        user = self.get_by_id(user_id)
        if not user:
            return False
        
        user.soft_delete()
        self.db.commit()
        return True
    
    def exists_by_email(self, email: str, exclude_user_id: Optional[int] = None) -> bool:
        """Check if user exists by email"""
        query = self.db.query(User).filter(User.email == email)
        
        if exclude_user_id:
            query = query.filter(User.id != exclude_user_id)
        
        return query.first() is not None
    
    def exists_by_username(self, username: str, exclude_user_id: Optional[int] = None) -> bool:
        """Check if user exists by username"""
        query = self.db.query(User).filter(User.username == username)
        
        if exclude_user_id:
            query = query.filter(User.id != exclude_user_id)
        
        return query.first() is not None
    
    def get_friends(
        self,
        user_id: int,
        pagination: PaginationParams,
        search_term: Optional[str] = None
    ) -> tuple[List[User], int]:
        """Get user's friends with pagination and optional search"""
        user = self.get_by_id(user_id)
        if not user:
            return [], 0
        
        # Start with friends query
        query = self.db.query(User).join(
            User.friends
        ).filter(
            User.friends.any(User.id == user_id)
        )
        
        # Apply search filter if provided
        if search_term:
            search_filter = or_(
                User.full_name.ilike(f"%{search_term}%"),
                User.username.ilike(f"%{search_term}%")
            )
            query = query.filter(search_filter)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        query = query.offset(pagination.offset).limit(pagination.limit)
        
        friends = query.all()
        
        return friends, total
    
    def get_mutual_friends(self, user_id: int, other_user_id: int) -> List[User]:
        """Get mutual friends between two users"""
        # Get friends of both users
        user_friends = self.db.query(User).join(
            User.friends
        ).filter(
            User.friends.any(User.id == user_id)
        ).subquery()
        
        other_user_friends = self.db.query(User).join(
            User.friends
        ).filter(
            User.friends.any(User.id == other_user_id)
        ).subquery()
        
        # Find intersection
        mutual_friends = self.db.query(User).filter(
            and_(
                User.id.in_(self.db.query(user_friends.c.id)),
                User.id.in_(self.db.query(other_user_friends.c.id))
            )
        ).all()
        
        return mutual_friends
    
    def get_friend_suggestions(
        self,
        user_id: int,
        limit: int = 10,
        name_query: Optional[str] = None,
        city: Optional[str] = None,
    ) -> List[User]:
        """Get friend suggestions based on mutual connections, with optional filters."""
        user = self.get_by_id(user_id)
        if not user:
            return []
        
        # If the user has no friends yet, optionally fall back to filter-based search
        if not user.friends:
            if name_query or city:
                exclude_ids = {user_id}
                for f in user.friends:
                    exclude_ids.add(f.id)
                q = self.db.query(User).filter(
                    User.is_active == True,
                    ~User.id.in_(exclude_ids)
                )
                if name_query:
                    like = f"%{name_query}%"
                    from sqlalchemy import or_
                    q = q.filter(or_(User.full_name.ilike(like), User.username.ilike(like)))
                if city:
                    q = q.filter(User.city.ilike(f"%{city}%"))
                return q.limit(limit).all()
            return []

        # Get current friend IDs
        current_friend_ids = [friend.id for friend in user.friends]
        current_friend_ids.append(user_id)  # Exclude self

        friend_ids = [friend.id for friend in user.friends]

        # Compose OR conditions on relationship to avoid IN() problems
        from sqlalchemy import or_
        fof_condition = or_(*[User.friends.any(User.id == fid) for fid in friend_ids])

        # Find users who are friends with current user's friends
        # but not already friends with the user
        q = (
            self.db.query(User)
            .filter(
                fof_condition,
                ~User.id.in_(current_friend_ids),
                User.is_active == True,
            )
            .distinct()
        )

        # Optional filters
        if name_query:
            like = f"%{name_query}%"
            from sqlalchemy import or_
            q = q.filter(or_(User.full_name.ilike(like), User.username.ilike(like)))
        if city:
            q = q.filter(User.city.ilike(f"%{city}%"))

        suggestions = q.limit(limit).all()

        # Fallback to global filtered search if mutual suggestions empty but filters provided
        if (name_query or city) and not suggestions:
            q2 = self.db.query(User).filter(
                User.is_active == True,
                ~User.id.in_(current_friend_ids)
            )
            if name_query:
                like = f"%{name_query}%"
                from sqlalchemy import or_
                q2 = q2.filter(or_(User.full_name.ilike(like), User.username.ilike(like)))
            if city:
                q2 = q2.filter(User.city.ilike(f"%{city}%"))
            suggestions = q2.limit(limit).all()
        
        return suggestions
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive user statistics"""
        user = self.get_by_id(user_id)
        if not user:
            return {}
        
        # Count events created
        events_created = len(user.created_events)
        
        # Count events attended (accepted invitations)
        events_attended = len([
            inv for inv in user.event_invitations 
            if inv.rsvp_status == "accepted"
        ])
        
        # Count tasks completed
        tasks_completed = len([
            task for task in user.assigned_tasks 
            if task.status == "completed"
        ])
        
        # Count friends
        friends_count = len(user.friends)
        
        # Count media uploaded
        media_uploaded = len(user.uploaded_media)
        
        return {
            "events_created": events_created,
            "events_attended": events_attended,
            "tasks_completed": tasks_completed,
            "friends_count": friends_count,
            "media_uploaded": media_uploaded,
            "member_since": user.created_at,
            "last_active": user.updated_at
        }
    
    def get_recent_activity(
        self,
        user_id: int,
        days: int = 30,
        limit: int = 50
    ) -> Dict[str, List]:
        """Get user's recent activity"""
        since_date = datetime.utcnow() - timedelta(days=days)
        
        user = self.get_by_id(user_id)
        if not user:
            return {}
        
        # Recent events created
        recent_events = [
            event for event in user.created_events
            if event.created_at >= since_date
        ][:limit]
        
        # Recent tasks completed
        recent_tasks = [
            task for task in user.assigned_tasks
            if task.completed_at and task.completed_at >= since_date
        ][:limit]
        
        # Recent media uploaded
        recent_media = [
            media for media in user.uploaded_media
            if media.created_at >= since_date
        ][:limit]
        
        return {
            "recent_events": recent_events,
            "recent_tasks": recent_tasks,
            "recent_media": recent_media
        }
    
    def get_active_sessions(self, user_id: int) -> List[UserSession]:
        """Get user's active sessions"""
        return self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).all()
    
    def count_total(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count total users with optional filters"""
        query = self.db.query(User)
        
        if filters:
            query = self._apply_filters(query, filters)
        
        return query.count()
    
    def _apply_filters(self, query, filters: Dict[str, Any]):
        """Apply filters to query"""
        for field, value in filters.items():
            if hasattr(User, field) and value is not None:
                if isinstance(value, list):
                    query = query.filter(getattr(User, field).in_(value))
                elif isinstance(value, str) and field.endswith('_like'):
                    # Handle LIKE queries
                    actual_field = field.replace('_like', '')
                    if hasattr(User, actual_field):
                        query = query.filter(
                            getattr(User, actual_field).ilike(f"%{value}%")
                        )
                else:
                    query = query.filter(getattr(User, field) == value)
        
        return query
    
    def _apply_sorting(self, query, sort: SortParams):
        """Apply sorting to query"""
        if sort.sort_by and hasattr(User, sort.sort_by):
            order_func = desc if sort.sort_order == "desc" else asc
            query = query.order_by(order_func(getattr(User, sort.sort_by)))
        else:
            # Default sorting
            query = query.order_by(desc(User.created_at))
        
        return query
    
    # UserProfile operations
    def get_user_profile(self, user_id: int) -> Optional[UserProfile]:
        """Get user profile by user ID"""
        return self.db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    
    def create_user_profile(self, profile_data: Dict[str, Any]) -> UserProfile:
        """Create a new user profile"""
        profile = UserProfile(**profile_data)
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile
    
    def update_user_profile(self, user_id: int, update_data: Dict[str, Any]) -> Optional[UserProfile]:
        """Update user profile"""
        profile = self.get_user_profile(user_id)
        if not profile:
            return None
        
        for field, value in update_data.items():
            if hasattr(profile, field):
                setattr(profile, field, value)
        
        self.db.commit()
        self.db.refresh(profile)
        return profile