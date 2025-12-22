from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, asc
from datetime import datetime, timedelta
from app.models.notification_models import (
    SmartReminder, NotificationLog, NotificationPreference, ReminderTemplate,
    AutomationRule, NotificationQueue, NotificationType, NotificationStatus,
    NotificationChannel, ReminderFrequency
)
from app.models.user_models import User
from app.models.event_models import Event, EventInvitation
from app.schemas.pagination import PaginationParams, SortParams

class NotificationRepository:
    """Repository for notification and smart reminder data access operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # Smart Reminder CRUD operations
    def get_reminder_by_id(
        self, 
        reminder_id: int, 
        include_relations: bool = False
    ) -> Optional[SmartReminder]:
        """Get smart reminder by ID with optional relation loading"""
        query = self.db.query(SmartReminder).filter(SmartReminder.id == reminder_id)
        
        if include_relations:
            query = query.options(
                joinedload(SmartReminder.creator),
                joinedload(SmartReminder.event),
                joinedload(SmartReminder.template)
            )
        
        return query.first()
    
    def get_event_reminders(
        self,
        event_id: int,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[SmartReminder], int]:
        """Get reminders for an event"""
        query = self.db.query(SmartReminder).options(
            joinedload(SmartReminder.creator)
        ).filter(
            SmartReminder.event_id == event_id,
            SmartReminder.is_active == True
        )
        
        if filters:
            if filters.get('notification_type'):
                query = query.filter(SmartReminder.notification_type == filters['notification_type'])
            
            if filters.get('status'):
                query = query.filter(SmartReminder.status == filters['status'])
            
            if filters.get('creator_id'):
                query = query.filter(SmartReminder.creator_id == filters['creator_id'])
            
            if filters.get('frequency'):
                query = query.filter(SmartReminder.frequency == filters['frequency'])
        
        total = query.count()
        
        reminders = query.order_by(
            SmartReminder.scheduled_time.asc(),
            SmartReminder.created_at.desc()
        ).offset(pagination.offset).limit(pagination.limit).all()
        
        return reminders, total
    
    def get_user_reminders(
        self,
        user_id: int,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[SmartReminder], int]:
        """Get reminders created by a user"""
        query = self.db.query(SmartReminder).options(
            joinedload(SmartReminder.event)
        ).filter(
            SmartReminder.creator_id == user_id,
            SmartReminder.is_active == True
        )
        
        if filters:
            if filters.get('event_id'):
                query = query.filter(SmartReminder.event_id == filters['event_id'])
            
            if filters.get('status'):
                query = query.filter(SmartReminder.status == filters['status'])
        
        total = query.count()
        
        reminders = query.order_by(
            SmartReminder.scheduled_time.asc()
        ).offset(pagination.offset).limit(pagination.limit).all()
        
        return reminders, total
    
    def create_reminder(self, reminder_data: Dict[str, Any]) -> SmartReminder:
        """Create a new smart reminder"""
        reminder = SmartReminder(**reminder_data)
        self.db.add(reminder)
        self.db.commit()
        self.db.refresh(reminder)
        return reminder
    
    def update_reminder(self, reminder_id: int, update_data: Dict[str, Any]) -> Optional[SmartReminder]:
        """Update smart reminder by ID"""
        reminder = self.get_reminder_by_id(reminder_id)
        if not reminder:
            return None
        
        for field, value in update_data.items():
            if hasattr(reminder, field):
                setattr(reminder, field, value)
        
        self.db.commit()
        self.db.refresh(reminder)
        return reminder
    
    def delete_reminder(self, reminder_id: int) -> bool:
        """Soft delete smart reminder by ID"""
        reminder = self.get_reminder_by_id(reminder_id)
        if not reminder:
            return False
        
        reminder.is_active = False
        self.db.commit()
        return True
    
    def get_pending_reminders(self, limit: int = 100) -> List[SmartReminder]:
        """Get pending reminders that need to be processed"""
        return self.db.query(SmartReminder).filter(
            SmartReminder.is_active == True,
            SmartReminder.status == NotificationStatus.PENDING,
            SmartReminder.scheduled_time <= datetime.utcnow()
        ).limit(limit).all()
    
    def get_recurring_reminders(self) -> List[SmartReminder]:
        """Get recurring reminders that need to be rescheduled"""
        return self.db.query(SmartReminder).filter(
            SmartReminder.is_active == True,
            SmartReminder.frequency != ReminderFrequency.ONCE,
            SmartReminder.status == NotificationStatus.SENT,
            SmartReminder.next_occurrence <= datetime.utcnow()
        ).all()
    
    # Notification Queue operations
    def create_notification_queue_item(self, queue_data: Dict[str, Any]) -> NotificationQueue:
        """Create a new notification queue item"""
        queue_item = NotificationQueue(**queue_data)
        self.db.add(queue_item)
        self.db.commit()
        self.db.refresh(queue_item)
        return queue_item
    
    def get_queued_notifications(
        self,
        limit: int = 50,
        channel: Optional[NotificationChannel] = None
    ) -> List[NotificationQueue]:
        """Get queued notifications ready for processing"""
        query = self.db.query(NotificationQueue).filter(
            NotificationQueue.status == 'queued',
            NotificationQueue.scheduled_for <= datetime.utcnow()
        )
        
        if channel:
            query = query.filter(NotificationQueue.channel == channel)
        
        return query.order_by(
            NotificationQueue.priority.asc(),
            NotificationQueue.scheduled_for.asc()
        ).limit(limit).all()
    
    def update_notification_queue_status(
        self, 
        queue_id: int, 
        status: str, 
        error_message: Optional[str] = None
    ) -> Optional[NotificationQueue]:
        """Update notification queue item status"""
        queue_item = self.db.query(NotificationQueue).filter(
            NotificationQueue.id == queue_id
        ).first()
        
        if not queue_item:
            return None
        
        queue_item.status = status
        queue_item.attempts += 1
        
        if status == 'sent':
            queue_item.sent_at = datetime.utcnow()
        elif status == 'failed':
            queue_item.error_message = error_message
            queue_item.failed_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(queue_item)
        return queue_item
    
    def get_failed_notifications(self, max_attempts: int = 3) -> List[NotificationQueue]:
        """Get failed notifications for retry"""
        return self.db.query(NotificationQueue).filter(
            NotificationQueue.status == 'failed',
            NotificationQueue.attempts < max_attempts
        ).all()
    
    def cancel_queued_notifications(self, reminder_id: int) -> int:
        """Cancel all queued notifications for a reminder"""
        updated_count = self.db.query(NotificationQueue).filter(
            NotificationQueue.reminder_id == reminder_id,
            NotificationQueue.status == 'queued'
        ).update({'status': 'cancelled'})
        
        self.db.commit()
        return updated_count
    
    # Notification Log operations
    def create_notification_log(self, log_data: Dict[str, Any]) -> NotificationLog:
        """Create a new notification log entry"""
        log_entry = NotificationLog(**log_data)
        self.db.add(log_entry)
        self.db.commit()
        self.db.refresh(log_entry)
        return log_entry
    
    def get_notification_logs(
        self,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[NotificationLog], int]:
        """Get notification logs with filters"""
        query = self.db.query(NotificationLog).options(
            joinedload(NotificationLog.recipient),
            joinedload(NotificationLog.event)
        )
        
        if filters:
            if filters.get('event_id'):
                query = query.filter(NotificationLog.event_id == filters['event_id'])
            
            if filters.get('recipient_id'):
                query = query.filter(NotificationLog.recipient_id == filters['recipient_id'])
            
            if filters.get('notification_type'):
                query = query.filter(NotificationLog.notification_type == filters['notification_type'])
            
            if filters.get('channel'):
                query = query.filter(NotificationLog.channel == filters['channel'])
            
            if filters.get('status'):
                query = query.filter(NotificationLog.status == filters['status'])
            
            if filters.get('start_date'):
                query = query.filter(NotificationLog.created_at >= filters['start_date'])
            
            if filters.get('end_date'):
                query = query.filter(NotificationLog.created_at <= filters['end_date'])
        
        total = query.count()
        
        logs = query.order_by(
            desc(NotificationLog.created_at)
        ).offset(pagination.offset).limit(pagination.limit).all()
        
        return logs, total

    def get_user_notifications(
        self,
        user_id: int,
        limit: int,
        include_read: bool = True
    ) -> List[NotificationLog]:
        """Get notifications for a user"""
        query = self.db.query(NotificationLog).options(
            joinedload(NotificationLog.event),
            joinedload(NotificationLog.recipient)
        ).filter(NotificationLog.recipient_id == user_id)

        if not include_read:
            query = query.filter(NotificationLog.read_at.is_(None))

        return query.order_by(desc(NotificationLog.created_at)).limit(limit).all()

    def count_user_notifications(self, user_id: int) -> int:
        """Count total notifications for a user"""
        return self.db.query(NotificationLog).filter(
            NotificationLog.recipient_id == user_id
        ).count()

    def count_unread_notifications(self, user_id: int) -> int:
        """Count unread notifications for a user"""
        return self.db.query(NotificationLog).filter(
            NotificationLog.recipient_id == user_id,
            NotificationLog.read_at.is_(None)
        ).count()
    
    # Notification Preferences operations
    def get_user_preferences(self, user_id: int) -> List[NotificationPreference]:
        """Get notification preferences for a user"""
        return self.db.query(NotificationPreference).filter(
            NotificationPreference.user_id == user_id
        ).all()
    
    def get_user_preference(
        self, 
        user_id: int, 
        notification_type: NotificationType
    ) -> Optional[NotificationPreference]:
        """Get specific notification preference for a user"""
        return self.db.query(NotificationPreference).filter(
            NotificationPreference.user_id == user_id,
            NotificationPreference.notification_type == notification_type
        ).first()
    
    def create_user_preference(self, preference_data: Dict[str, Any]) -> NotificationPreference:
        """Create a new notification preference"""
        preference = NotificationPreference(**preference_data)
        self.db.add(preference)
        self.db.commit()
        self.db.refresh(preference)
        return preference
    
    def update_user_preferences(self, user_id: int, preferences: List[Dict[str, Any]]) -> List[NotificationPreference]:
        """Update user notification preferences"""
        # Delete existing preferences
        self.db.query(NotificationPreference).filter(
            NotificationPreference.user_id == user_id
        ).delete()
        
        # Create new preferences
        created_preferences = []
        for pref_data in preferences:
            pref_data['user_id'] = user_id
            preference = NotificationPreference(**pref_data)
            self.db.add(preference)
            created_preferences.append(preference)
        
        self.db.commit()
        
        for pref in created_preferences:
            self.db.refresh(pref)
        
        return created_preferences
    
    # Reminder Template operations
    def get_template_by_id(self, template_id: int) -> Optional[ReminderTemplate]:
        """Get reminder template by ID"""
        return self.db.query(ReminderTemplate).filter(
            ReminderTemplate.id == template_id
        ).first()
    
    def get_reminder_templates(
        self,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[ReminderTemplate], int]:
        """Get reminder templates with filters"""
        query = self.db.query(ReminderTemplate).options(
            joinedload(ReminderTemplate.creator)
        ).filter(ReminderTemplate.is_active == True)
        
        if filters:
            if filters.get('notification_type'):
                query = query.filter(ReminderTemplate.notification_type == filters['notification_type'])
            
            if filters.get('creator_id'):
                query = query.filter(ReminderTemplate.creator_id == filters['creator_id'])
            
            if filters.get('is_public') is not None:
                query = query.filter(ReminderTemplate.is_public == filters['is_public'])
            
            if filters.get('category'):
                query = query.filter(ReminderTemplate.category == filters['category'])
        
        total = query.count()
        
        templates = query.order_by(
            desc(ReminderTemplate.is_featured),
            desc(ReminderTemplate.usage_count),
            desc(ReminderTemplate.created_at)
        ).offset(pagination.offset).limit(pagination.limit).all()
        
        return templates, total
    
    def create_reminder_template(self, template_data: Dict[str, Any]) -> ReminderTemplate:
        """Create a new reminder template"""
        template = ReminderTemplate(**template_data)
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template
    
    def update_reminder_template(
        self, 
        template_id: int, 
        update_data: Dict[str, Any]
    ) -> Optional[ReminderTemplate]:
        """Update reminder template by ID"""
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
    
    # Automation Rule operations
    def get_automation_rules(
        self,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[AutomationRule], int]:
        """Get automation rules with filters"""
        query = self.db.query(AutomationRule).options(
            joinedload(AutomationRule.creator)
        ).filter(AutomationRule.is_active == True)
        
        if filters:
            if filters.get('trigger_event'):
                query = query.filter(AutomationRule.trigger_event == filters['trigger_event'])
            
            if filters.get('creator_id'):
                query = query.filter(AutomationRule.creator_id == filters['creator_id'])
        
        total = query.count()
        
        rules = query.order_by(
            desc(AutomationRule.created_at)
        ).offset(pagination.offset).limit(pagination.limit).all()
        
        return rules, total
    
    def create_automation_rule(self, rule_data: Dict[str, Any]) -> AutomationRule:
        """Create a new automation rule"""
        rule = AutomationRule(**rule_data)
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule
    
    def get_active_automation_rules(self, trigger_event: str) -> List[AutomationRule]:
        """Get active automation rules for a specific trigger event"""
        return self.db.query(AutomationRule).filter(
            AutomationRule.is_active == True,
            AutomationRule.trigger_event == trigger_event
        ).all()
    
    # Analytics and statistics operations
    def get_notification_analytics(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get notification analytics with filters"""
        query = self.db.query(NotificationLog)
        
        if filters:
            if filters.get('event_id'):
                query = query.filter(NotificationLog.event_id == filters['event_id'])
            
            if filters.get('user_id'):
                query = query.filter(NotificationLog.recipient_id == filters['user_id'])
            
            if filters.get('start_date'):
                query = query.filter(NotificationLog.created_at >= filters['start_date'])
            
            if filters.get('end_date'):
                query = query.filter(NotificationLog.created_at <= filters['end_date'])
        
        logs = query.all()
        
        if not logs:
            return {
                "total_sent": 0,
                "delivery_rate": 0.0,
                "by_type": {},
                "by_channel": {},
                "by_status": {}
            }
        
        total_sent = len(logs)
        successful_deliveries = len([log for log in logs if log.status == NotificationStatus.SENT])
        delivery_rate = (successful_deliveries / total_sent) * 100 if total_sent > 0 else 0
        
        # Group by type
        by_type = {}
        for log in logs:
            type_name = log.notification_type.value if log.notification_type else 'unknown'
            by_type[type_name] = by_type.get(type_name, 0) + 1
        
        # Group by channel
        by_channel = {}
        for log in logs:
            channel_name = log.channel.value if log.channel else 'unknown'
            by_channel[channel_name] = by_channel.get(channel_name, 0) + 1
        
        # Group by status
        by_status = {}
        for log in logs:
            status_name = log.status.value if log.status else 'unknown'
            by_status[status_name] = by_status.get(status_name, 0) + 1
        
        return {
            "total_sent": total_sent,
            "delivery_rate": round(delivery_rate, 2),
            "by_type": by_type,
            "by_channel": by_channel,
            "by_status": by_status
        }
    
    def get_user_notification_stats(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get notification statistics for a specific user"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get logs for the user
        logs = self.db.query(NotificationLog).filter(
            NotificationLog.recipient_id == user_id,
            NotificationLog.created_at >= start_date
        ).all()
        
        # Get reminders created by the user
        reminders = self.db.query(SmartReminder).filter(
            SmartReminder.creator_id == user_id,
            SmartReminder.created_at >= start_date
        ).all()
        
        return {
            "notifications_received": len(logs),
            "reminders_created": len(reminders),
            "active_reminders": len([r for r in reminders if r.is_active]),
            "engagement_rate": 85.0  # This would be calculated based on actual engagement
        }
    
    # Search and filtering operations
    def search_reminders(
        self,
        search_params: Dict[str, Any],
        pagination: PaginationParams
    ) -> Tuple[List[SmartReminder], int]:
        """Search reminders with filters"""
        query = self.db.query(SmartReminder).options(
            joinedload(SmartReminder.creator),
            joinedload(SmartReminder.event)
        ).filter(SmartReminder.is_active == True)
        
        if search_params.get('query'):
            search_term = f"%{search_params['query']}%"
            query = query.filter(
                or_(
                    SmartReminder.title.ilike(search_term),
                    SmartReminder.message.ilike(search_term)
                )
            )
        
        if search_params.get('notification_type'):
            query = query.filter(SmartReminder.notification_type == search_params['notification_type'])
        
        if search_params.get('status'):
            query = query.filter(SmartReminder.status == search_params['status'])
        
        if search_params.get('creator_id'):
            query = query.filter(SmartReminder.creator_id == search_params['creator_id'])
        
        total = query.count()
        
        reminders = query.order_by(
            SmartReminder.scheduled_time.asc()
        ).offset(pagination.offset).limit(pagination.limit).all()
        
        return reminders, total
    
    def get_reminder_targets(self, reminder: SmartReminder) -> List[User]:
        """Get target users for a reminder based on its configuration"""
        if reminder.target_all_guests:
            # Get all invited users for the event
            invitations = self.db.query(EventInvitation).filter(
                EventInvitation.event_id == reminder.event_id
            ).all()
            
            user_ids = [inv.user_id for inv in invitations]
            
            # Filter by RSVP status if specified
            if reminder.target_rsvp_status:
                user_ids = [
                    inv.user_id for inv in invitations 
                    if inv.rsvp_status == reminder.target_rsvp_status
                ]
            
            return self.db.query(User).filter(User.id.in_(user_ids)).all()
        
        elif reminder.target_user_ids:
            # Get specific users
            return self.db.query(User).filter(
                User.id.in_(reminder.target_user_ids)
            ).all()
        
        return []
    
    def count_total(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count total reminders with optional filters"""
        query = self.db.query(SmartReminder).filter(SmartReminder.is_active == True)
        
        if filters:
            if filters.get('event_id'):
                query = query.filter(SmartReminder.event_id == filters['event_id'])
            
            if filters.get('creator_id'):
                query = query.filter(SmartReminder.creator_id == filters['creator_id'])
        
        return query.count()