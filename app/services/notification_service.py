from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, time
import asyncio
from app.repositories.notification_repo import NotificationRepository
from app.repositories.event_repo import EventRepository
from app.repositories.user_repo import UserRepository
from app.models.notification_models import (
    NotificationType, NotificationStatus, NotificationChannel, ReminderFrequency
)
from app.models.event_models import EventInvitation
from app.models.user_models import User
from app.schemas.pagination import PaginationParams
from app.core.errors import NotFoundError, ValidationError, AuthorizationError
from app.services.email_service import EmailService
from app.services.sms_service import SMSService
from app.services.push_service import push_service
from app.services.websocket_manager import websocket_manager
from app.core.logger import get_logger

# Initialize logger
logger = get_logger(__name__)

class NotificationService:
    """Service for managing smart reminders and notifications."""
    
    def __init__(self, db: Session):
        self.db = db
        self.notification_repo = NotificationRepository(db)
        self.event_repo = EventRepository(db)
        self.user_repo = UserRepository(db)
        
        # Initialize services for sending notifications
        self.email_service = EmailService()
        self.sms_service = SMSService()
    
    # Smart Reminder CRUD operations
    def create_reminder(
        self, 
        event_id: int, 
        user_id: int, 
        reminder_data: Dict[str, Any]
    ):
        """Create a new smart reminder."""
        # Verify event access
        event = self._get_event_with_access(event_id, user_id)
        
        # Prepare reminder data
        processed_data = {
            'title': reminder_data['title'],
            'message': reminder_data['message'],
            'notification_type': NotificationType(reminder_data['notification_type']),
            'scheduled_time': reminder_data['scheduled_time'],
            'frequency': ReminderFrequency(reminder_data.get('frequency', 'once')),
            'event_id': event_id,
            'creator_id': user_id,
            'target_all_guests': reminder_data.get('target_all_guests', True),
            'target_user_ids': reminder_data.get('target_user_ids'),
            'target_rsvp_status': reminder_data.get('target_rsvp_status'),
            'send_email': reminder_data.get('send_email', True),
            'send_sms': reminder_data.get('send_sms', False),
            'send_push': reminder_data.get('send_push', True),
            'send_in_app': reminder_data.get('send_in_app', True),
            'template_id': reminder_data.get('template_id'),
            'custom_data': reminder_data.get('custom_data', {})
        }
        
        # Create reminder
        reminder = self.notification_repo.create_reminder(processed_data)
        
        # Queue notifications for delivery
        self._queue_reminder_notifications(reminder)
        
        return reminder
    
    def get_event_reminders(
        self, 
        event_id: int, 
        user_id: int, 
        search_params: Dict[str, Any]
    ) -> Tuple[List, int]:
        """Get reminders for an event."""
        
        # Verify event access
        self._get_event_with_access(event_id, user_id)
        
        # Create pagination params
        page = search_params.get('page', 1)
        per_page = search_params.get('per_page', 20)
        pagination = PaginationParams(page=page, per_page=per_page)
        
        # Extract filters
        filters = {
            'notification_type': search_params.get('notification_type'),
            'status': search_params.get('status'),
            'creator_id': search_params.get('creator_id'),
            'frequency': search_params.get('frequency')
        }
        
        return self.notification_repo.get_event_reminders(event_id, pagination, filters)
    
    def update_reminder(
        self, 
        reminder_id: int, 
        user_id: int, 
        update_data: Dict[str, Any]
    ):
        """Update a smart reminder."""
        reminder = self.notification_repo.get_reminder_by_id(reminder_id)
        
        if not reminder:
            raise NotFoundError("Reminder not found")
        
        # Check permissions
        event = self._get_event_with_access(reminder.event_id, user_id)
        if not self._can_edit_reminder(reminder, event, user_id):
            raise AuthorizationError("You don't have permission to edit this reminder")
        
        # Update reminder
        updated_reminder = self.notification_repo.update_reminder(reminder_id, update_data)
        
        # If scheduling changed, requeue notifications
        if 'scheduled_time' in update_data or 'frequency' in update_data:
            self._requeue_reminder_notifications(updated_reminder)
        
        return updated_reminder
    
    def delete_reminder(self, reminder_id: int, user_id: int) -> bool:
        """Delete a smart reminder."""
        reminder = self.notification_repo.get_reminder_by_id(reminder_id)
        
        if not reminder:
            raise NotFoundError("Reminder not found")
        
        # Check permissions
        event = self._get_event_with_access(reminder.event_id, user_id)
        if not self._can_edit_reminder(reminder, event, user_id):
            raise AuthorizationError("You don't have permission to delete this reminder")
        
        # Cancel queued notifications
        self.notification_repo.cancel_queued_notifications(reminder_id)
        
        # Delete reminder
        return self.notification_repo.delete_reminder(reminder_id)
    
    # Automatic reminder creation
    def create_automatic_reminders(self, event_id: int) -> List:
        """Create automatic reminders for an event."""
        event = self.event_repo.get_by_id(event_id)
        
        if not event:
            raise NotFoundError("Event not found")
        
        created_reminders = []
        
        # Create RSVP reminder (7 days before event)
        rsvp_reminder = self._create_rsvp_reminder(event)
        if rsvp_reminder:
            created_reminders.append(rsvp_reminder)
        
        # Create event reminders (1 month, 1 week, 1 day, and day-of)
        event_reminders = self._create_event_reminders(event)
        if event_reminders:
            created_reminders.extend(event_reminders)
        
        # Create dress code reminder if applicable
        dress_code_reminder = self._create_dress_code_reminder(event)
        if dress_code_reminder:
            created_reminders.append(dress_code_reminder)
        
        return created_reminders
    
    # Notification processing
    async def process_pending_notifications(self, limit: int = 50) -> int:
        """Process pending notifications in the queue."""
        notifications = self.notification_repo.get_queued_notifications(limit)
        processed_count = 0
        
        for notification in notifications:
            try:
                # Send notification based on channel
                success = await self._send_notification(notification)
                
                if success:
                    # Mark as sent
                    self.notification_repo.update_notification_queue_status(
                        notification.id, 'sent'
                    )
                    
                    # Log successful delivery
                    self._log_notification(notification, NotificationStatus.SENT)
                else:
                    # Mark as failed
                    self.notification_repo.update_notification_queue_status(
                        notification.id, 'failed', 'Delivery failed'
                    )
                    
                    # Log failed delivery
                    self._log_notification(notification, NotificationStatus.FAILED)
                
                processed_count += 1
                
            except Exception as e:
                # Mark as failed with error
                self.notification_repo.update_notification_queue_status(
                    notification.id, 'failed', str(e)
                )
                
                # Log error
                self._log_notification(notification, NotificationStatus.FAILED)
        
        return processed_count
    
    # Notification preferences
    def get_user_preferences(self, user_id: int) -> List:
        """Get notification preferences for a user, seeding defaults on first access."""
        preferences = self.notification_repo.get_user_preferences(user_id)
        if preferences:
            return preferences

        default_preferences = self._build_default_preferences()
        if not default_preferences:
            return []

        return self.notification_repo.update_user_preferences(user_id, default_preferences)
    
    def update_user_preferences(
        self, 
        user_id: int, 
        preferences: List[Dict[str, Any]]
    ) -> List:
        """Update user notification preferences."""
        return self.notification_repo.update_user_preferences(user_id, preferences)

    def _build_default_preferences(self) -> List[Dict[str, Any]]:
        """Construct the system default preference payloads for every notification type."""
        defaults: List[Dict[str, Any]] = []

        for notification_type in NotificationType:
            defaults.append(
                {
                    'notification_type': notification_type,
                    'email_enabled': True,
                    'sms_enabled': False,
                    'push_enabled': True,
                    'in_app_enabled': True,
                    'advance_notice_hours': 24,
                    'quiet_hours_start': None,
                    'quiet_hours_end': None,
                    'max_daily_notifications': 10,
                }
            )

        return defaults
    
    # Template management
    def create_reminder_template(
        self, 
        user_id: int, 
        template_data: Dict[str, Any]
    ):
        """Create a reminder template."""
        processed_data = {
            'name': template_data['name'],
            'description': template_data.get('description'),
            'notification_type': NotificationType(template_data['notification_type']),
            'subject_template': template_data['subject_template'],
            'message_template': template_data['message_template'],
            'template_variables': template_data.get('template_variables', []),
            'creator_id': user_id,
            'is_public': template_data.get('is_public', False),
            'category': template_data.get('category')
        }
        
        return self.notification_repo.create_reminder_template(processed_data)
    
    def get_reminder_templates(
        self, 
        user_id: int, 
        notification_type: Optional[NotificationType] = None,
        search_params: Optional[Dict[str, Any]] = None
    ) -> Tuple[List, int]:
        """Get reminder templates."""
        
        # Create pagination params
        page = search_params.get('page', 1) if search_params else 1
        per_page = search_params.get('per_page', 20) if search_params else 20
        pagination = PaginationParams(page=page, per_page=per_page)
        
        # Extract filters
        filters = {
            'notification_type': notification_type,
            'creator_id': user_id,
            'is_public': search_params.get('is_public') if search_params else None,
            'category': search_params.get('category') if search_params else None
        }
        
        return self.notification_repo.get_reminder_templates(pagination, filters)
    
    # Analytics and reporting
    def get_notification_analytics(
        self, 
        event_id: Optional[int] = None, 
        user_id: Optional[int] = None, 
        days: int = 30
    ) -> Dict[str, Any]:
        """Get notification analytics."""
        filters = {}
        
        if event_id:
            filters['event_id'] = event_id
        
        if user_id:
            filters['user_id'] = user_id
        
        if days:
            filters['start_date'] = datetime.utcnow() - timedelta(days=days)
        
        return self.notification_repo.get_notification_analytics(filters)
    
    def get_notification_logs(
        self, 
        search_params: Dict[str, Any]
    ) -> Tuple[List, int]:
        """Get notification logs with filters."""
        
        # Create pagination params
        page = search_params.get('page', 1)
        per_page = search_params.get('per_page', 50)
        pagination = PaginationParams(page=page, per_page=per_page)
        
        # Extract filters
        filters = {
            'event_id': search_params.get('event_id'),
            'recipient_id': search_params.get('recipient_id'),
            'notification_type': search_params.get('notification_type'),
            'channel': search_params.get('channel'),
            'status': search_params.get('status'),
            'start_date': search_params.get('start_date'),
            'end_date': search_params.get('end_date')
        }
        
        return self.notification_repo.get_notification_logs(pagination, filters)
    
    # Queue management
    def get_queue_status(self) -> Dict[str, Any]:
        """Get notification queue status."""
        # Get counts by status
        queued_count = len(self.notification_repo.get_queued_notifications(limit=1000))
        failed_count = len(self.notification_repo.get_failed_notifications())
        
        return {
            'queued_notifications': queued_count,
            'failed_notifications': failed_count,
            'processing_status': 'active' if queued_count > 0 else 'idle'
        }

    def get_user_notifications(
        self,
        user_id: int,
        limit: int = 50,
        unread_only: bool = False
    ) -> Dict[str, Any]:
        """Get notifications for a specific user."""
        page_size = max(1, min(limit, 100))

        notifications = self.notification_repo.get_user_notifications(
            user_id=user_id,
            limit=page_size,
            include_read=not unread_only
        )

        total = self.notification_repo.count_user_notifications(user_id)
        unread_count = self.notification_repo.count_unread_notifications(user_id)

        return {
            'notifications': notifications,
            'total': total,
            'unread_count': unread_count,
            'limit': page_size
        }
    
    def retry_failed_notifications(self) -> int:
        """Retry failed notifications."""
        failed_notifications = self.notification_repo.get_failed_notifications()
        retry_count = 0
        
        for notification in failed_notifications:
            # Reset status to queued for retry
            self.notification_repo.update_notification_queue_status(
                notification.id, 'queued'
            )
            retry_count += 1
        
        return retry_count
    
    # Test notifications
    def send_test_notification(
        self, 
        user_id: int, 
        channel: NotificationChannel, 
        test_data: Dict[str, Any]
    ) -> bool:
        """Send a test notification."""
        # Create test notification queue item
        queue_data = {
            'reminder_id': None,
            'event_id': None,
            'recipient_id': user_id,
            'notification_type': NotificationType.CUSTOM,
            'channel': channel,
            'subject': test_data.get('subject', 'Test Notification'),
            'message': test_data.get('message', 'This is a test notification.'),
            'scheduled_time': datetime.utcnow(),
            'priority': 5,
            'status': 'queued'
        }
        
        test_notification = self.notification_repo.create_notification_queue_item(queue_data)
        
        # Send immediately
        try:
            success = asyncio.run(self._send_notification(test_notification))
            
            # Update status
            status = 'sent' if success else 'failed'
            self.notification_repo.update_notification_queue_status(
                test_notification.id, status
            )
            
            return success
            
        except Exception as e:
            self.notification_repo.update_notification_queue_status(
                test_notification.id, 'failed', str(e)
            )
            return False
    
    # Automation rules
    def create_automation_rule(
        self, 
        user_id: int, 
        rule_data: Dict[str, Any]
    ):
        """Create an automation rule."""
        processed_data = {
            'name': rule_data['name'],
            'description': rule_data.get('description'),
            'trigger_event': rule_data['trigger_event'],
            'conditions': rule_data.get('conditions', {}),
            'actions': rule_data['actions'],
            'creator_id': user_id,
            'is_active': rule_data.get('is_active', True)
        }
        
        return self.notification_repo.create_automation_rule(processed_data)
    
    def get_automation_rules(
        self, 
        user_id: int, 
        search_params: Dict[str, Any]
    ) -> Tuple[List, int]:
        """Get automation rules."""
        
        # Create pagination params
        page = search_params.get('page', 1)
        per_page = search_params.get('per_page', 20)
        pagination = PaginationParams(page=page, per_page=per_page)
        
        # Extract filters
        filters = {
            'trigger_event': search_params.get('trigger_event'),
            'creator_id': user_id
        }
        
        return self.notification_repo.get_automation_rules(pagination, filters)
    
    # Helper methods
    def _get_event_with_access(self, event_id: int, user_id: int):
        """Get event and verify user has access."""
        event = self.event_repo.get_by_id(event_id, include_relations=True)
        
        if not event:
            raise NotFoundError("Event not found")
        
        # Check access (creator, collaborator, or invited)
        if event.creator_id != user_id:
            # Check if user is collaborator or invited (invitations loaded with include_relations)
            if not any(inv.user_id == user_id for inv in (event.invitations or [])):
                raise AuthorizationError("You don't have access to this event")
        
        return event
    
    def _can_edit_reminder(self, reminder, event, user_id: int) -> bool:
        """Check if user can edit a reminder."""
        # Reminder creator can edit
        if reminder.creator_id == user_id:
            return True
        
        # Event creator can edit
        if event.creator_id == user_id:
            return True
        
        return False
    
    def _queue_reminder_notifications(self, reminder):
        """Queue notifications for a reminder."""
        # Get target users
        target_users = self.notification_repo.get_reminder_targets(reminder)
        
        for user in target_users:
            # Get user preferences
            preferences = self._get_user_notification_preferences(
                user.id, reminder.notification_type
            )
            
            # Queue notifications based on preferences and reminder settings
            channels_to_send = []
            
            if reminder.send_email and preferences.get('email_enabled', True):
                channels_to_send.append(NotificationChannel.EMAIL)
            
            if reminder.send_sms and preferences.get('sms_enabled', False):
                channels_to_send.append(NotificationChannel.SMS)
            
            if reminder.send_push and preferences.get('push_enabled', True):
                channels_to_send.append(NotificationChannel.PUSH)
            
            if reminder.send_in_app and preferences.get('in_app_enabled', True):
                channels_to_send.append(NotificationChannel.IN_APP)
            
            # Create queue items for each channel
            for channel in channels_to_send:
                self._queue_notification(
                    reminder, user, channel, preferences
                )
    
    def _queue_notification(self, reminder, user, channel: NotificationChannel, preferences: Dict):
        """Queue a single notification."""
        # Calculate scheduled time based on user preferences
        scheduled_time = reminder.scheduled_time
        
        # Apply user's advance notice preference
        advance_notice_hours = preferences.get('advance_notice_hours', 0)
        if advance_notice_hours > 0:
            scheduled_time = scheduled_time - timedelta(hours=advance_notice_hours)
        
        # Check quiet hours
        if self._is_quiet_hours(scheduled_time, preferences):
            # Adjust to next available time
            scheduled_time = self._adjust_for_quiet_hours(scheduled_time, preferences)
        
        queue_data = {
            'reminder_id': reminder.id,
            'event_id': reminder.event_id,
            'recipient_id': user.id,
            'notification_type': reminder.notification_type,
            'channel': channel,
            'subject': reminder.title,
            'message': reminder.message,
            'scheduled_time': scheduled_time,
            'priority': self._get_notification_priority(reminder.notification_type),
            'status': 'queued'
        }
        
        self.notification_repo.create_notification_queue_item(queue_data)
    
    def _requeue_reminder_notifications(self, reminder):
        """Cancel existing notifications and queue new ones."""
        # Cancel existing queued notifications
        self.notification_repo.cancel_queued_notifications(reminder.id)
        
        # Queue new notifications
        self._queue_reminder_notifications(reminder)
    
    def _get_user_notification_preferences(self, user_id: int, notification_type: NotificationType) -> Dict:
        """Get user notification preferences for a specific type."""
        preference = self.notification_repo.get_user_preference(user_id, notification_type)
        
        if preference:
            return {
                'email_enabled': preference.email_enabled,
                'sms_enabled': preference.sms_enabled,
                'push_enabled': preference.push_enabled,
                'in_app_enabled': preference.in_app_enabled,
                'advance_notice_hours': preference.advance_notice_hours,
                'quiet_hours_start': preference.quiet_hours_start,
                'quiet_hours_end': preference.quiet_hours_end
            }
        
        # Return default preferences
        return {
            'email_enabled': True,
            'sms_enabled': False,
            'push_enabled': True,
            'in_app_enabled': True,
            'advance_notice_hours': 0,
            'quiet_hours_start': '22:00',
            'quiet_hours_end': '08:00'
        }
    
    def _get_notification_priority(self, notification_type: NotificationType) -> int:
        """Get priority for notification type (1=highest, 5=lowest)."""
        priority_map = {
            NotificationType.EVENT_REMINDER: 1,
            NotificationType.PAYMENT_REMINDER: 2,
            NotificationType.RSVP_REMINDER: 3,
            NotificationType.TASK_REMINDER: 4,
            NotificationType.CUSTOM: 5
        }
        
        return priority_map.get(notification_type, 5)
    
    def _is_quiet_hours(self, scheduled_time: datetime, preferences: Dict) -> bool:
        """Check if scheduled time falls within user's quiet hours."""
        quiet_start = preferences.get('quiet_hours_start', '22:00')
        quiet_end = preferences.get('quiet_hours_end', '08:00')
        
        if not quiet_start or not quiet_end:
            return False
        
        # Convert to time objects
        start_time = time.fromisoformat(quiet_start)
        end_time = time.fromisoformat(quiet_end)
        
        scheduled_time_only = scheduled_time.time()
        
        # Handle overnight quiet hours (e.g., 22:00 to 08:00)
        if start_time > end_time:
            return scheduled_time_only >= start_time or scheduled_time_only <= end_time
        else:
            return start_time <= scheduled_time_only <= end_time
    
    def _adjust_for_quiet_hours(self, scheduled_time: datetime, preferences: Dict) -> datetime:
        """Adjust scheduled time to avoid quiet hours."""
        quiet_end = preferences.get('quiet_hours_end', '08:00')
        
        if not quiet_end:
            return scheduled_time
        
        # Move to end of quiet hours
        end_time = time.fromisoformat(quiet_end)
        
        # Set to quiet hours end time on the same or next day
        adjusted = scheduled_time.replace(
            hour=end_time.hour,
            minute=end_time.minute,
            second=0,
            microsecond=0
        )
        
        # If the adjusted time is before the original, move to next day
        if adjusted <= scheduled_time:
            adjusted += timedelta(days=1)
        
        return adjusted
    
    async def _send_notification(self, notification) -> bool:
        """Send a notification based on its channel."""
        try:
            if notification.channel == NotificationChannel.EMAIL:
                return await self._send_email_notification(notification)
            elif notification.channel == NotificationChannel.SMS:
                return await self._send_sms_notification(notification)
            elif notification.channel == NotificationChannel.PUSH:
                return await self._send_push_notification(notification)
            elif notification.channel == NotificationChannel.IN_APP:
                return await self._send_in_app_notification(notification)
            else:
                return False
                
        except Exception as e:
            print(f"Error sending notification: {e}")
            return False
    
    async def _send_email_notification(self, notification) -> bool:
        """Send email notification."""
        try:
            # Get recipient user
            user = self.user_repo.get_by_id(notification.recipient_id)
            
            if not user or not user.email:
                return False
            
            # Send email
            success = await self.email_service.send_email(
                to_email=user.email,
                subject=notification.subject,
                body=notification.message,
                template_name='notification'
            )
            
            return success
            
        except Exception as e:
            print(f"Error sending email notification: {e}")
            return False
    
    async def _send_sms_notification(self, notification) -> bool:
        """Send SMS notification using Termii SMS service."""
        try:
            # Get recipient user
            recipient = self.user_repo.get_by_id(notification.recipient_id)
            if not recipient or not recipient.phone_number:
                return False
            
            # Check if SMS service is configured
            if not self.sms_service.is_configured():
                logger.warning("SMS service not configured, skipping SMS notification")
                return False
            
            # Send SMS
            result = self.sms_service.send_sms(
                to_phone=recipient.phone_number,
                message=f"{notification.subject}\n\n{notification.message}"
            )
            
            logger.info(f"SMS notification sent successfully: {result.get('sid')}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending SMS notification: {str(e)}")
            return False
    
    async def _send_push_notification(self, notification) -> bool:
        """Send push notification using Firebase Cloud Messaging."""
        try:
            # Get user's active devices
            user_devices = self.user_repo.get_by_id(notification.recipient_id)
            if not user_devices or not user_devices.devices:
                return False
            
            # Get active device tokens
            active_devices = [device for device in user_devices.devices if device.is_active]
            if not active_devices:
                return False
            
            device_tokens = [device.device_token for device in active_devices]
            
            # Prepare notification data
            data = {}
            if hasattr(notification, 'extra_data') and notification.extra_data:
                try:
                    import json
                    data = json.loads(notification.extra_data)
                except:
                    pass
            
            # Add event and notification IDs to data
            data.update({
                'event_id': str(notification.event_id),
                'notification_id': str(notification.id) if hasattr(notification, 'id') else None,
                'click_action': 'FLUTTER_NOTIFICATION_CLICK'  # For Flutter apps
            })
            
            # Send to multiple devices
            if len(device_tokens) == 1:
                # Single device
                platform = active_devices[0].platform if active_devices else None
                success = await push_service.send_notification(
                    device_token=device_tokens[0],
                    title=notification.subject or "New Notification",
                    body=notification.message,
                    data=data,
                    notification_type=notification.notification_type,
                    platform=platform
                )
                return success
            else:
                # Multiple devices
                result = await push_service.send_multicast_notification(
                    device_tokens=device_tokens,
                    title=notification.subject or "New Notification",
                    body=notification.message,
                    data=data,
                    notification_type=notification.notification_type
                )
                return result['success_count'] > 0
                
        except Exception as e:
            # Log error but don't raise to avoid breaking notification flow
            print(f"Error sending push notification: {str(e)}")
            return False
    
    async def _send_in_app_notification(self, notification) -> bool:
        """Send in-app notification via WebSocket and store for offline users."""
        try:
            # Get recipient user
            recipient = self.user_repo.get_by_id(notification.recipient_id)
            if not recipient:
                return False
            
            # Prepare notification payload
            notification_data = {
                'type': 'notification',
                'id': getattr(notification, 'id', None),
                'title': notification.subject,
                'message': notification.message,
                'notification_type': getattr(notification, 'notification_type', 'general'),
                'event_id': getattr(notification, 'event_id', None),
                'timestamp': datetime.utcnow().isoformat(),
                'priority': getattr(notification, 'priority', 5),
                'read': False
            }
            
            # Try to send via WebSocket to online users
            websocket_sent = await websocket_manager.send_user_notification(
                notification.recipient_id, 
                notification_data
            )
            
            # Always store notification for offline access and persistence
            # This ensures users can see notifications when they come back online
            stored = self._store_in_app_notification(notification, notification_data)
            
            # Consider it successful if either WebSocket sent OR stored successfully
            success = websocket_sent or stored
            
            if websocket_sent:
                logger.info(f"In-app notification sent via WebSocket to user {notification.recipient_id}")
            else:
                logger.info(f"User {notification.recipient_id} offline, notification stored for later retrieval")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending in-app notification: {str(e)}")
            return False
    
    def _store_in_app_notification(self, notification, notification_data: dict) -> bool:
        """Store in-app notification in database for offline users."""
        try:
            # Create notification log entry
            self._log_notification(notification, NotificationStatus.SENT)
            
            # You might want to create a separate in_app_notifications table
            # For now, we'll use the existing notification logging system
            return True
            
        except Exception as e:
            logger.error(f"Error storing in-app notification: {str(e)}")
            return False
    
    def _log_notification(self, notification, status: NotificationStatus):
        """Log notification delivery."""
        log_data = {
            'reminder_id': notification.reminder_id,
            'event_id': notification.event_id,
            'recipient_id': notification.recipient_id,
            'notification_type': notification.notification_type,
            'channel': notification.channel,
            'subject': notification.subject,
            'message': notification.message,
            'status': status,
            'sent_at': datetime.utcnow() if status == NotificationStatus.SENT else None,
            'error_message': notification.error_message if status == NotificationStatus.FAILED else None
        }
        
        self.notification_repo.create_notification_log(log_data)
    
    def _create_rsvp_reminder(self, event):
        """Create automatic RSVP reminder."""
        # Only create if event is more than 7 days away
        days_until_event = (event.start_datetime - datetime.utcnow()).days
        
        if days_until_event < 7:
            return None
        
        # Schedule for 7 days before event
        scheduled_time = event.start_datetime - timedelta(days=7)
        
        reminder_data = {
            'title': f'RSVP Reminder - {event.title}',
            'message': f'Please RSVP for {event.title} scheduled for {event.start_datetime.strftime("%B %d, %Y")}.',
            'notification_type': NotificationType.RSVP_REMINDER,
            'scheduled_time': scheduled_time,
            'frequency': ReminderFrequency.ONCE,
            'event_id': event.id,
            'creator_id': event.creator_id,
            'target_all_guests': True,
            'send_email': True,
            'send_push': True,
            'send_in_app': True
        }
        
        reminder = self.notification_repo.create_reminder(reminder_data)
        self._queue_reminder_notifications(reminder)
        
        return reminder
    
    def _create_event_reminders(self, event):
        """Create automatic event reminders at 1 month, 1 week, 1 day, and day-of."""
        now = datetime.utcnow()
        offsets = [
            (timedelta(days=30), "1 month"),
            (timedelta(days=7), "1 week"),
            (timedelta(days=1), "1 day"),
            (timedelta(hours=0), "today")
        ]
        created_reminders = []
        
        for offset, label in offsets:
            scheduled_time = event.start_datetime - offset
            
            # Skip if this reminder would occur in the past
            if scheduled_time <= now:
                continue
            
            # Build label-specific messaging
            if label == "today":
                title = f'Event Reminder (Today) - {event.title}'
                message = f"{event.title} is today at {event.start_datetime.strftime('%I:%M %p')}."
            elif label == "1 day":
                title = f'Event Reminder (Tomorrow) - {event.title}'
                message = f"Reminder: {event.title} is tomorrow at {event.start_datetime.strftime('%I:%M %p')}."
            else:
                title = f'Event Reminder ({label}) - {event.title}'
                message = (
                    f"Reminder: {event.title} is in {label} on "
                    f"{event.start_datetime.strftime('%B %d, %Y at %I:%M %p')}.")
            
            reminder_data = {
                'title': title,
                'message': message,
                'notification_type': NotificationType.EVENT_REMINDER,
                'scheduled_time': scheduled_time,
                'frequency': ReminderFrequency.ONCE,
                'event_id': event.id,
                'creator_id': event.creator_id,
                'target_all_guests': True,
                'send_email': True,
                'send_push': True,
                'send_in_app': True
            }
            
            reminder = self.notification_repo.create_reminder(reminder_data)
            self._queue_reminder_notifications(reminder)
            created_reminders.append(reminder)
        
        return created_reminders
    
    def _create_dress_code_reminder(self, event):
        """Create dress code reminder if event has dress code."""
        # Check if event has dress code information
        if not hasattr(event, 'dress_code') or not event.dress_code:
            return None
        
        # Only create if event is more than 3 days away
        days_until_event = (event.start_datetime - datetime.utcnow()).days
        
        if days_until_event < 3:
            return None
        
        # Schedule for 3 days before event
        scheduled_time = event.start_datetime - timedelta(days=3)
        
        reminder_data = {
            'title': f'Dress Code Reminder - {event.title}',
            'message': f'Reminder: The dress code for {event.title} is {event.dress_code}.',
            'notification_type': NotificationType.CUSTOM,
            'scheduled_time': scheduled_time,
            'frequency': ReminderFrequency.ONCE,
            'event_id': event.id,
            'creator_id': event.creator_id,
            'target_all_guests': True,
            'send_email': True,
            'send_push': True
        }
        
        reminder = self.notification_repo.create_reminder(reminder_data)
        self._queue_reminder_notifications(reminder)
        
        return reminder