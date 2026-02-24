from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, asc
from datetime import datetime, timedelta
from app.models.timeline_models import (
    EventTimeline, TimelineItem, TimelineDependency, TimelineTemplate,
    TimelineNotification, TimelineUpdate, TimelineItemType, TimelineStatus
)
from app.models.user_models import User
from app.models.event_models import Event
from app.schemas.pagination import PaginationParams, SortParams

class TimelineRepository:
    """Repository for timeline data access operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # Timeline CRUD operations
    def get_timeline_by_id(
        self, 
        timeline_id: int, 
        include_relations: bool = False
    ) -> Optional[EventTimeline]:
        """Get timeline by ID with optional relation loading"""
        query = self.db.query(EventTimeline).filter(EventTimeline.id == timeline_id)
        
        if include_relations:
            query = query.options(
                joinedload(EventTimeline.creator),
                joinedload(EventTimeline.event),
                joinedload(EventTimeline.items).joinedload(TimelineItem.assigned_to),
                joinedload(EventTimeline.items).joinedload(TimelineItem.task)
            )
        
        return query.first()
    
    def get_event_timelines(
        self,
        event_id: int,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[EventTimeline], int]:
        """Get timelines for an event"""
        query = self.db.query(EventTimeline).options(
            joinedload(EventTimeline.creator)
        ).filter(
            EventTimeline.event_id == event_id,
            EventTimeline.is_active == True
        )
        
        if filters:
            if filters.get('creator_id'):
                query = query.filter(EventTimeline.creator_id == filters['creator_id'])
            
            if filters.get('template_id'):
                query = query.filter(EventTimeline.template_id == filters['template_id'])
            
            if filters.get('is_published') is not None:
                query = query.filter(EventTimeline.is_published == filters['is_published'])
        
        total = query.count()
        
        timelines = query.order_by(
            desc(EventTimeline.created_at)
        ).offset(pagination.offset).limit(pagination.limit).all()
        
        return timelines, total
    
    def get_user_timelines(
        self,
        user_id: int,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[EventTimeline], int]:
        """Get timelines created by a user"""
        query = self.db.query(EventTimeline).options(
            joinedload(EventTimeline.event)
        ).filter(
            EventTimeline.creator_id == user_id,
            EventTimeline.is_active == True
        )
        
        if filters:
            if filters.get('event_id'):
                query = query.filter(EventTimeline.event_id == filters['event_id'])
        
        total = query.count()
        
        timelines = query.order_by(
            desc(EventTimeline.created_at)
        ).offset(pagination.offset).limit(pagination.limit).all()
        
        return timelines, total
    
    def create_timeline(self, timeline_data: Dict[str, Any]) -> EventTimeline:
        """Create a new timeline"""
        timeline = EventTimeline(**timeline_data)
        self.db.add(timeline)
        self.db.commit()
        self.db.refresh(timeline)
        return timeline
    
    def update_timeline(self, timeline_id: int, update_data: Dict[str, Any]) -> Optional[EventTimeline]:
        """Update timeline by ID"""
        timeline = self.get_timeline_by_id(timeline_id)
        if not timeline:
            return None
        
        for field, value in update_data.items():
            if hasattr(timeline, field):
                setattr(timeline, field, value)
        
        self.db.commit()
        self.db.refresh(timeline)
        return timeline
    
    def delete_timeline(self, timeline_id: int) -> bool:
        """Soft delete timeline by ID"""
        timeline = self.get_timeline_by_id(timeline_id)
        if not timeline:
            return False
        
        timeline.is_active = False
        self.db.commit()
        return True
    
    # Timeline Item operations
    def get_timeline_item_by_id(self, item_id: int) -> Optional[TimelineItem]:
        """Get timeline item by ID"""
        return self.db.query(TimelineItem).options(
            joinedload(TimelineItem.timeline).joinedload(EventTimeline.event),
            joinedload(TimelineItem.assigned_to),
            joinedload(TimelineItem.task),
            joinedload(TimelineItem.dependencies),
            joinedload(TimelineItem.dependent_items)
        ).filter(TimelineItem.id == item_id).first()
    
    def get_timeline_items(
        self,
        timeline_id: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[TimelineItem]:
        """Get all items for a timeline"""
        query = self.db.query(TimelineItem).options(
            joinedload(TimelineItem.assigned_to)
        ).filter(TimelineItem.timeline_id == timeline_id)
        
        if filters:
            if filters.get('item_type'):
                query = query.filter(TimelineItem.item_type == filters['item_type'])
            
            if filters.get('status'):
                query = query.filter(TimelineItem.status == filters['status'])
            
            if filters.get('assigned_to_id'):
                query = query.filter(TimelineItem.assigned_to_id == filters['assigned_to_id'])
            elif filters.get('assignee_id'):
                query = query.filter(TimelineItem.assigned_to_id == filters['assignee_id'])
            
            if filters.get('start_date'):
                query = query.filter(TimelineItem.start_time >= filters['start_date'])
            
            if filters.get('end_date'):
                query = query.filter(TimelineItem.end_time <= filters['end_date'])
        
        return query.order_by(
            TimelineItem.order_index,
            TimelineItem.start_time
        ).all()
    
    def create_timeline_item(self, item_data: Dict[str, Any]) -> TimelineItem:
        """Create a new timeline item"""
        item = TimelineItem(**item_data)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        
        # Update timeline stats
        self.update_timeline_stats(item.timeline_id)
        
        return item
    
    def update_timeline_item(self, item_id: int, update_data: Dict[str, Any]) -> Optional[TimelineItem]:
        """Update timeline item by ID"""
        item = self.get_timeline_item_by_id(item_id)
        if not item:
            return None
        
        for field, value in update_data.items():
            if hasattr(item, field):
                setattr(item, field, value)
        
        self.db.commit()
        self.db.refresh(item)
        
        # Update timeline stats
        self.update_timeline_stats(item.timeline_id)
        
        return item
    
    def delete_timeline_item(self, item_id: int) -> bool:
        """Delete timeline item by ID"""
        item = self.get_timeline_item_by_id(item_id)
        if not item:
            return False
        
        timeline_id = item.timeline_id
        
        # Delete dependencies first
        self.db.query(TimelineDependency).filter(
            or_(
                TimelineDependency.item_id == item_id,
                TimelineDependency.depends_on_id == item_id
            )
        ).delete(synchronize_session=False)
        
        self.db.delete(item)
        self.db.commit()
        
        # Update timeline stats
        self.update_timeline_stats(timeline_id)
        
        return True
    
    def reorder_timeline_items(self, timeline_id: int, item_orders: List[Dict[str, Any]]) -> bool:
        """Reorder timeline items"""
        try:
            for item_order in item_orders:
                item = self.db.query(TimelineItem).filter(
                    TimelineItem.id == item_order['item_id'],
                    TimelineItem.timeline_id == timeline_id
                ).first()
                
                if item:
                    item.order_index = item_order['order_index']
            
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            return False
    
    # Timeline Dependency operations
    def create_timeline_dependency(self, dependency_data: Dict[str, Any]) -> TimelineDependency:
        """Create a new timeline dependency"""
        dependency = TimelineDependency(**dependency_data)
        self.db.add(dependency)
        self.db.commit()
        self.db.refresh(dependency)
        return dependency
    
    def get_item_dependencies(self, item_id: int) -> List[TimelineDependency]:
        """Get all dependencies for a timeline item"""
        return self.db.query(TimelineDependency).filter(
            TimelineDependency.dependent_item_id == item_id
        ).all()
    
    def get_item_prerequisites(self, item_id: int) -> List[TimelineDependency]:
        """Get all prerequisites for a timeline item"""
        return self.db.query(TimelineDependency).filter(
            TimelineDependency.prerequisite_item_id == item_id
        ).all()
    
    def delete_timeline_dependency(self, dependency_id: int) -> bool:
        """Delete timeline dependency by ID"""
        dependency = self.db.query(TimelineDependency).filter(
            TimelineDependency.id == dependency_id
        ).first()
        
        if not dependency:
            return False
        
        self.db.delete(dependency)
        self.db.commit()
        return True
    
    # Timeline Template operations
    def get_template_by_id(self, template_id: int) -> Optional[TimelineTemplate]:
        """Get timeline template by ID"""
        return self.db.query(TimelineTemplate).filter(
            TimelineTemplate.id == template_id
        ).first()
    
    def get_templates(
        self,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[TimelineTemplate], int]:
        """Get timeline templates with filters"""
        query = self.db.query(TimelineTemplate).options(
            joinedload(TimelineTemplate.creator)
        ).filter(TimelineTemplate.is_active == True)
        
        if filters:
            if filters.get('event_type'):
                query = query.filter(TimelineTemplate.event_type == filters['event_type'])
            
            if filters.get('creator_id'):
                query = query.filter(TimelineTemplate.creator_id == filters['creator_id'])
            
            if filters.get('is_public') is not None:
                query = query.filter(TimelineTemplate.is_public == filters['is_public'])
            
            if filters.get('category'):
                query = query.filter(TimelineTemplate.category == filters['category'])
        
        total = query.count()
        
        templates = query.order_by(
            desc(TimelineTemplate.usage_count),
            desc(TimelineTemplate.created_at)
        ).offset(pagination.offset).limit(pagination.limit).all()
        
        return templates, total
    
    def create_template(self, template_data: Dict[str, Any]) -> TimelineTemplate:
        """Create a new timeline template"""
        template = TimelineTemplate(**template_data)
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template
    
    def update_template(self, template_id: int, update_data: Dict[str, Any]) -> Optional[TimelineTemplate]:
        """Update timeline template by ID"""
        template = self.get_template_by_id(template_id)
        if not template:
            return None
        
        for field, value in update_data.items():
            if hasattr(template, field):
                setattr(template, field, value)
        
        self.db.commit()
        self.db.refresh(template)
        return template
    
    def increment_template_usage(self, template_id: int):
        """Increment template usage count"""
        template = self.get_template_by_id(template_id)
        if template:
            template.usage_count += 1
            self.db.commit()
    
    # Timeline Notification operations
    def create_timeline_notification(self, notification_data: Dict[str, Any]) -> TimelineNotification:
        """Create a new timeline notification"""
        notification = TimelineNotification(**notification_data)
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification
    
    def get_timeline_notifications(
        self,
        timeline_id: int,
        pagination: PaginationParams
    ) -> Tuple[List[TimelineNotification], int]:
        """Get notifications for a timeline"""
        query = self.db.query(TimelineNotification).filter(
            TimelineNotification.timeline_id == timeline_id
        )
        
        total = query.count()
        
        notifications = query.order_by(
            desc(TimelineNotification.created_at)
        ).offset(pagination.offset).limit(pagination.limit).all()
        
        return notifications, total
    
    def get_pending_notifications(self, limit: int = 100) -> List[TimelineNotification]:
        """Get pending timeline notifications"""
        return self.db.query(TimelineNotification).filter(
            TimelineNotification.is_sent == False,
            TimelineNotification.scheduled_time <= datetime.utcnow()
        ).limit(limit).all()
    
    def mark_notification_sent(self, notification_id: int):
        """Mark notification as sent"""
        notification = self.db.query(TimelineNotification).filter(
            TimelineNotification.id == notification_id
        ).first()
        
        if notification:
            notification.is_sent = True
            notification.sent_at = datetime.utcnow()
            self.db.commit()
    
    # Timeline Update operations
    def create_timeline_update(self, update_data: Dict[str, Any]) -> TimelineUpdate:
        """Create a new timeline update"""
        update = TimelineUpdate(**update_data)
        self.db.add(update)
        self.db.commit()
        self.db.refresh(update)
        return update
    
    def get_timeline_updates(
        self,
        timeline_id: int,
        pagination: PaginationParams
    ) -> Tuple[List[TimelineUpdate], int]:
        """Get updates for a timeline"""
        query = self.db.query(TimelineUpdate).options(
            joinedload(TimelineUpdate.user)
        ).filter(TimelineUpdate.timeline_id == timeline_id)
        
        total = query.count()
        
        updates = query.order_by(
            desc(TimelineUpdate.created_at)
        ).offset(pagination.offset).limit(pagination.limit).all()
        
        return updates, total
    
    # Search and filtering operations
    def search_timelines(
        self,
        search_params: Dict[str, Any],
        pagination: PaginationParams
    ) -> Tuple[List[EventTimeline], int]:
        """Search timelines with filters"""
        query = self.db.query(EventTimeline).options(
            joinedload(EventTimeline.creator),
            joinedload(EventTimeline.event)
        ).filter(EventTimeline.is_active == True)
        
        if search_params.get('query'):
            search_term = f"%{search_params['query']}%"
            query = query.filter(
                or_(
                    EventTimeline.title.ilike(search_term),
                    EventTimeline.description.ilike(search_term)
                )
            )
        
        if search_params.get('event_type'):
            query = query.join(Event).filter(Event.event_type == search_params['event_type'])
        
        if search_params.get('creator_id'):
            query = query.filter(EventTimeline.creator_id == search_params['creator_id'])
        
        if search_params.get('is_published') is not None:
            query = query.filter(EventTimeline.is_published == search_params['is_published'])
        
        total = query.count()
        
        timelines = query.order_by(
            desc(EventTimeline.is_main_timeline),
            desc(EventTimeline.created_at)
        ).offset(pagination.offset).limit(pagination.limit).all()
        
        return timelines, total
    
    def get_overdue_items(self, timeline_id: Optional[int] = None) -> List[TimelineItem]:
        """Get overdue timeline items"""
        query = self.db.query(TimelineItem).filter(
            TimelineItem.end_time < datetime.utcnow(),
            TimelineItem.status.in_([TimelineStatus.PENDING, TimelineStatus.IN_PROGRESS])
        )
        
        if timeline_id:
            query = query.filter(TimelineItem.timeline_id == timeline_id)
        
        return query.all()
    
    def get_upcoming_items(
        self,
        timeline_id: Optional[int] = None,
        hours_ahead: int = 24
    ) -> List[TimelineItem]:
        """Get upcoming timeline items"""
        upcoming_time = datetime.utcnow() + timedelta(hours=hours_ahead)
        
        query = self.db.query(TimelineItem).filter(
            TimelineItem.start_time <= upcoming_time,
            TimelineItem.start_time >= datetime.utcnow(),
            TimelineItem.status == TimelineStatus.PENDING
        )
        
        if timeline_id:
            query = query.filter(TimelineItem.timeline_id == timeline_id)
        
        return query.order_by(TimelineItem.start_time).all()
    
    # Statistics operations
    def get_timeline_statistics(self, timeline_id: int) -> Dict[str, Any]:
        """Get comprehensive statistics for a timeline"""
        items = self.get_timeline_items(timeline_id)
        
        if not items:
            return {
                "total_items": 0,
                "completed_items": 0,
                "in_progress_items": 0,
                "pending_items": 0,
                "overdue_items": 0,
                "completion_percentage": 0.0
            }
        
        total_items = len(items)
        completed_items = len([item for item in items if item.status == TimelineStatus.COMPLETED])
        in_progress_items = len([item for item in items if item.status == TimelineStatus.IN_PROGRESS])
        pending_items = len([item for item in items if item.status == TimelineStatus.PENDING])
        
        # Count overdue items
        now = datetime.utcnow()
        overdue_items = len([
            item for item in items 
            if item.end_time < now and item.status != TimelineStatus.COMPLETED
        ])
        
        completion_percentage = (completed_items / total_items) * 100 if total_items > 0 else 0
        
        return {
            "total_items": total_items,
            "completed_items": completed_items,
            "in_progress_items": in_progress_items,
            "pending_items": pending_items,
            "overdue_items": overdue_items,
            "completion_percentage": round(completion_percentage, 2)
        }
    
    def get_timeline_progress(self, timeline_id: int) -> Dict[str, Any]:
        """Get timeline progress information"""
        timeline = self.get_timeline_by_id(timeline_id)
        if not timeline:
            return {}
        
        items = self.get_timeline_items(timeline_id)
        stats = self.get_timeline_statistics(timeline_id)
        
        # Calculate time-based progress
        if timeline.start_time and timeline.end_time:
            total_duration = (timeline.end_time - timeline.start_time).total_seconds()
            elapsed_duration = (datetime.utcnow() - timeline.start_time).total_seconds()
            time_progress = min(100, max(0, (elapsed_duration / total_duration) * 100))
        else:
            time_progress = 0
        
        return {
            **stats,
            "time_progress_percentage": round(time_progress, 2),
            "is_on_schedule": stats["completion_percentage"] >= time_progress,
            "timeline_start": timeline.start_time,
            "timeline_end": timeline.end_time
        }
    
    # Helper methods
    def update_timeline_stats(self, timeline_id: int):
        """Update timeline statistics"""
        timeline = self.get_timeline_by_id(timeline_id)
        if not timeline:
            return
        
        items = self.get_timeline_items(timeline_id)
        total_duration = sum(item.duration_minutes for item in items)
        timeline.total_duration_minutes = total_duration if total_duration > 0 else None

        self.db.commit()
    
    def validate_timeline_conflicts(self, timeline_id: int) -> List[Dict[str, Any]]:
        """Validate timeline for scheduling conflicts"""
        items = self.get_timeline_items(timeline_id)
        conflicts = []
        
        for i, item1 in enumerate(items):
            for item2 in items[i+1:]:
                # Check for time overlap
                if (item1.start_time < item2.end_time and 
                    item2.start_time < item1.end_time):
                    conflicts.append({
                        "item1_id": item1.id,
                        "item1_title": item1.title,
                        "item2_id": item2.id,
                        "item2_title": item2.title,
                        "conflict_type": "time_overlap"
                    })
        
        return conflicts
    
    def count_total(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count total timelines with optional filters"""
        query = self.db.query(EventTimeline).filter(EventTimeline.is_active == True)
        
        if filters:
            if filters.get('event_id'):
                query = query.filter(EventTimeline.event_id == filters['event_id'])
            
            if filters.get('creator_id'):
                query = query.filter(EventTimeline.creator_id == filters['creator_id'])
        
        return query.count()
