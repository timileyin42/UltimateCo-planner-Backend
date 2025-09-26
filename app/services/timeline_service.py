from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.repositories.timeline_repo import TimelineRepository
from app.repositories.event_repo import EventRepository
from app.models.timeline_models import TimelineItemType, TimelineStatus
from app.models.event_models import EventInvitation
from app.core.errors import NotFoundError, ValidationError, AuthorizationError
from app.schemas.pagination import PaginationParams
from app.services.ai_service import ai_service
import json

class TimelineService:
    """Service for managing event timelines and timeline items."""
    
    def __init__(self, db: Session):
        self.db = db
        self.timeline_repo = TimelineRepository(db)
        self.event_repo = EventRepository(db)
    
    # Timeline CRUD operations
    def create_timeline(
        self, 
        event_id: int, 
        user_id: int, 
        timeline_data: Dict[str, Any]
    ):
        """Create a new timeline for an event."""
        # Verify event access
        event = self._get_event_with_access(event_id, user_id)
        
        # Prepare timeline data
        processed_data = {
            'title': timeline_data['title'],
            'description': timeline_data.get('description'),
            'event_id': event_id,
            'creator_id': user_id,
            'template_id': timeline_data.get('template_id'),
            'start_time': timeline_data.get('start_time'),
            'end_time': timeline_data.get('end_time'),
            'is_published': timeline_data.get('is_published', False),
            'is_main_timeline': timeline_data.get('is_main_timeline', False)
        }
        
        return self.timeline_repo.create_timeline(processed_data)
    
    def get_timeline(self, timeline_id: int, user_id: int):
        """Get a timeline by ID."""
        timeline = self.timeline_repo.get_timeline_by_id(timeline_id, include_relations=True)
        
        if not timeline:
            raise NotFoundError("Timeline not found")
        
        # Check access permissions
        event = self._get_event_with_access(timeline.event_id, user_id)
        
        return timeline
    
    def get_event_timelines(
        self, 
        event_id: int, 
        user_id: int, 
        search_params: Dict[str, Any]
    ) -> Tuple[List, int]:
        """Get timelines for an event."""
        # Verify event access
        self._get_event_with_access(event_id, user_id)
        
        # Create pagination params
        page = search_params.get('page', 1)
        per_page = search_params.get('per_page', 20)
        pagination = PaginationParams(page=page, per_page=per_page)
        
        # Extract filters
        filters = {
            'creator_id': search_params.get('creator_id'),
            'template_id': search_params.get('template_id'),
            'is_published': search_params.get('is_published')
        }
        
        return self.timeline_repo.get_event_timelines(event_id, pagination, filters)
    
    def update_timeline(
        self, 
        timeline_id: int, 
        user_id: int, 
        update_data: Dict[str, Any]
    ):
        """Update a timeline."""
        timeline = self.timeline_repo.get_timeline_by_id(timeline_id)
        
        if not timeline:
            raise NotFoundError("Timeline not found")
        
        # Check permissions
        event = self._get_event_with_access(timeline.event_id, user_id)
        if not self._can_edit_timeline(timeline, event, user_id):
            raise AuthorizationError("You don't have permission to edit this timeline")
        
        return self.timeline_repo.update_timeline(timeline_id, update_data)
    
    def delete_timeline(self, timeline_id: int, user_id: int) -> bool:
        """Delete a timeline."""
        timeline = self.timeline_repo.get_timeline_by_id(timeline_id)
        
        if not timeline:
            raise NotFoundError("Timeline not found")
        
        # Check permissions
        event = self._get_event_with_access(timeline.event_id, user_id)
        if not self._can_edit_timeline(timeline, event, user_id):
            raise AuthorizationError("You don't have permission to delete this timeline")
        
        return self.timeline_repo.delete_timeline(timeline_id)
    
    # Timeline Item operations
    def add_timeline_item(
        self, 
        timeline_id: int, 
        user_id: int, 
        item_data: Dict[str, Any]
    ):
        """Add an item to a timeline."""
        timeline = self.timeline_repo.get_timeline_by_id(timeline_id)
        
        if not timeline:
            raise NotFoundError("Timeline not found")
        
        # Check permissions
        event = self._get_event_with_access(timeline.event_id, user_id)
        if not self._can_edit_timeline(timeline, event, user_id):
            raise AuthorizationError("You don't have permission to edit this timeline")
        
        # Calculate end time if not provided
        start_time = item_data['start_time']
        duration_minutes = item_data.get('duration_minutes', 60)
        end_time = item_data.get('end_time')
        
        if not end_time:
            end_time = self._calculate_item_end_time(start_time, duration_minutes)
        
        # Prepare item data
        processed_data = {
            'timeline_id': timeline_id,
            'title': item_data['title'],
            'description': item_data.get('description'),
            'item_type': TimelineItemType(item_data.get('item_type', 'activity')),
            'start_time': start_time,
            'end_time': end_time,
            'duration_minutes': duration_minutes,
            'assignee_id': item_data.get('assignee_id'),
            'location': item_data.get('location'),
            'notes': item_data.get('notes'),
            'order_index': item_data.get('order_index', 0),
            'status': TimelineStatus.PENDING
        }
        
        return self.timeline_repo.create_timeline_item(processed_data)
    
    def update_timeline_item(
        self, 
        item_id: int, 
        user_id: int, 
        update_data: Dict[str, Any]
    ):
        """Update a timeline item."""
        item = self.timeline_repo.get_timeline_item_by_id(item_id)
        
        if not item:
            raise NotFoundError("Timeline item not found")
        
        # Check permissions
        timeline = self.timeline_repo.get_timeline_by_id(item.timeline_id)
        event = self._get_event_with_access(timeline.event_id, user_id)
        
        if not self._can_edit_timeline(timeline, event, user_id):
            raise AuthorizationError("You don't have permission to edit this timeline item")
        
        # Recalculate end time if start time or duration changed
        if 'start_time' in update_data or 'duration_minutes' in update_data:
            start_time = update_data.get('start_time', item.start_time)
            duration_minutes = update_data.get('duration_minutes', item.duration_minutes)
            
            if 'end_time' not in update_data:
                update_data['end_time'] = self._calculate_item_end_time(start_time, duration_minutes)
        
        return self.timeline_repo.update_timeline_item(item_id, update_data)
    
    def update_item_status(
        self, 
        item_id: int, 
        user_id: int, 
        status_data: Dict[str, Any]
    ):
        """Update timeline item status."""
        item = self.timeline_repo.get_timeline_item_by_id(item_id)
        
        if not item:
            raise NotFoundError("Timeline item not found")
        
        # Check permissions (assignee or timeline editor can update status)
        timeline = self.timeline_repo.get_timeline_by_id(item.timeline_id)
        event = self._get_event_with_access(timeline.event_id, user_id)
        
        can_update = (
            item.assignee_id == user_id or 
            self._can_edit_timeline(timeline, event, user_id)
        )
        
        if not can_update:
            raise AuthorizationError("You don't have permission to update this item's status")
        
        # Prepare status update data
        update_data = {
            'status': TimelineStatus(status_data['status'])
        }
        
        # Add timestamps based on status
        if status_data['status'] == 'in_progress':
            update_data['actual_start_time'] = status_data.get('actual_start_time', datetime.utcnow())
        elif status_data['status'] == 'completed':
            update_data['actual_end_time'] = status_data.get('actual_end_time', datetime.utcnow())
            if not item.actual_start_time:
                update_data['actual_start_time'] = item.start_time
        
        return self.timeline_repo.update_timeline_item(item_id, update_data)
    
    def delete_timeline_item(self, item_id: int, user_id: int) -> bool:
        """Delete a timeline item."""
        item = self.timeline_repo.get_timeline_item_by_id(item_id)
        
        if not item:
            raise NotFoundError("Timeline item not found")
        
        # Check permissions
        timeline = self.timeline_repo.get_timeline_by_id(item.timeline_id)
        event = self._get_event_with_access(timeline.event_id, user_id)
        
        if not self._can_edit_timeline(timeline, event, user_id):
            raise AuthorizationError("You don't have permission to delete this timeline item")
        
        return self.timeline_repo.delete_timeline_item(item_id)
    
    def reorder_timeline_items(
        self, 
        timeline_id: int, 
        user_id: int, 
        item_orders: List[Dict[str, Any]]
    ) -> bool:
        """Reorder timeline items."""
        timeline = self.timeline_repo.get_timeline_by_id(timeline_id)
        
        if not timeline:
            raise NotFoundError("Timeline not found")
        
        # Check permissions
        event = self._get_event_with_access(timeline.event_id, user_id)
        if not self._can_edit_timeline(timeline, event, user_id):
            raise AuthorizationError("You don't have permission to reorder timeline items")
        
        return self.timeline_repo.reorder_timeline_items(timeline_id, item_orders)
    
    # AI Timeline Generation
    def generate_ai_timeline(
        self, 
        event_id: int, 
        user_id: int, 
        ai_request: Dict[str, Any]
    ):
        """Generate a timeline using AI."""
        # Verify event access
        event = self._get_event_with_access(event_id, user_id)
        
        # Generate timeline items using AI
        ai_items = ai_service.generate_event_timeline(
            event_type=ai_request.get('event_type', 'general'),
            duration_hours=ai_request.get('duration_hours', 4),
            guest_count=ai_request.get('guest_count', 20),
            preferences=ai_request.get('preferences', [])
        )
        
        # Create timeline
        timeline_data = {
            'title': f"AI Generated Timeline - {event.title}",
            'description': f"Automatically generated timeline for {ai_request.get('event_type', 'event')}",
            'event_id': event_id,
            'creator_id': user_id,
            'start_time': event.start_datetime,
            'end_time': event.end_datetime,
            'is_published': False
        }
        
        timeline = self.timeline_repo.create_timeline(timeline_data)
        
        # Create timeline items from AI suggestions
        for i, ai_item in enumerate(ai_items):
            start_time = event.start_datetime + timedelta(minutes=ai_item.get('start_time_offset_minutes', 0))
            duration_minutes = ai_item.get('duration_minutes', 60)
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            item_data = {
                'timeline_id': timeline.id,
                'title': ai_item['title'],
                'description': ai_item.get('description'),
                'item_type': TimelineItemType(ai_item.get('item_type', 'activity')),
                'start_time': start_time,
                'end_time': end_time,
                'duration_minutes': duration_minutes,
                'order_index': i,
                'status': TimelineStatus.PENDING
            }
            
            self.timeline_repo.create_timeline_item(item_data)
        
        return timeline
    
    # Template operations
    def create_template(
        self, 
        user_id: int, 
        template_data: Dict[str, Any]
    ):
        """Create a timeline template."""
        processed_data = {
            'name': template_data['name'],
            'description': template_data.get('description'),
            'event_type': template_data.get('event_type'),
            'duration_hours': template_data.get('duration_hours'),
            'template_data': json.dumps(template_data.get('template_data', {})),
            'creator_id': user_id,
            'is_public': template_data.get('is_public', False),
            'category': template_data.get('category')
        }
        
        return self.timeline_repo.create_template(processed_data)
    
    def apply_template(
        self, 
        event_id: int, 
        user_id: int, 
        template_id: int
    ):
        """Apply a template to create a timeline."""
        # Verify event access
        event = self._get_event_with_access(event_id, user_id)
        
        # Get template
        template = self.timeline_repo.get_template_by_id(template_id)
        
        if not template:
            raise NotFoundError("Template not found")
        
        # Create timeline from template
        timeline_data = {
            'title': f"{template.name} - {event.title}",
            'description': f"Timeline created from template: {template.name}",
            'event_id': event_id,
            'creator_id': user_id,
            'template_id': template_id,
            'start_time': event.start_datetime,
            'end_time': event.end_datetime,
            'is_published': False
        }
        
        timeline = self.timeline_repo.create_timeline(timeline_data)
        
        # Create items from template
        template_items = json.loads(template.template_data).get('items', [])
        
        for i, template_item in enumerate(template_items):
            start_offset = template_item.get('start_time_offset_minutes', 0)
            start_time = event.start_datetime + timedelta(minutes=start_offset)
            duration_minutes = template_item.get('duration_minutes', 60)
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            item_data = {
                'timeline_id': timeline.id,
                'title': template_item['title'],
                'description': template_item.get('description'),
                'item_type': TimelineItemType(template_item.get('item_type', 'activity')),
                'start_time': start_time,
                'end_time': end_time,
                'duration_minutes': duration_minutes,
                'order_index': i,
                'status': TimelineStatus.PENDING
            }
            
            self.timeline_repo.create_timeline_item(item_data)
        
        # Increment template usage
        self.timeline_repo.increment_template_usage(template_id)
        
        return timeline
    
    def get_templates(
        self, 
        search_params: Dict[str, Any]
    ) -> Tuple[List, int]:
        """Get timeline templates."""
        # Create pagination params
        page = search_params.get('page', 1)
        per_page = search_params.get('per_page', 20)
        pagination = PaginationParams(page=page, per_page=per_page)
        
        # Extract filters
        filters = {
            'event_type': search_params.get('event_type'),
            'creator_id': search_params.get('creator_id'),
            'is_public': search_params.get('is_public'),
            'category': search_params.get('category')
        }
        
        return self.timeline_repo.get_templates(pagination, filters)
    
    # Dependencies
    def add_item_dependency(
        self, 
        timeline_id: int, 
        user_id: int, 
        dependency_data: Dict[str, Any]
    ):
        """Add a dependency between timeline items."""
        timeline = self.timeline_repo.get_timeline_by_id(timeline_id)
        
        if not timeline:
            raise NotFoundError("Timeline not found")
        
        # Check permissions
        event = self._get_event_with_access(timeline.event_id, user_id)
        if not self._can_edit_timeline(timeline, event, user_id):
            raise AuthorizationError("You don't have permission to edit timeline dependencies")
        
        # Validate that both items exist and belong to the timeline
        items = self.timeline_repo.get_timeline_items(timeline_id)
        item_ids = [item.id for item in items]
        
        if (dependency_data['dependent_item_id'] not in item_ids or 
            dependency_data['prerequisite_item_id'] not in item_ids):
            raise ValidationError("Both items must belong to the same timeline")
        
        return self.timeline_repo.create_timeline_dependency(dependency_data)
    
    # Statistics and analytics
    def get_timeline_statistics(self, timeline_id: int, user_id: int) -> Dict[str, Any]:
        """Get statistics for a timeline."""
        timeline = self.timeline_repo.get_timeline_by_id(timeline_id)
        
        if not timeline:
            raise NotFoundError("Timeline not found")
        
        # Check access permissions
        self._get_event_with_access(timeline.event_id, user_id)
        
        return self.timeline_repo.get_timeline_statistics(timeline_id)
    
    def get_timeline_progress(self, timeline_id: int, user_id: int) -> Dict[str, Any]:
        """Get timeline progress information."""
        timeline = self.timeline_repo.get_timeline_by_id(timeline_id)
        
        if not timeline:
            raise NotFoundError("Timeline not found")
        
        # Check access permissions
        self._get_event_with_access(timeline.event_id, user_id)
        
        return self.timeline_repo.get_timeline_progress(timeline_id)
    
    def get_overdue_items(self, timeline_id: Optional[int] = None, user_id: Optional[int] = None):
        """Get overdue timeline items."""
        if timeline_id:
            # Check permissions for specific timeline
            timeline = self.timeline_repo.get_timeline_by_id(timeline_id)
            if timeline and user_id:
                self._get_event_with_access(timeline.event_id, user_id)
        
        return self.timeline_repo.get_overdue_items(timeline_id)
    
    def get_upcoming_items(
        self, 
        timeline_id: Optional[int] = None, 
        user_id: Optional[int] = None,
        hours_ahead: int = 24
    ):
        """Get upcoming timeline items."""
        if timeline_id:
            # Check permissions for specific timeline
            timeline = self.timeline_repo.get_timeline_by_id(timeline_id)
            if timeline and user_id:
                self._get_event_with_access(timeline.event_id, user_id)
        
        return self.timeline_repo.get_upcoming_items(timeline_id, hours_ahead)
    
    # Search operations
    def search_timelines(
        self, 
        search_params: Dict[str, Any]
    ) -> Tuple[List, int]:
        """Search timelines."""
        # Create pagination params
        page = search_params.get('page', 1)
        per_page = search_params.get('per_page', 20)
        pagination = PaginationParams(page=page, per_page=per_page)
        
        return self.timeline_repo.search_timelines(search_params, pagination)
    
    # Helper methods
    def _get_event_with_access(self, event_id: int, user_id: int):
        """Get event and verify user has access."""
        event = self.event_repo.get_by_id(event_id, include_relations=True)
        
        if not event:
            raise NotFoundError("Event not found")
        
        # Check access (creator, collaborator, or invited)
        if event.creator_id != user_id:
            # Check if user is collaborator or invited
            invitation = self.db.query(EventInvitation).filter(
                EventInvitation.event_id == event_id,
                EventInvitation.user_id == user_id
            ).first()
            
            if not invitation:
                raise AuthorizationError("You don't have access to this event")
        
        return event
    
    def _can_edit_timeline(self, timeline, event, user_id: int) -> bool:
        """Check if user can edit a timeline."""
        # Timeline creator can edit
        if timeline.creator_id == user_id:
            return True
        
        # Event creator can edit
        if event.creator_id == user_id:
            return True
        
        return False
    
    def _calculate_item_end_time(self, start_time: datetime, duration_minutes: int) -> datetime:
        """Calculate end time for a timeline item."""
        return start_time + timedelta(minutes=duration_minutes)
    
    def _validate_timeline_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate timeline items for conflicts."""
        conflicts = []
        
        for i, item1 in enumerate(items):
            for j, item2 in enumerate(items[i+1:], i+1):
                # Check for time overlap
                if (item1['start_time'] < item2['end_time'] and 
                    item2['start_time'] < item1['end_time']):
                    conflicts.append({
                        'item1_index': i,
                        'item2_index': j,
                        'conflict_type': 'time_overlap',
                        'message': f"Items {i+1} and {j+1} have overlapping times"
                    })
        
        return conflicts