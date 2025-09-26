import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.email_service import EmailService, email_service
from app.models.user_models import User
from app.models.event_models import Event, EventInvitation
from app.tests.conftest import UserFactory, EventFactory
from datetime import datetime, timedelta

class TestEmailService:
    """Test cases for EmailService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.email_service = EmailService()
        self.mock_user = Mock(spec=User)
        self.mock_user.id = 1
        self.mock_user.email = "test@example.com"
        self.mock_user.full_name = "Test User"
        self.mock_user.username = "testuser"
    
    @pytest.mark.asyncio
    @patch('resend.Emails.send')
    async def test_send_email_success(self, mock_resend_send):
        """Test successful email sending."""
        mock_resend_send.return_value = {"id": "email_123"}
        
        result = await self.email_service.send_email(
            to_email="test@example.com",
            subject="Test Subject",
            html_content="<h1>Test Content</h1>"
        )
        
        assert result is True
        mock_resend_send.assert_called_once()
        call_args = mock_resend_send.call_args[0][0]
        assert call_args["to"] == ["test@example.com"]
        assert call_args["subject"] == "Test Subject"
        assert call_args["html"] == "<h1>Test Content</h1>"
    
    @pytest.mark.asyncio
    @patch('resend.Emails.send')
    async def test_send_email_failure(self, mock_resend_send):
        """Test email sending failure."""
        mock_resend_send.side_effect = Exception("API Error")
        
        result = await self.email_service.send_email(
            to_email="test@example.com",
            subject="Test Subject",
            html_content="<h1>Test Content</h1>"
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    @patch('resend.Emails.send')
    async def test_send_bulk_email(self, mock_resend_send):
        """Test bulk email sending."""
        mock_resend_send.return_value = {"id": "email_123"}
        
        recipients = ["user1@example.com", "user2@example.com", "user3@example.com"]
        results = await self.email_service.send_bulk_email(
            recipients=recipients,
            subject="Bulk Test",
            html_content="<h1>Bulk Content</h1>"
        )
        
        assert len(results) == 3
        assert all(results.values())
        assert mock_resend_send.call_count == 3
    
    @patch('app.services.email_service.env.get_template')
    def test_render_template_success(self, mock_get_template):
        """Test successful template rendering."""
        mock_template = Mock()
        mock_template.render.return_value = "<h1>Hello Test User</h1>"
        mock_get_template.return_value = mock_template
        
        result = self.email_service.render_template(
            "welcome.html",
            {"user_name": "Test User"}
        )
        
        assert result == "<h1>Hello Test User</h1>"
        mock_get_template.assert_called_once_with("welcome.html")
        mock_template.render.assert_called_once_with(user_name="Test User")
    
    @patch('app.services.email_service.env.get_template')
    def test_render_template_failure(self, mock_get_template):
        """Test template rendering failure."""
        mock_get_template.side_effect = Exception("Template not found")
        
        result = self.email_service.render_template(
            "nonexistent.html",
            {"user_name": "Test User"}
        )
        
        assert result == ""
    
    @pytest.mark.asyncio
    @patch.object(EmailService, 'send_email')
    @patch.object(EmailService, 'render_template')
    async def test_send_welcome_email(self, mock_render, mock_send):
        """Test welcome email sending."""
        mock_render.return_value = "<h1>Welcome Test User</h1>"
        mock_send.return_value = True
        
        result = await self.email_service.send_welcome_email(self.mock_user)
        
        assert result is True
        mock_render.assert_called_once_with("welcome.html", {
            "user_name": "Test User",
            "user_email": "test@example.com",
            "app_name": "Plan et al",
            "login_url": "http://localhost:3000/login"
        })
        mock_send.assert_called_once()
    
    @pytest.mark.asyncio
    @patch.object(EmailService, 'send_email')
    @patch.object(EmailService, 'render_template')
    async def test_send_verification_otp(self, mock_render, mock_send):
        """Test OTP verification email sending."""
        mock_render.return_value = "<h1>Your OTP: 123456</h1>"
        mock_send.return_value = True
        
        result = await self.email_service.send_verification_otp(self.mock_user, "123456")
        
        assert result is True
        mock_render.assert_called_once_with("verification_otp.html", {
            "user_name": "Test User",
            "otp_code": "123456",
            "app_name": "Plan et al",
            "expires_in": "10 minutes"
        })
        mock_send.assert_called_once_with(
            to_email="test@example.com",
            subject="Your Plan et al verification code",
            html_content="<h1>Your OTP: 123456</h1>"
        )
    
    @pytest.mark.asyncio
    @patch.object(EmailService, 'send_email')
    @patch.object(EmailService, 'render_template')
    async def test_send_password_reset_otp(self, mock_render, mock_send):
        """Test password reset OTP email sending."""
        mock_render.return_value = "<h1>Reset OTP: 654321</h1>"
        mock_send.return_value = True
        
        result = await self.email_service.send_password_reset_otp(self.mock_user, "654321")
        
        assert result is True
        mock_render.assert_called_once_with("password_reset_otp.html", {
            "user_name": "Test User",
            "otp_code": "654321",
            "app_name": "Plan et al",
            "expires_in": "10 minutes"
        })
        mock_send.assert_called_once_with(
            to_email="test@example.com",
            subject="Your Plan et al password reset code",
            html_content="<h1>Reset OTP: 654321</h1>"
        )
    
    @pytest.mark.asyncio
    @patch.object(EmailService, 'send_email')
    @patch.object(EmailService, 'render_template')
    async def test_send_event_invitation(self, mock_render, mock_send):
        """Test event invitation email sending."""
        mock_render.return_value = "<h1>You're invited!</h1>"
        mock_send.return_value = True
        
        # Create mock event and invitation
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.title = "Test Event"
        mock_event.description = "Test Description"
        mock_event.start_datetime = datetime.utcnow() + timedelta(days=7)
        mock_event.venue_name = "Test Venue"
        mock_event.venue_address = "123 Test St"
        
        mock_invitation = Mock(spec=EventInvitation)
        mock_invitation.id = 1
        mock_invitation.invitation_message = "Please join us!"
        mock_invitation.plus_one_allowed = True
        
        mock_inviter = Mock(spec=User)
        mock_inviter.email = "inviter@example.com"
        mock_inviter.full_name = "Event Organizer"
        
        result = await self.email_service.send_event_invitation(
            mock_event, mock_invitation, self.mock_user, mock_inviter
        )
        
        assert result is True
        mock_render.assert_called_once()
        mock_send.assert_called_once()
        
        # Check that reply_to is set to inviter's email
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["reply_to"] == "inviter@example.com"
    
    @pytest.mark.asyncio
    @patch.object(EmailService, 'send_email')
    @patch.object(EmailService, 'render_template')
    async def test_send_rsvp_confirmation(self, mock_render, mock_send):
        """Test RSVP confirmation email sending."""
        mock_render.return_value = "<h1>RSVP Confirmed</h1>"
        mock_send.return_value = True
        
        # Create mock event and invitation
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.title = "Test Event"
        mock_event.start_datetime = datetime.utcnow() + timedelta(days=7)
        mock_event.venue_name = "Test Venue"
        
        mock_invitation = Mock(spec=EventInvitation)
        mock_invitation.rsvp_status = "accepted"
        mock_invitation.response_message = "Looking forward to it!"
        mock_invitation.plus_one_name = "Guest Name"
        mock_invitation.dietary_restrictions = "Vegetarian"
        
        result = await self.email_service.send_rsvp_confirmation(
            mock_event, mock_invitation, self.mock_user
        )
        
        assert result is True
        mock_render.assert_called_once()
        mock_send.assert_called_once_with(
            to_email="test@example.com",
            subject="RSVP confirmed for Test Event",
            html_content="<h1>RSVP Confirmed</h1>"
        )
    
    @pytest.mark.asyncio
    @patch.object(EmailService, 'send_email')
    @patch.object(EmailService, 'render_template')
    async def test_send_event_reminder(self, mock_render, mock_send):
        """Test event reminder email sending."""
        mock_render.return_value = "<h1>Event Reminder</h1>"
        mock_send.return_value = True
        
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.title = "Test Event"
        mock_event.start_datetime = datetime.utcnow() + timedelta(hours=24)
        mock_event.venue_name = "Test Venue"
        mock_event.venue_address = "123 Test St"
        
        result = await self.email_service.send_event_reminder(
            mock_event, self.mock_user, "24h"
        )
        
        assert result is True
        mock_render.assert_called_once()
        mock_send.assert_called_once_with(
            to_email="test@example.com",
            subject="Reminder: Test Event",
            html_content="<h1>Event Reminder</h1>"
        )
    
    @pytest.mark.asyncio
    @patch.object(EmailService, 'send_email')
    @patch.object(EmailService, 'render_template')
    async def test_send_task_assignment(self, mock_render, mock_send):
        """Test task assignment email sending."""
        mock_render.return_value = "<h1>New Task Assigned</h1>"
        mock_send.return_value = True
        
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.title = "Test Event"
        
        mock_assigner = Mock(spec=User)
        mock_assigner.email = "assigner@example.com"
        mock_assigner.full_name = "Task Assigner"
        
        due_date = datetime.utcnow() + timedelta(days=3)
        
        result = await self.email_service.send_task_assignment(
            mock_event, "Buy decorations", self.mock_user, mock_assigner, due_date
        )
        
        assert result is True
        mock_render.assert_called_once()
        mock_send.assert_called_once()
        
        # Check that reply_to is set to assigner's email
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["reply_to"] == "assigner@example.com"
    
    @pytest.mark.asyncio
    @patch.object(EmailService, 'send_email')
    @patch.object(EmailService, 'render_template')
    async def test_send_expense_split_notification(self, mock_render, mock_send):
        """Test expense split notification email sending."""
        mock_render.return_value = "<h1>Expense Split</h1>"
        mock_send.return_value = True
        
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.title = "Test Event"
        
        mock_paid_by = Mock(spec=User)
        mock_paid_by.email = "payer@example.com"
        mock_paid_by.full_name = "Bill Payer"
        
        result = await self.email_service.send_expense_split_notification(
            mock_event, "Venue Rental", 50.0, "USD", self.mock_user, mock_paid_by
        )
        
        assert result is True
        mock_render.assert_called_once()
        mock_send.assert_called_once()
        
        # Check that reply_to is set to payer's email
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["reply_to"] == "payer@example.com"
    
    @pytest.mark.asyncio
    @patch.object(EmailService, 'send_email')
    @patch.object(EmailService, 'render_template')
    async def test_send_friend_request_notification(self, mock_render, mock_send):
        """Test friend request notification email sending."""
        mock_render.return_value = "<h1>Friend Request</h1>"
        mock_send.return_value = True
        
        mock_requester = Mock(spec=User)
        mock_requester.id = 2
        mock_requester.full_name = "Friend Requester"
        mock_requester.username = "friendrequester"
        
        result = await self.email_service.send_friend_request_notification(
            self.mock_user, mock_requester
        )
        
        assert result is True
        mock_render.assert_called_once()
        mock_send.assert_called_once_with(
            to_email="test@example.com",
            subject="Friend Requester wants to be friends!",
            html_content="<h1>Friend Request</h1>"
        )
    
    @pytest.mark.asyncio
    @patch.object(EmailService, 'send_email')
    @patch.object(EmailService, 'render_template')
    async def test_send_weekly_digest(self, mock_render, mock_send):
        """Test weekly digest email sending."""
        mock_render.return_value = "<h1>Weekly Digest</h1>"
        mock_send.return_value = True
        
        upcoming_events = []
        pending_tasks = []
        pending_rsvps = []
        
        result = await self.email_service.send_weekly_digest(
            self.mock_user, upcoming_events, pending_tasks, pending_rsvps
        )
        
        assert result is True
        mock_render.assert_called_once()
        mock_send.assert_called_once_with(
            to_email="test@example.com",
            subject="Your Plan et al weekly digest",
            html_content="<h1>Weekly Digest</h1>"
        )
    
    def test_email_service_singleton(self):
        """Test that email_service is properly instantiated."""
        assert email_service is not None
        assert isinstance(email_service, EmailService)
        assert email_service.from_email == "noreply@planetal.com"
        assert email_service.from_name == "Plan et al"
from unittest.mock import Mock, patch, AsyncMock
from app.services.email_service import EmailService, email_service
from app.models.user_models import User
from app.models.event_models import Event, EventInvitation
from datetime import datetime, timedelta

class TestEmailService:
    """Test cases for EmailService."""
    
    @pytest.fixture
    def email_service_instance(self):
        """Create EmailService instance for testing."""
        return EmailService()
    
    @pytest.fixture
    def mock_user(self):
        """Create a mock user for testing."""
        user = Mock(spec=User)
        user.id = 1
        user.email = "test@example.com"
        user.full_name = "Test User"
        user.username = "testuser"
        return user
    
    @pytest.fixture
    def mock_event(self):
        """Create a mock event for testing."""
        event = Mock(spec=Event)
        event.id = 1
        event.title = "Test Event"
        event.description = "A test event"
        event.start_datetime = datetime.utcnow() + timedelta(days=7)
        event.end_datetime = datetime.utcnow() + timedelta(days=7, hours=3)
        event.venue_name = "Test Venue"
        event.venue_address = "123 Test St"
        return event
    
    @pytest.fixture
    def mock_invitation(self, mock_event, mock_user):
        """Create a mock event invitation."""
        invitation = Mock(spec=EventInvitation)
        invitation.id = 1
        invitation.event = mock_event
        invitation.user = mock_user
        invitation.invitation_message = "Please join us!"
        invitation.plus_one_allowed = True
        invitation.rsvp_status = "pending"
        invitation.response_message = None
        invitation.plus_one_name = None
        invitation.dietary_restrictions = None
        return invitation
    
    @patch('resend.Emails.send')
    async def test_send_email_success(self, mock_resend_send, email_service_instance):
        """Test successful email sending."""
        # Mock successful response
        mock_resend_send.return_value = {"id": "email_123"}
        
        result = await email_service_instance.send_email(
            to_email="test@example.com",
            subject="Test Subject",
            html_content="<h1>Test Content</h1>"
        )
        
        assert result is True
        mock_resend_send.assert_called_once()
        
        # Verify the call arguments
        call_args = mock_resend_send.call_args[0][0]
        assert call_args["to"] == ["test@example.com"]
        assert call_args["subject"] == "Test Subject"
        assert call_args["html"] == "<h1>Test Content</h1>"
    
    @patch('resend.Emails.send')
    async def test_send_email_failure(self, mock_resend_send, email_service_instance):
        """Test email sending failure."""
        # Mock failure response
        mock_resend_send.side_effect = Exception("Email sending failed")
        
        result = await email_service_instance.send_email(
            to_email="test@example.com",
            subject="Test Subject",
            html_content="<h1>Test Content</h1>"
        )
        
        assert result is False
    
    @patch('resend.Emails.send')
    async def test_send_bulk_email(self, mock_resend_send, email_service_instance):
        """Test bulk email sending."""
        # Mock successful responses
        mock_resend_send.return_value = {"id": "email_123"}
        
        recipients = ["user1@example.com", "user2@example.com", "user3@example.com"]
        
        results = await email_service_instance.send_bulk_email(
            recipients=recipients,
            subject="Bulk Test",
            html_content="<h1>Bulk Content</h1>"
        )
        
        assert len(results) == 3
        assert all(results.values())  # All should be True
        assert mock_resend_send.call_count == 3
    
    @patch.object(EmailService, 'render_template')
    @patch.object(EmailService, 'send_email')
    async def test_send_welcome_email(self, mock_send_email, mock_render_template, email_service_instance, mock_user):
        """Test sending welcome email."""
        mock_render_template.return_value = "<h1>Welcome!</h1>"
        mock_send_email.return_value = True
        
        result = await email_service_instance.send_welcome_email(mock_user)
        
        assert result is True
        mock_render_template.assert_called_once_with("welcome.html", {
            "user_name": "Test User",
            "user_email": "test@example.com",
            "app_name": "Plan et al",
            "login_url": "http://localhost:3000/login"
        })
        mock_send_email.assert_called_once()
    
    @patch.object(EmailService, 'render_template')
    @patch.object(EmailService, 'send_email')
    async def test_send_verification_otp(self, mock_send_email, mock_render_template, email_service_instance, mock_user):
        """Test sending verification OTP email."""
        mock_render_template.return_value = "<h1>Your OTP: 123456</h1>"
        mock_send_email.return_value = True
        
        result = await email_service_instance.send_verification_otp(mock_user, "123456")
        
        assert result is True
        mock_render_template.assert_called_once_with("verification_otp.html", {
            "user_name": "Test User",
            "otp_code": "123456",
            "app_name": "Plan et al",
            "expires_in": "10 minutes"
        })
        mock_send_email.assert_called_once_with(
            to_email="test@example.com",
            subject="Your Plan et al verification code",
            html_content="<h1>Your OTP: 123456</h1>"
        )
    
    @patch.object(EmailService, 'render_template')
    @patch.object(EmailService, 'send_email')
    async def test_send_password_reset_otp(self, mock_send_email, mock_render_template, email_service_instance, mock_user):
        """Test sending password reset OTP email."""
        mock_render_template.return_value = "<h1>Reset OTP: 654321</h1>"
        mock_send_email.return_value = True
        
        result = await email_service_instance.send_password_reset_otp(mock_user, "654321")
        
        assert result is True
        mock_render_template.assert_called_once_with("password_reset_otp.html", {
            "user_name": "Test User",
            "otp_code": "654321",
            "app_name": "Plan et al",
            "expires_in": "10 minutes"
        })
        mock_send_email.assert_called_once_with(
            to_email="test@example.com",
            subject="Your Plan et al password reset code",
            html_content="<h1>Reset OTP: 654321</h1>"
        )
    
    @patch.object(EmailService, 'render_template')
    @patch.object(EmailService, 'send_email')
    async def test_send_password_changed_notification(self, mock_send_email, mock_render_template, email_service_instance, mock_user):
        """Test sending password changed notification."""
        mock_render_template.return_value = "<h1>Password Changed</h1>"
        mock_send_email.return_value = True
        
        result = await email_service_instance.send_password_changed_notification(mock_user)
        
        assert result is True
        mock_render_template.assert_called_once()
        mock_send_email.assert_called_once_with(
            to_email="test@example.com",
            subject="Your Plan et al password was changed",
            html_content="<h1>Password Changed</h1>"
        )
    
    @patch.object(EmailService, 'render_template')
    @patch.object(EmailService, 'send_email')
    async def test_send_event_invitation(self, mock_send_email, mock_render_template, email_service_instance, mock_event, mock_invitation, mock_user):
        """Test sending event invitation email."""
        mock_render_template.return_value = "<h1>You're Invited!</h1>"
        mock_send_email.return_value = True
        
        inviter = Mock(spec=User)
        inviter.email = "inviter@example.com"
        inviter.full_name = "Event Organizer"
        
        result = await email_service_instance.send_event_invitation(
            mock_event, mock_invitation, mock_user, inviter
        )
        
        assert result is True
        mock_render_template.assert_called_once()
        mock_send_email.assert_called_once()
        
        # Check that reply_to is set to inviter's email
        call_kwargs = mock_send_email.call_args[1]
        assert call_kwargs["reply_to"] == "inviter@example.com"
    
    @patch.object(EmailService, 'render_template')
    @patch.object(EmailService, 'send_email')
    async def test_send_rsvp_confirmation(self, mock_send_email, mock_render_template, email_service_instance, mock_event, mock_invitation, mock_user):
        """Test sending RSVP confirmation email."""
        mock_render_template.return_value = "<h1>RSVP Confirmed</h1>"
        mock_send_email.return_value = True
        
        # Set RSVP status
        mock_invitation.rsvp_status = "accepted"
        mock_invitation.response_message = "Looking forward to it!"
        
        result = await email_service_instance.send_rsvp_confirmation(
            mock_event, mock_invitation, mock_user
        )
        
        assert result is True
        mock_render_template.assert_called_once()
        mock_send_email.assert_called_once_with(
            to_email="test@example.com",
            subject="RSVP confirmed for Test Event",
            html_content="<h1>RSVP Confirmed</h1>"
        )
    
    @patch.object(EmailService, 'render_template')
    @patch.object(EmailService, 'send_email')
    async def test_send_event_reminder(self, mock_send_email, mock_render_template, email_service_instance, mock_event, mock_user):
        """Test sending event reminder email."""
        mock_render_template.return_value = "<h1>Event Reminder</h1>"
        mock_send_email.return_value = True
        
        result = await email_service_instance.send_event_reminder(
            mock_event, mock_user, "24h"
        )
        
        assert result is True
        mock_render_template.assert_called_once_with("event_reminder.html", {
            "user_name": "Test User",
            "event_title": "Test Event",
            "event_date": mock_event.start_datetime.strftime("%A, %B %d, %Y"),
            "event_time": mock_event.start_datetime.strftime("%I:%M %p"),
            "event_venue": "Test Venue",
            "event_address": "123 Test St",
            "reminder_message": "Don't forget! Your event is tomorrow.",
            "event_url": "http://localhost:3000/events/1"
        })
    
    @patch.object(EmailService, 'render_template')
    @patch.object(EmailService, 'send_email')
    async def test_send_task_assignment(self, mock_send_email, mock_render_template, email_service_instance, mock_event, mock_user):
        """Test sending task assignment email."""
        mock_render_template.return_value = "<h1>New Task Assigned</h1>"
        mock_send_email.return_value = True
        
        assigner = Mock(spec=User)
        assigner.email = "assigner@example.com"
        assigner.full_name = "Task Assigner"
        
        due_date = datetime.utcnow() + timedelta(days=3)
        
        result = await email_service_instance.send_task_assignment(
            mock_event, "Buy decorations", mock_user, assigner, due_date
        )
        
        assert result is True
        mock_render_template.assert_called_once()
        mock_send_email.assert_called_once()
        
        # Check reply_to is set
        call_kwargs = mock_send_email.call_args[1]
        assert call_kwargs["reply_to"] == "assigner@example.com"
    
    @patch.object(EmailService, 'render_template')
    @patch.object(EmailService, 'send_email')
    async def test_send_expense_split_notification(self, mock_send_email, mock_render_template, email_service_instance, mock_event, mock_user):
        """Test sending expense split notification."""
        mock_render_template.return_value = "<h1>Expense Split</h1>"
        mock_send_email.return_value = True
        
        paid_by = Mock(spec=User)
        paid_by.email = "payer@example.com"
        paid_by.full_name = "Event Payer"
        
        result = await email_service_instance.send_expense_split_notification(
            mock_event, "Venue Rental", 50.0, "USD", mock_user, paid_by
        )
        
        assert result is True
        mock_render_template.assert_called_once_with("expense_split.html", {
            "user_name": "Test User",
            "paid_by_name": "Event Payer",
            "expense_title": "Venue Rental",
            "amount_owed": "USD 50.00",
            "event_title": "Test Event",
            "event_url": "http://localhost:3000/events/1/expenses"
        })
    
    def test_render_template_success(self, email_service_instance):
        """Test successful template rendering."""
        with patch('jinja2.Environment.get_template') as mock_get_template:
            mock_template = Mock()
            mock_template.render.return_value = "<h1>Rendered Content</h1>"
            mock_get_template.return_value = mock_template
            
            result = email_service_instance.render_template("test.html", {"name": "Test"})
            
            assert result == "<h1>Rendered Content</h1>"
            mock_get_template.assert_called_once_with("test.html")
            mock_template.render.assert_called_once_with(name="Test")
    
    def test_render_template_failure(self, email_service_instance):
        """Test template rendering failure."""
        with patch('jinja2.Environment.get_template') as mock_get_template:
            mock_get_template.side_effect = Exception("Template not found")
            
            result = email_service_instance.render_template("nonexistent.html", {})
            
            assert result == ""
    
    @patch.object(EmailService, 'render_template')
    @patch.object(EmailService, 'send_email')
    async def test_send_friend_request_notification(self, mock_send_email, mock_render_template, email_service_instance, mock_user):
        """Test sending friend request notification."""
        mock_render_template.return_value = "<h1>Friend Request</h1>"
        mock_send_email.return_value = True
        
        requester = Mock(spec=User)
        requester.id = 2
        requester.full_name = "Friend Requester"
        requester.username = "friendrequester"
        
        result = await email_service_instance.send_friend_request_notification(
            mock_user, requester
        )
        
        assert result is True
        mock_render_template.assert_called_once_with("friend_request.html", {
            "user_name": "Test User",
            "requester_name": "Friend Requester",
            "requester_username": "friendrequester",
            "profile_url": "http://localhost:3000/users/2",
            "friends_url": "http://localhost:3000/friends"
        })
    
    @patch.object(EmailService, 'render_template')
    @patch.object(EmailService, 'send_email')
    async def test_send_weekly_digest(self, mock_send_email, mock_render_template, email_service_instance, mock_user):
        """Test sending weekly digest email."""
        mock_render_template.return_value = "<h1>Weekly Digest</h1>"
        mock_send_email.return_value = True
        
        upcoming_events = [mock_user]  # Mock events list
        pending_tasks = [{"title": "Test Task"}]
        pending_rsvps = [{"event": "Test Event"}]
        
        result = await email_service_instance.send_weekly_digest(
            mock_user, upcoming_events, pending_tasks, pending_rsvps
        )
        
        assert result is True
        mock_render_template.assert_called_once_with("weekly_digest.html", {
            "user_name": "Test User",
            "upcoming_events": upcoming_events,
            "pending_tasks": pending_tasks,
            "pending_rsvps": pending_rsvps,
            "dashboard_url": "http://localhost:3000/dashboard"
        })
        mock_send_email.assert_called_once_with(
            to_email="test@example.com",
            subject="Your Plan et al weekly digest",
            html_content="<h1>Weekly Digest</h1>"
        )

class TestEmailServiceIntegration:
    """Integration tests for EmailService."""
    
    def test_global_email_service_instance(self):
        """Test that global email service instance is properly initialized."""
        assert email_service is not None
        assert isinstance(email_service, EmailService)
        assert email_service.from_email == "noreply@planetal.com"
        assert email_service.from_name == "Plan et al"
    
    @patch('resend.api_key')
    def test_resend_api_key_initialization(self, mock_api_key):
        """Test that Resend API key is properly set."""
        # This would test the actual initialization
        # In a real test, you'd verify the API key is set from settings
        pass

class TestEmailServiceErrorHandling:
    """Test error handling in EmailService."""
    
    @pytest.fixture
    def email_service_instance(self):
        return EmailService()
    
    @patch('resend.Emails.send')
    async def test_send_email_with_invalid_recipient(self, mock_resend_send, email_service_instance):
        """Test email sending with invalid recipient."""
        mock_resend_send.side_effect = Exception("Invalid email address")
        
        result = await email_service_instance.send_email(
            to_email="invalid-email",
            subject="Test",
            html_content="Test"
        )
        
        assert result is False
    
    @patch('resend.Emails.send')
    async def test_send_email_with_empty_content(self, mock_resend_send, email_service_instance):
        """Test email sending with empty content."""
        mock_resend_send.return_value = {"id": "email_123"}
        
        result = await email_service_instance.send_email(
            to_email="test@example.com",
            subject="",
            html_content=""
        )
        
        assert result is True  # Should still send even with empty content
    
    async def test_bulk_email_partial_failure(self, email_service_instance):
        """Test bulk email with some failures."""
        with patch.object(email_service_instance, 'send_email') as mock_send:
            # Mock some successes and some failures
            mock_send.side_effect = [True, False, True]
            
            recipients = ["user1@example.com", "user2@example.com", "user3@example.com"]
            results = await email_service_instance.send_bulk_email(
                recipients, "Test", "Content"
            )
            
            assert results["user1@example.com"] is True
            assert results["user2@example.com"] is False
            assert results["user3@example.com"] is True
            assert mock_send.call_count == 3