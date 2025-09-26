import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.services.notification_service import NotificationService
from app.models.notification_models import (
    SmartReminder, NotificationLog, NotificationPreference, ReminderTemplate,
    AutomationRule, NotificationQueue, NotificationType, NotificationStatus,
    NotificationChannel, ReminderFrequency
)
from app.models.user_models import User
from app.models.event_models import Event, EventInvitation
from app.models.shared_models import RSVPStatus
from app.core.errors import NotFoundError, ValidationError, AuthorizationError

class TestNotificationService:
    """Test cases for NotificationService."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def notification_service(self, mock_db):
        """Create NotificationService instance with mocked database."""
        return NotificationService(mock_db)
    
    @pytest.fixture
    def mock_user(self):
        """Mock user for testing."""
        user = Mock(spec=User)
        user.id = 1
        user.full_name = "Test User"
        user.email = "test@example.com"
        return user
    
    @pytest.fixture
    def mock_event(self):
        """Mock event for testing."""
        event = Mock(spec=Event)
        event.id = 1
        event.title = "Test Event"
        event.creator_id = 1
        event.start_datetime = datetime.utcnow() + timedelta(days=7)
        event.collaborators = []
        event.invitations = []
        return event
    
    @pytest.fixture
    def mock_reminder(self):
        """Mock smart reminder for testing."""
        reminder = Mock(spec=SmartReminder)
        reminder.id = 1
        reminder.title = "Test Reminder"
        reminder.message = "Test reminder message"
        reminder.notification_type = NotificationType.RSVP_REMINDER
        reminder.scheduled_time = datetime.utcnow() + timedelta(hours=1)
        reminder.event_id = 1
        reminder.creator_id = 1
        reminder.status = NotificationStatus.PENDING
        reminder.is_active = True
        reminder.target_all_guests = True
        reminder.target_specific_users = None
        reminder.target_rsvp_status = None
        reminder.send_email = True
        reminder.send_sms = False
        reminder.send_push = True
        reminder.send_in_app = True
        return reminder
    
    @pytest.fixture
    def mock_notification_log(self):
        """Mock notification log for testing."""
        log = Mock(spec=NotificationLog)
        log.id = 1
        log.notification_type = NotificationType.RSVP_REMINDER
        log.channel = NotificationChannel.EMAIL
        log.subject = "RSVP Reminder"
        log.message = "Please RSVP for the event"
        log.status = NotificationStatus.SENT
        log.sent_at = datetime.utcnow()
        log.event_id = 1
        log.recipient_id = 1
        return log
    
    # Smart Reminder CRUD tests
    def test_create_reminder_success(self, notification_service, mock_db, mock_event):
        """Test successful reminder creation."""
        # Setup
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_event
        
        with patch.object(notification_service, '_queue_reminder_notifications'):
            mock_db.add = Mock()
            mock_db.commit = Mock()
            mock_db.refresh = Mock()
            
            reminder_data = {
                "title": "Test Reminder",
                "message": "Test reminder message",
                "notification_type": "rsvp_reminder",
                "scheduled_time": datetime.utcnow() + timedelta(hours=1),
                "frequency": "once",
                "target_all_guests": True,
                "send_email": True,
                "send_push": True
            }
            
            # Execute
            result = notification_service.create_reminder(1, 1, reminder_data)
            
            # Assert
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()
            assert result is not None
    
    def test_create_reminder_event_not_found(self, notification_service, mock_db):
        """Test reminder creation with non-existent event."""
        # Setup
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = None
        
        reminder_data = {
            "title": "Test Reminder",
            "message": "Test message",
            "notification_type": "rsvp_reminder",
            "scheduled_time": datetime.utcnow() + timedelta(hours=1)
        }
        
        # Execute & Assert
        with pytest.raises(NotFoundError, match="Event not found"):
            notification_service.create_reminder(999, 1, reminder_data)
    
    def test_get_event_reminders_success(self, notification_service, mock_db, mock_event):
        """Test successful event reminders retrieval."""
        # Setup
        mock_reminders = [Mock(spec=SmartReminder) for _ in range(3)]
        
        with patch.object(notification_service, '_get_event_with_access', return_value=mock_event):
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.all.return_value = mock_reminders
            
            mock_db.query.return_value.options.return_value = mock_query
            
            # Execute
            result = notification_service.get_event_reminders(1, 1)
            
            # Assert
            assert len(result) == 3
    
    def test_update_reminder_success(self, notification_service, mock_db, mock_reminder, mock_event):
        """Test successful reminder update."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_reminder
        
        with patch.object(notification_service, '_get_event_with_access', return_value=mock_event):
            with patch.object(notification_service, '_requeue_reminder_notifications'):
                mock_db.commit = Mock()
                mock_db.refresh = Mock()
                
                update_data = {
                    "title": "Updated Reminder",
                    "scheduled_time": datetime.utcnow() + timedelta(hours=2)
                }
                
                # Execute
                result = notification_service.update_reminder(1, 1, update_data)
                
                # Assert
                mock_db.commit.assert_called_once()
                mock_db.refresh.assert_called_once()
                assert result == mock_reminder
    
    def test_update_reminder_permission_denied(self, notification_service, mock_db, mock_reminder, mock_event):
        """Test reminder update with permission denied."""
        # Setup
        mock_reminder.creator_id = 2  # Different user
        mock_event.creator_id = 3  # Different event creator
        mock_db.query.return_value.filter.return_value.first.return_value = mock_reminder
        
        with patch.object(notification_service, '_get_event_with_access', return_value=mock_event):
            update_data = {"title": "Updated Reminder"}
            
            # Execute & Assert
            with pytest.raises(AuthorizationError, match="You don't have permission to edit this reminder"):
                notification_service.update_reminder(1, 1, update_data)
    
    def test_delete_reminder_success(self, notification_service, mock_db, mock_reminder, mock_event):
        """Test successful reminder deletion."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_reminder
        
        with patch.object(notification_service, '_get_event_with_access', return_value=mock_event):
            # Mock queue update
            mock_queue_query = Mock()
            mock_queue_query.filter.return_value.update.return_value = None
            mock_db.query.side_effect = [Mock(), mock_queue_query]
            
            mock_db.commit = Mock()
            
            # Execute
            result = notification_service.delete_reminder(1, 1)
            
            # Assert
            assert result is True
            assert mock_reminder.is_active is False
            mock_db.commit.assert_called_once()
    
    # Automatic reminder creation tests
    def test_create_automatic_reminders_success(self, notification_service, mock_db, mock_event):
        """Test successful automatic reminders creation."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_event
        
        with patch.object(notification_service, '_create_rsvp_reminder') as mock_rsvp:
            with patch.object(notification_service, '_create_event_reminder') as mock_event_rem:
                with patch.object(notification_service, '_create_dress_code_reminder') as mock_dress:
                    mock_rsvp.return_value = Mock(spec=SmartReminder)
                    mock_event_rem.return_value = Mock(spec=SmartReminder)
                    mock_dress.return_value = None  # No dress code
                    
                    # Execute
                    result = notification_service.create_automatic_reminders(1)
                    
                    # Assert
                    assert len(result) == 2  # RSVP and event reminders
                    mock_rsvp.assert_called_once_with(mock_event)
                    mock_event_rem.assert_called_once_with(mock_event)
    
    # Notification processing tests
    @pytest.mark.asyncio
    async def test_process_pending_notifications_success(self, notification_service, mock_db):
        """Test successful notification processing."""
        # Setup
        mock_notifications = [Mock(spec=NotificationQueue) for _ in range(3)]
        for i, notif in enumerate(mock_notifications):
            notif.id = i + 1
            notif.status = "queued"
            notif.attempts = 0
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_notifications
        
        mock_db.query.return_value = mock_query
        mock_db.commit = Mock()
        
        with patch.object(notification_service, '_send_notification', new_callable=AsyncMock) as mock_send:
            with patch.object(notification_service, '_log_notification'):
                mock_send.return_value = True
                
                # Execute
                result = await notification_service.process_pending_notifications()
                
                # Assert
                assert result == 3
                assert mock_send.call_count == 3
    
    # Notification preferences tests
    def test_get_user_preferences_success(self, notification_service, mock_db):
        """Test successful user preferences retrieval."""
        # Setup
        mock_preferences = [Mock(spec=NotificationPreference) for _ in range(5)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_preferences
        
        # Execute
        result = notification_service.get_user_preferences(1)
        
        # Assert
        assert len(result) == 5
    
    def test_update_user_preferences_success(self, notification_service, mock_db):
        """Test successful user preferences update."""
        # Setup
        mock_db.query.return_value.filter.return_value.delete.return_value = None
        mock_db.add = Mock()
        mock_db.commit = Mock()
        
        preferences = [
            {
                "notification_type": "rsvp_reminder",
                "email_enabled": True,
                "sms_enabled": False,
                "push_enabled": True,
                "advance_notice_hours": 24
            },
            {
                "notification_type": "event_reminder",
                "email_enabled": True,
                "sms_enabled": True,
                "push_enabled": True,
                "advance_notice_hours": 2
            }
        ]
        
        # Execute
        result = notification_service.update_user_preferences(1, preferences)
        
        # Assert
        assert mock_db.add.call_count == 2
        mock_db.commit.assert_called_once()
        assert len(result) == 2
    
    # Template management tests
    def test_create_reminder_template_success(self, notification_service, mock_db):
        """Test successful reminder template creation."""
        # Setup
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        template_data = {
            "name": "RSVP Reminder Template",
            "description": "Standard RSVP reminder",
            "notification_type": "rsvp_reminder",
            "subject_template": "RSVP Reminder for {event_title}",
            "message_template": "Please RSVP for {event_title} by {rsvp_deadline}",
            "template_variables": ["event_title", "rsvp_deadline"]
        }
        
        # Execute
        result = notification_service.create_reminder_template(1, template_data)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result is not None
    
    def test_get_reminder_templates_success(self, notification_service, mock_db):
        """Test successful reminder templates retrieval."""
        # Setup
        mock_templates = [Mock(spec=ReminderTemplate) for _ in range(3)]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = mock_templates
        
        mock_db.query.return_value = mock_query
        
        # Execute
        result = notification_service.get_reminder_templates(1, NotificationType.RSVP_REMINDER)
        
        # Assert
        assert len(result) == 3
    
    # Analytics and reporting tests
    def test_get_notification_analytics_success(self, notification_service, mock_db):
        """Test successful notification analytics retrieval."""
        # Setup
        mock_logs = []
        for i in range(10):
            log = Mock(spec=NotificationLog)
            log.notification_type = NotificationType.RSVP_REMINDER if i < 5 else NotificationType.EVENT_REMINDER
            log.channel = NotificationChannel.EMAIL if i < 7 else NotificationChannel.PUSH
            log.status = NotificationStatus.SENT if i < 8 else NotificationStatus.FAILED
            mock_logs.append(log)
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_logs
        
        mock_db.query.return_value = mock_query
        
        # Execute
        result = notification_service.get_notification_analytics(event_id=1, user_id=1, days=30)
        
        # Assert
        assert result["total_sent"] == 10
        assert result["delivery_rate"] == 80.0  # 8 sent out of 10
        assert result["by_type"]["rsvp_reminder"] == 5
        assert result["by_type"]["event_reminder"] == 5
        assert result["by_channel"]["email"] == 7
        assert result["by_channel"]["push"] == 3
        assert result["by_status"]["sent"] == 8
        assert result["by_status"]["failed"] == 2
    
    # Helper method tests
    def test_get_event_with_access_success(self, notification_service, mock_db, mock_event):
        """Test successful event access check."""
        # Setup
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_event
        
        # Execute
        result = notification_service._get_event_with_access(1, 1)
        
        # Assert
        assert result == mock_event
    
    def test_get_event_with_access_not_found(self, notification_service, mock_db):
        """Test event access check with non-existent event."""
        # Setup
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = None
        
        # Execute & Assert
        with pytest.raises(NotFoundError, match="Event not found"):
            notification_service._get_event_with_access(999, 1)
    
    def test_get_event_with_access_denied(self, notification_service, mock_db, mock_event):
        """Test event access check with access denied."""
        # Setup
        mock_event.creator_id = 2  # Different user
        mock_event.collaborators = []
        
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_event
        
        # Mock invitation query to return None (no invitation)
        mock_invitation_query = Mock()
        mock_invitation_query.filter.return_value.first.return_value = None
        mock_db.query.side_effect = [Mock().options.return_value, mock_invitation_query]
        
        # Execute & Assert
        with pytest.raises(AuthorizationError, match="You don't have access to this event"):
            notification_service._get_event_with_access(1, 1)
    
    def test_queue_reminder_notifications_success(self, notification_service, mock_db, mock_reminder):
        """Test successful reminder notifications queueing."""
        # Setup
        mock_users = [Mock(spec=User) for _ in range(3)]
        for i, user in enumerate(mock_users):
            user.id = i + 1
        
        with patch.object(notification_service, '_get_reminder_targets', return_value=mock_users):
            with patch.object(notification_service, '_get_user_notification_preferences') as mock_prefs:
                with patch.object(notification_service, '_queue_notification') as mock_queue:
                    mock_prefs.return_value = {
                        'email_enabled': True,
                        'sms_enabled': False,
                        'push_enabled': True,
                        'in_app_enabled': True
                    }
                    
                    # Execute
                    notification_service._queue_reminder_notifications(mock_reminder)
                    
                    # Assert
                    # Should queue 3 channels (email, push, in_app) for 3 users = 9 notifications
                    assert mock_queue.call_count == 9
    
    def test_get_reminder_targets_all_guests(self, notification_service, mock_db, mock_reminder):
        """Test getting reminder targets for all guests."""
        # Setup
        mock_reminder.target_all_guests = True
        mock_reminder.target_rsvp_status = None
        
        mock_invitations = [Mock(spec=EventInvitation) for _ in range(5)]
        for i, inv in enumerate(mock_invitations):
            inv.user_id = i + 1
        
        mock_users = [Mock(spec=User) for _ in range(5)]
        
        mock_db.query.return_value.filter.return_value.all.return_value = mock_invitations
        mock_db.query.return_value.filter.return_value.all.return_value = mock_users
        
        # Execute
        result = notification_service._get_reminder_targets(mock_reminder)
        
        # Assert
        assert len(result) == 5
    
    def test_get_reminder_targets_specific_users(self, notification_service, mock_db, mock_reminder):
        """Test getting reminder targets for specific users."""
        # Setup
        mock_reminder.target_all_guests = False
        mock_reminder.target_user_ids = [1, 2, 3]
        
        mock_users = [Mock(spec=User) for _ in range(3)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_users
        
        # Execute
        result = notification_service._get_reminder_targets(mock_reminder)
        
        # Assert
        assert len(result) == 3
    
    def test_get_user_notification_preferences_with_record(self, notification_service, mock_db):
        """Test getting user notification preferences with existing record."""
        # Setup
        mock_preference = Mock(spec=NotificationPreference)
        mock_preference.email_enabled = True
        mock_preference.sms_enabled = False
        mock_preference.push_enabled = True
        mock_preference.in_app_enabled = True
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_preference
        
        # Execute
        result = notification_service._get_user_notification_preferences(1, NotificationType.RSVP_REMINDER)
        
        # Assert
        assert result['email_enabled'] is True
        assert result['sms_enabled'] is False
        assert result['push_enabled'] is True
        assert result['in_app_enabled'] is True
    
    def test_get_user_notification_preferences_default(self, notification_service, mock_db):
        """Test getting user notification preferences with default values."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Execute
        result = notification_service._get_user_notification_preferences(1, NotificationType.RSVP_REMINDER)
        
        # Assert
        assert result['email_enabled'] is True
        assert result['sms_enabled'] is False
        assert result['push_enabled'] is True
        assert result['in_app_enabled'] is True
    
    def test_get_notification_priority(self, notification_service):
        """Test notification priority assignment."""
        # Execute & Assert
        assert notification_service._get_notification_priority(NotificationType.EVENT_REMINDER) == 1
        assert notification_service._get_notification_priority(NotificationType.PAYMENT_REMINDER) == 2
        assert notification_service._get_notification_priority(NotificationType.RSVP_REMINDER) == 3
        assert notification_service._get_notification_priority(NotificationType.CUSTOM) == 5
    
    @pytest.mark.asyncio
    async def test_send_email_notification_success(self, notification_service, mock_db):
        """Test successful email notification sending."""
        # Setup
        mock_notification = Mock(spec=NotificationQueue)
        mock_notification.recipient_id = 1
        mock_notification.subject = "Test Subject"
        mock_notification.message = "Test message"
        
        mock_user = Mock(spec=User)
        mock_user.email = "test@example.com"
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        with patch.object(notification_service.email_service, 'send_email', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            # Execute
            result = await notification_service._send_email_notification(mock_notification)
            
            # Assert
            assert result is True
            mock_send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_sms_notification_placeholder(self, notification_service):
        """Test SMS notification sending (placeholder implementation)."""
        # Setup
        mock_notification = Mock(spec=NotificationQueue)
        
        # Execute
        result = await notification_service._send_sms_notification(mock_notification)
        
        # Assert
        assert result is True  # Placeholder always returns True
    
    def test_log_notification_success(self, notification_service, mock_db):
        """Test successful notification logging."""
        # Setup
        mock_notification = Mock(spec=NotificationQueue)
        mock_notification.reminder_id = 1
        mock_notification.event_id = 1
        mock_notification.recipient_id = 1
        mock_notification.notification_type = NotificationType.RSVP_REMINDER
        mock_notification.channel = NotificationChannel.EMAIL
        mock_notification.subject = "Test Subject"
        mock_notification.message = "Test message"
        mock_notification.error_message = None
        
        mock_db.add = Mock()
        mock_db.commit = Mock()
        
        # Execute
        notification_service._log_notification(mock_notification, NotificationStatus.SENT)
        
        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    def test_create_rsvp_reminder_success(self, notification_service, mock_db, mock_event):
        """Test successful RSVP reminder creation."""
        # Setup
        mock_event.start_datetime = datetime.utcnow() + timedelta(days=10)  # Far enough in future
        
        with patch.object(notification_service, '_queue_reminder_notifications'):
            mock_db.add = Mock()
            mock_db.commit = Mock()
            mock_db.refresh = Mock()
            
            # Execute
            result = notification_service._create_rsvp_reminder(mock_event)
            
            # Assert
            assert result is not None
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()
    
    def test_create_rsvp_reminder_too_late(self, notification_service, mock_event):
        """Test RSVP reminder creation when it's too late."""
        # Setup
        mock_event.start_datetime = datetime.utcnow() + timedelta(days=3)  # Less than 7 days
        
        # Execute
        result = notification_service._create_rsvp_reminder(mock_event)
        
        # Assert
        assert result is None
    
    def test_create_event_reminder_success(self, notification_service, mock_db, mock_event):
        """Test successful event reminder creation."""
        # Setup
        mock_event.start_datetime = datetime.utcnow() + timedelta(days=5)  # Far enough in future
        
        with patch.object(notification_service, '_queue_reminder_notifications'):
            mock_db.add = Mock()
            mock_db.commit = Mock()
            mock_db.refresh = Mock()
            
            # Execute
            result = notification_service._create_event_reminder(mock_event)
            
            # Assert
            assert result is not None
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()
    
    def test_requeue_reminder_notifications_success(self, notification_service, mock_db, mock_reminder):
        """Test successful reminder notifications re-queueing."""
        # Setup
        mock_queue_query = Mock()
        mock_queue_query.filter.return_value.update.return_value = None
        mock_db.query.return_value = mock_queue_query
        
        with patch.object(notification_service, '_queue_reminder_notifications'):
            # Execute
            notification_service._requeue_reminder_notifications(mock_reminder)
            
            # Assert - should cancel existing and queue new
            mock_queue_query.filter.return_value.update.assert_called_once()
    
    # Integration-style tests
    def test_notification_workflow_integration(self, notification_service, mock_db, mock_event):
        """Test complete notification workflow integration."""
        # Setup mocks for the entire workflow
        mock_reminder = Mock(spec=SmartReminder)
        mock_reminder.id = 1
        mock_reminder.creator_id = 1
        
        mock_template = Mock(spec=ReminderTemplate)
        mock_template.id = 1
        
        # Mock database interactions
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = mock_event
        
        with patch.object(notification_service, '_queue_reminder_notifications'):
            mock_db.add = Mock()
            mock_db.commit = Mock()
            mock_db.refresh = Mock()
            
            # Execute workflow
            # 1. Create reminder template
            template_data = {
                "name": "Test Template",
                "notification_type": "rsvp_reminder",
                "subject_template": "RSVP for {event_title}",
                "message_template": "Please RSVP for {event_title}"
            }
            template = notification_service.create_reminder_template(1, template_data)
            
            # 2. Create reminder
            reminder_data = {
                "title": "Test Reminder",
                "message": "Test message",
                "notification_type": "rsvp_reminder",
                "scheduled_time": datetime.utcnow() + timedelta(hours=1),
                "target_all_guests": True
            }
            reminder = notification_service.create_reminder(1, 1, reminder_data)
            
            # 3. Update user preferences
            preferences = [{
                "notification_type": "rsvp_reminder",
                "email_enabled": True,
                "push_enabled": True
            }]
            prefs = notification_service.update_user_preferences(1, preferences)
            
            # Assert all operations succeeded
            assert mock_db.add.call_count >= 3  # template, reminder, preferences
            assert mock_db.commit.call_count >= 3
            assert template is not None
            assert reminder is not None
            assert len(prefs) == 1