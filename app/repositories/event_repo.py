from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, asc
from datetime import datetime, timedelta
from app.models.event_models import Event, EventInvitation, Task, Expense, Comment, Poll
from app.models.user_models import User
from app.models.shared_models import EventStatus, EventType, RSVPStatus, TaskStatus
from app.schemas.pagination import PaginationParams, SortParams

class EventRepository:
    """Repository for event data access operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(
        self, 
        event_id: int, 
        include_relations: bool = False
    ) -> Optional[Event]:
        """Get event by ID with optional relation loading"""
        query = self.db.query(Event).filter(Event.id == event_id)
        
        if include_relations:
            query = query.options(
                joinedload(Event.creator),
                joinedload(Event.collaborators),
                joinedload(Event.invitations),
                joinedload(Event.tasks),
                joinedload(Event.expenses)
            )
        
        return query.first()
    
    def get_multiple(
        self,
        event_ids: List[int],
        include_relations: bool = False
    ) -> List[Event]:
        """Get multiple events by IDs"""
        query = self.db.query(Event).filter(Event.id.in_(event_ids))
        
        if include_relations:
            query = query.options(
                joinedload(Event.creator),
                joinedload(Event.collaborators)
            )
        
        return query.all()
    
    def get_all(
        self,
        pagination: PaginationParams,
        sort: SortParams,
        filters: Optional[Dict[str, Any]] = None,
        include_relations: bool = False
    ) -> Tuple[List[Event], int]:
        """Get all events with pagination, sorting, and filtering"""
        query = self.db.query(Event).filter(Event.is_deleted == False)
        
        # Apply filters
        if filters:
            query = self._apply_filters(query, filters)
        
        # Get total count before pagination
        total = query.count()
        
        # Apply sorting
        query = self._apply_sorting(query, sort)
        
        # Apply pagination
        query = query.offset(pagination.offset).limit(pagination.limit)
        
        # Include relations if requested
        if include_relations:
            query = query.options(
                joinedload(Event.creator),
                joinedload(Event.collaborators)
            )
        
        events = query.all()
        
        return events, total
    
    def get_public_events(
        self,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Event], int]:
        """Get public events with pagination and filtering"""
        query = self.db.query(Event).filter(
            Event.is_public == True,
            Event.is_deleted == False
        )
        
        if filters:
            query = self._apply_filters(query, filters)
        
        total = query.count()
        
        query = query.order_by(desc(Event.start_datetime))
        query = query.offset(pagination.offset).limit(pagination.limit)
        
        events = query.all()
        
        return events, total
    
    def get_user_events(
        self,
        user_id: int,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None,
        role_filter: Optional[str] = None  # 'created', 'invited', 'collaborating'
    ) -> Tuple[List[Event], int]:
        """Get events for a specific user based on their role"""
        base_filter = Event.is_deleted == False
        
        if role_filter == 'created':
            query = self.db.query(Event).filter(
                Event.creator_id == user_id,
                base_filter
            )
        elif role_filter == 'invited':
            query = self.db.query(Event).join(EventInvitation).filter(
                EventInvitation.user_id == user_id,
                base_filter
            )
        elif role_filter == 'collaborating':
            query = self.db.query(Event).join(Event.collaborators).filter(
                Event.collaborators.any(User.id == user_id),
                base_filter
            )
        else:
            # All events user has access to
            query = self.db.query(Event).filter(
                or_(
                    Event.creator_id == user_id,
                    Event.collaborators.any(User.id == user_id),
                    Event.invitations.any(EventInvitation.user_id == user_id)
                ),
                base_filter
            )
        
        if filters:
            query = self._apply_filters(query, filters)
        
        total = query.count()
        
        query = query.order_by(desc(Event.start_datetime))
        query = query.offset(pagination.offset).limit(pagination.limit)
        
        events = query.all()
        
        return events, total
    
    def search(
        self,
        search_term: str,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None
    ) -> Tuple[List[Event], int]:
        """Search events by title, description, or venue"""
        search_filter = or_(
            Event.title.ilike(f"%{search_term}%"),
            Event.description.ilike(f"%{search_term}%"),
            Event.venue_name.ilike(f"%{search_term}%"),
            Event.venue_city.ilike(f"%{search_term}%")
        )
        
        query = self.db.query(Event).filter(
            search_filter,
            Event.is_deleted == False
        )
        
        # Apply access control
        if user_id:
            access_filter = or_(
                Event.is_public == True,
                Event.creator_id == user_id,
                Event.collaborators.any(User.id == user_id),
                Event.invitations.any(EventInvitation.user_id == user_id)
            )
            query = query.filter(access_filter)
        else:
            query = query.filter(Event.is_public == True)
        
        if filters:
            query = self._apply_filters(query, filters)
        
        total = query.count()
        
        query = query.order_by(desc(Event.start_datetime))
        query = query.offset(pagination.offset).limit(pagination.limit)
        
        events = query.all()
        
        return events, total
    
    def get_upcoming_events(
        self,
        user_id: Optional[int] = None,
        days_ahead: int = 30,
        limit: int = 10
    ) -> List[Event]:
        """Get upcoming events within specified days"""
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=days_ahead)
        
        query = self.db.query(Event).filter(
            Event.start_datetime >= start_date,
            Event.start_datetime <= end_date,
            Event.is_deleted == False
        )
        
        if user_id:
            access_filter = or_(
                Event.is_public == True,
                Event.creator_id == user_id,
                Event.collaborators.any(User.id == user_id),
                Event.invitations.any(
                    and_(
                        EventInvitation.user_id == user_id,
                        EventInvitation.rsvp_status == RSVPStatus.ACCEPTED
                    )
                )
            )
            query = query.filter(access_filter)
        else:
            query = query.filter(Event.is_public == True)
        
        return query.order_by(Event.start_datetime).limit(limit).all()
    
    def get_events_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[int] = None
    ) -> List[Event]:
        """Get events within a specific date range"""
        query = self.db.query(Event).filter(
            Event.start_datetime >= start_date,
            Event.start_datetime <= end_date,
            Event.is_deleted == False
        )
        
        if user_id:
            access_filter = or_(
                Event.is_public == True,
                Event.creator_id == user_id,
                Event.collaborators.any(User.id == user_id),
                Event.invitations.any(EventInvitation.user_id == user_id)
            )
            query = query.filter(access_filter)
        else:
            query = query.filter(Event.is_public == True)
        
        return query.order_by(Event.start_datetime).all()
    
    def create(self, event_data: Dict[str, Any]) -> Event:
        """Create a new event"""
        event = Event(**event_data)
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
    
    def update(self, event_id: int, update_data: Dict[str, Any]) -> Optional[Event]:
        """Update event by ID"""
        event = self.get_by_id(event_id)
        if not event:
            return None
        
        for field, value in update_data.items():
            if hasattr(event, field):
                setattr(event, field, value)
        
        self.db.commit()
        self.db.refresh(event)
        return event
    
    def delete(self, event_id: int) -> bool:
        """Soft delete event by ID"""
        event = self.get_by_id(event_id)
        if not event:
            return False
        
        event.soft_delete()
        self.db.commit()
        return True
    
    def get_event_statistics(self, event_id: int) -> Dict[str, Any]:
        """Get comprehensive statistics for an event"""
        event = self.get_by_id(event_id, include_relations=True)
        if not event:
            return {}
        
        # RSVP statistics
        rsvp_stats = self.db.query(
            EventInvitation.rsvp_status,
            func.count(EventInvitation.id)
        ).filter(
            EventInvitation.event_id == event_id
        ).group_by(EventInvitation.rsvp_status).all()
        
        rsvp_counts = {status.value: 0 for status in RSVPStatus}
        for status, count in rsvp_stats:
            rsvp_counts[status] = count
        
        # Task statistics
        task_stats = self.db.query(
            Task.status,
            func.count(Task.id)
        ).filter(
            Task.event_id == event_id
        ).group_by(Task.status).all()
        
        task_counts = {status.value: 0 for status in TaskStatus}
        for status, count in task_stats:
            task_counts[status] = count
        
        # Expense statistics
        expense_total = self.db.query(
            func.sum(Expense.amount)
        ).filter(
            Expense.event_id == event_id
        ).scalar() or 0
        
        # Comment count
        comment_count = self.db.query(
            func.count(Comment.id)
        ).filter(
            Comment.event_id == event_id
        ).scalar() or 0
        
        # Poll count
        poll_count = self.db.query(
            func.count(Poll.id)
        ).filter(
            Poll.event_id == event_id
        ).scalar() or 0
        
        return {
            "rsvp_counts": rsvp_counts,
            "task_counts": task_counts,
            "total_expenses": float(expense_total),
            "budget_remaining": float(event.total_budget - expense_total) if event.total_budget else None,
            "comment_count": comment_count,
            "poll_count": poll_count,
            "collaborator_count": len(event.collaborators),
            "invitation_count": len(event.invitations)
        }
    
    def get_events_by_location(
        self,
        city: Optional[str] = None,
        country: Optional[str] = None,
        radius_km: Optional[float] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        pagination: Optional[PaginationParams] = None
    ) -> Tuple[List[Event], int]:
        """Get events by location with optional radius search"""
        query = self.db.query(Event).filter(
            Event.is_public == True,
            Event.is_deleted == False
        )
        
        if city:
            query = query.filter(Event.venue_city.ilike(f"%{city}%"))
        
        if country:
            query = query.filter(Event.venue_country.ilike(f"%{country}%"))
        
        # TODO: Implement radius search using PostGIS or similar
        # For now, just filter by exact coordinates if provided
        if latitude and longitude:
            query = query.filter(
                Event.latitude == latitude,
                Event.longitude == longitude
            )
        
        total = query.count()
        
        if pagination:
            query = query.offset(pagination.offset).limit(pagination.limit)
        
        events = query.order_by(Event.start_datetime).all()
        
        return events, total
    
    def get_popular_events(
        self,
        limit: int = 10,
        days_back: int = 30
    ) -> List[Event]:
        """Get popular events based on invitation acceptance rate"""
        since_date = datetime.utcnow() - timedelta(days=days_back)
        
        # Subquery to count accepted invitations per event
        accepted_invitations = self.db.query(
            EventInvitation.event_id,
            func.count(EventInvitation.id).label('accepted_count')
        ).filter(
            EventInvitation.rsvp_status == RSVPStatus.ACCEPTED,
            EventInvitation.created_at >= since_date
        ).group_by(EventInvitation.event_id).subquery()
        
        # Join with events and order by acceptance count
        query = self.db.query(Event).join(
            accepted_invitations,
            Event.id == accepted_invitations.c.event_id
        ).filter(
            Event.is_public == True,
            Event.is_deleted == False
        ).order_by(
            desc(accepted_invitations.c.accepted_count)
        ).limit(limit)
        
        return query.all()
    
    def count_total(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count total events with optional filters"""
        query = self.db.query(Event).filter(Event.is_deleted == False)
        
        if filters:
            query = self._apply_filters(query, filters)
        
        return query.count()
    
    def _apply_filters(self, query, filters: Dict[str, Any]):
        """Apply filters to query"""
        for field, value in filters.items():
            if value is None:
                continue
                
            if field == 'event_type' and hasattr(Event, 'event_type'):
                if isinstance(value, list):
                    query = query.filter(Event.event_type.in_(value))
                else:
                    query = query.filter(Event.event_type == value)
            
            elif field == 'status' and hasattr(Event, 'status'):
                if isinstance(value, list):
                    query = query.filter(Event.status.in_(value))
                else:
                    query = query.filter(Event.status == value)
            
            elif field == 'start_date_after':
                query = query.filter(Event.start_datetime >= value)
            
            elif field == 'start_date_before':
                query = query.filter(Event.start_datetime <= value)
            
            elif field == 'city':
                query = query.filter(Event.venue_city.ilike(f"%{value}%"))
            
            elif field == 'country':
                query = query.filter(Event.venue_country.ilike(f"%{value}%"))
            
            elif field == 'is_public':
                query = query.filter(Event.is_public == value)
            
            elif field == 'creator_id':
                query = query.filter(Event.creator_id == value)
            
            elif hasattr(Event, field):
                if isinstance(value, list):
                    query = query.filter(getattr(Event, field).in_(value))
                else:
                    query = query.filter(getattr(Event, field) == value)
        
        return query
    
    def _apply_sorting(self, query, sort: SortParams):
        """Apply sorting to query"""
        if sort.sort_by and hasattr(Event, sort.sort_by):
            order_func = desc if sort.sort_order == "desc" else asc
            query = query.order_by(order_func(getattr(Event, sort.sort_by)))
        else:
            # Default sorting by start date
            query = query.order_by(desc(Event.start_datetime))
        
        return query