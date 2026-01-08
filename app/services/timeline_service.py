from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, time
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
        payload = self._to_payload(timeline_data)
        start_time = self._normalize_time_value(payload.get('start_time'))
        end_time = self._normalize_time_value(payload.get('end_time'))
        processed_data = {
            'title': payload['title'],
            'description': payload.get('description'),
            'event_id': event_id,
            'creator_id': user_id,
            'start_time': start_time,
            'end_time': end_time,
            'default_buffer_minutes': payload.get('default_buffer_minutes', 15),
            'setup_buffer_minutes': payload.get('setup_buffer_minutes', 30),
            'cleanup_buffer_minutes': payload.get('cleanup_buffer_minutes', 30),
            'is_active': payload.get('is_active', True)
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
        
        search_payload = self._to_payload(search_params)
        # Create pagination params
        page = search_payload.get('page', 1)
        per_page = search_payload.get('per_page', 20)
        pagination = PaginationParams(page=page, size=per_page)
        
        # Extract filters
        filters = {
            'creator_id': search_payload.get('creator_id'),
            'template_id': search_payload.get('template_id'),
            'is_published': search_payload.get('is_published')
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

        update_payload = self._to_payload(update_data)

        if "start_time" in update_payload:
            update_payload["start_time"] = self._normalize_time_value(update_payload["start_time"])
        if "end_time" in update_payload:
            update_payload["end_time"] = self._normalize_time_value(update_payload["end_time"])

        if not update_payload:
            return timeline

        return self.timeline_repo.update_timeline(timeline_id, update_payload)
    
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
        
        item_payload = self._to_payload(item_data)
        start_time = self._normalize_time_value(item_payload.get('start_time'))
        if not start_time:
            raise ValidationError("Timeline items require a start_time")
        duration_minutes = item_payload.get('duration_minutes', 60)
        # Calculate end time if not provided
        end_time = self._normalize_time_value(item_payload.get('end_time'))
        if not end_time:
            end_time = self._calculate_item_end_time(start_time, duration_minutes)
        item_type_value = item_payload.get('item_type', TimelineItemType.ACTIVITY)
        item_type = item_type_value if isinstance(item_type_value, TimelineItemType) else TimelineItemType(item_type_value)
        requirements_value = item_payload.get('requirements')
        if isinstance(requirements_value, list):
            requirements_value = json.dumps(requirements_value)
        
        # Prepare item data
        assigned_to_id = item_payload.get('assigned_to_id', item_payload.get('assignee_id'))

        processed_data = {
            'timeline_id': timeline_id,
            'title': item_payload['title'],
            'description': item_payload.get('description'),
            'item_type': item_type,
            'start_time': start_time,
            'end_time': end_time,
            'duration_minutes': duration_minutes,
            'buffer_minutes': item_payload.get('buffer_minutes', 0),
            'assigned_to_id': assigned_to_id,
            'location': item_payload.get('location'),
            'notes': item_payload.get('notes'),
            'order_index': item_payload.get('order_index', 0),
            'status': TimelineStatus.PENDING,
            'is_critical': item_payload.get('is_critical', False),
            'is_flexible': item_payload.get('is_flexible', True),
            'requirements': requirements_value,
            'task_id': item_payload.get('task_id')
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
        
        update_payload = self._to_payload(update_data)
        if 'item_type' in update_payload and not isinstance(update_payload['item_type'], TimelineItemType):
            update_payload['item_type'] = TimelineItemType(update_payload['item_type'])
        if 'status' in update_payload and not isinstance(update_payload['status'], TimelineStatus):
            update_payload['status'] = TimelineStatus(update_payload['status'])
        if 'assignee_id' in update_payload and 'assigned_to_id' not in update_payload:
            update_payload['assigned_to_id'] = update_payload.pop('assignee_id')
        if 'start_time' in update_payload:
            update_payload['start_time'] = self._normalize_time_value(update_payload['start_time'])
        if 'end_time' in update_payload:
            update_payload['end_time'] = self._normalize_time_value(update_payload['end_time'])
        if 'actual_start_time' in update_payload:
            update_payload['actual_start_time'] = self._normalize_time_value(update_payload['actual_start_time'])
        if 'actual_end_time' in update_payload:
            update_payload['actual_end_time'] = self._normalize_time_value(update_payload['actual_end_time'])
        if 'requirements' in update_payload and isinstance(update_payload['requirements'], list):
            update_payload['requirements'] = json.dumps(update_payload['requirements'])
        
        # Recalculate end time if start time or duration changed
        if 'start_time' in update_payload or 'duration_minutes' in update_payload:
            start_time_value = update_payload.get('start_time', item.start_time)
            if isinstance(start_time_value, datetime):
                start_time_value = self._normalize_time_value(start_time_value)
            duration_minutes = update_payload.get('duration_minutes', item.duration_minutes)
            update_payload['start_time'] = start_time_value
            update_payload['duration_minutes'] = duration_minutes
            update_payload['end_time'] = self._calculate_item_end_time(start_time_value, duration_minutes)
        
        return self.timeline_repo.update_timeline_item(item_id, update_payload)
    
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
            item.assigned_to_id == user_id or 
            self._can_edit_timeline(timeline, event, user_id)
        )
        
        if not can_update:
            raise AuthorizationError("You don't have permission to update this item's status")
        
        status_payload = self._to_payload(status_data)
        status_value = status_payload.get('status')
        status_enum = status_value if isinstance(status_value, TimelineStatus) else TimelineStatus(status_value)
        # Prepare status update data
        update_data = {
            'status': status_enum
        }
        
        # Add timestamps based on status
        if status_enum == TimelineStatus.IN_PROGRESS:
            actual_start = self._normalize_time_value(status_payload.get('actual_start_time'))
            update_data['actual_start_time'] = actual_start or datetime.utcnow().time()
        elif status_enum == TimelineStatus.COMPLETED:
            actual_end = self._normalize_time_value(status_payload.get('actual_end_time'))
            update_data['actual_end_time'] = actual_end or datetime.utcnow().time()
            if status_payload.get('actual_start_time'):
                update_data.setdefault('actual_start_time', self._normalize_time_value(status_payload['actual_start_time']))
            elif item.actual_start_time:
                update_data.setdefault('actual_start_time', item.actual_start_time)
            else:
                update_data.setdefault('actual_start_time', item.start_time)
        
        return self.timeline_repo.update_timeline_item(item_id, update_data)
    
    def delete_timeline_item(self, item_id: int, user_id: int) -> bool:
        """Delete a timeline item."""
        item = self.timeline_repo.get_timeline_item_by_id(item_id)
        
        if not item:
            raise NotFoundError("Timeline item not found")
        
        # Check permissions
        timeline = self.timeline_repo.get_timeline_by_id(item.timeline_id)
        if not timeline:
            raise NotFoundError("Timeline not found")
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
        request_payload = self._to_payload(ai_request)
        
        # Generate timeline items using AI
        ai_items = ai_service.generate_event_timeline(
            event_type=request_payload.get('event_type', 'general'),
            duration_hours=request_payload.get('duration_hours', 4),
            guest_count=request_payload.get('guest_count', 20),
            preferences=request_payload.get('preferences', [])
        )
        
        # Create timeline
        timeline_data = {
            'title': f"AI Generated Timeline - {event.title}",
            'description': f"Automatically generated timeline for {request_payload.get('event_type', 'event')}",
            'event_id': event_id,
            'creator_id': user_id,
            'start_time': self._normalize_time_value(event.start_datetime) if event.start_datetime else None,
            'end_time': self._normalize_time_value(event.end_datetime) if event.end_datetime else None,
            'auto_generated': True,
            'is_active': True
        }
        
        timeline = self.timeline_repo.create_timeline(timeline_data)
        
        # Create timeline items from AI suggestions
        for i, ai_item in enumerate(ai_items):
            start_time = event.start_datetime + timedelta(minutes=ai_item.get('start_time_offset_minutes', 0))
            duration_minutes = ai_item.get('duration_minutes', 60)
            end_time = start_time + timedelta(minutes=duration_minutes)
            start_time_value = self._normalize_time_value(start_time)
            end_time_value = self._normalize_time_value(end_time)
            
            item_data = {
                'timeline_id': timeline.id,
                'title': ai_item['title'],
                'description': ai_item.get('description'),
                'item_type': TimelineItemType(ai_item.get('item_type', 'activity')),
                'start_time': start_time_value,
                'end_time': end_time_value,
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
        payload = self._to_payload(template_data)
        processed_data = {
            'name': payload['name'],
            'description': payload.get('description'),
            'event_type': payload.get('event_type'),
            'duration_hours': payload.get('duration_hours'),
            'template_data': json.dumps(payload.get('template_data', {})),
            'creator_id': user_id,
            'is_public': payload.get('is_public', False),
            'category': payload.get('category')
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
            'start_time': self._normalize_time_value(event.start_datetime) if event.start_datetime else None,
            'end_time': self._normalize_time_value(event.end_datetime) if event.end_datetime else None,
            'is_active': True
        }
        
        timeline = self.timeline_repo.create_timeline(timeline_data)
        
        # Create items from template
        template_items = json.loads(template.template_data).get('items', [])
        
        for i, template_item in enumerate(template_items):
            start_offset = template_item.get('start_time_offset_minutes', 0)
            start_time = event.start_datetime + timedelta(minutes=start_offset)
            duration_minutes = template_item.get('duration_minutes', 60)
            end_time = start_time + timedelta(minutes=duration_minutes)
            start_time_value = self._normalize_time_value(start_time)
            end_time_value = self._normalize_time_value(end_time)
            item_type_value = template_item.get('item_type', 'activity')
            item_type = item_type_value if isinstance(item_type_value, TimelineItemType) else TimelineItemType(item_type_value)
            
            item_data = {
                'timeline_id': timeline.id,
                'title': template_item['title'],
                'description': template_item.get('description'),
                'item_type': item_type,
                'start_time': start_time_value,
                'end_time': end_time_value,
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
        search_payload = self._to_payload(search_params)
        # Create pagination params
        page = search_payload.get('page', 1)
        per_page = search_payload.get('per_page', 20)
        pagination = PaginationParams(page=page, size=per_page)
        
        # Extract filters
        filters = {
            'event_type': search_payload.get('event_type'),
            'creator_id': search_payload.get('creator_id'),
            'is_public': search_payload.get('is_public'),
            'category': search_payload.get('category')
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
        
        payload = self._to_payload(dependency_data)
        # Validate that both items exist and belong to the timeline
        items = self.timeline_repo.get_timeline_items(timeline_id)
        item_ids = [item.id for item in items]
        
        if (payload['dependent_item_id'] not in item_ids or 
            payload['prerequisite_item_id'] not in item_ids):
            raise ValidationError("Both items must belong to the same timeline")
        
        return self.timeline_repo.create_timeline_dependency(payload)
    
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
        search_payload = self._to_payload(search_params)
        # Create pagination params
        page = search_payload.get('page', 1)
        per_page = search_payload.get('per_page', 20)
        pagination = PaginationParams(page=page, size=per_page)
        
        return self.timeline_repo.search_timelines(search_payload, pagination)
    
    # Helper methods
    def _to_payload(self, data: Any) -> Dict[str, Any]:
        """Convert Pydantic models or other inputs into standard dicts."""
        if data is None:
            return {}
        if isinstance(data, dict):
            return data
        model_dump = getattr(data, "model_dump", None)
        if callable(model_dump):
            return model_dump(exclude_unset=True)
        raise TypeError(f"Unsupported payload type: {type(data)}")

    def _normalize_time_value(self, value: Any) -> Optional[time]:
        """Ensure time-like values are converted to datetime.time objects."""
        if value is None:
            return None
        if isinstance(value, time):
            return value
        if isinstance(value, datetime):
            return value.time()
        if isinstance(value, str):
            try:
                # Try parsing full datetime strings first
                return datetime.fromisoformat(value).time()
            except ValueError:
                try:
                    return time.fromisoformat(value)
                except ValueError as exc:
                    raise ValidationError("Invalid time format provided") from exc
        raise ValidationError("Unsupported time value provided")

    def _get_event_with_access(self, event_id: int, user_id: int):
        """Get event and verify user has access."""
        event = self.event_repo.get_by_id(event_id, include_relations=True)
        
        if not event:
            raise NotFoundError("Event not found")

        # Event creator always has access
        if event.creator_id == user_id:
            return event

        # Collaborators can access timelines as well
        if any(collaborator.id == user_id for collaborator in (event.collaborators or [])):
            return event

        # Fall back to invitation check for invited guests who accepted
        # Invitations are already loaded with include_relations=True
        if any(
            inv.user_id == user_id and not inv.is_deleted 
            for inv in (event.invitations or [])
        ):
            return event

        raise AuthorizationError("You don't have access to this event")
    
    def _can_edit_timeline(self, timeline, event, user_id: int) -> bool:
        """Check if user can edit a timeline."""
        # Timeline creator can edit
        if timeline.creator_id == user_id:
            return True
        
        # Event creator can edit
        if event.creator_id == user_id:
            return True
        
        return False
    
    def _calculate_item_end_time(self, start_time: time, duration_minutes: int) -> time:
        """Calculate end time for a timeline item."""
        base_datetime = datetime.combine(datetime.utcnow().date(), start_time)
        end_datetime = base_datetime + timedelta(minutes=duration_minutes)
        return end_datetime.time()
    
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