import resend
from typing import List, Optional, Dict, Any
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.core.config import settings
from app.core.circuit_breaker import email_circuit_breaker, email_fallback
from app.models.user_models import User
from app.models.event_models import Event, EventInvitation
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Initialize Resend
resend.api_key = settings.RESEND_API_KEY

# Log Resend configuration status
if not settings.RESEND_API_KEY:
    logger.warning("Resend API key not configured. Email functionality will be disabled.")

# Initialize Jinja2 for email templates
template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates', 'emails')
env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(['html', 'xml'])
)

# Add custom filter for current year
def current_year():
    """Return the current year"""
    return datetime.now().year

env.globals['current_year'] = current_year

class EmailService:
    """Service for sending emails using Resend."""
    
    def __init__(self):
        self.from_email = settings.EMAILS_FROM_EMAIL or "noreply@planetal.com"
        self.from_name = settings.EMAILS_FROM_NAME or "Plan et al"

    def is_configured(self) -> bool:
        """Return True when outbound email has the minimum configuration."""
        return bool(settings.RESEND_API_KEY)
    
    @email_circuit_breaker(fallback=email_fallback)
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict]] = None
    ) -> bool:
        """Send email using Resend."""
        try:
            params = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }
            
            if text_content:
                params["text"] = text_content
            
            if reply_to:
                params["reply_to"] = reply_to
            
            if attachments:
                params["attachments"] = attachments
            
            response = resend.Emails.send(params)
            return response.get("id") is not None
            
        except Exception as e:
            print(f"Failed to send email: {str(e)}")
            return False
    
    async def send_bulk_email(
        self,
        recipients: List[str],
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> Dict[str, bool]:
        """Send bulk emails to multiple recipients."""
        results = {}
        
        for email in recipients:
            success = await self.send_email(
                to_email=email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            results[email] = success
        
        return results
    
    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render email template with context."""
        try:
            template = env.get_template(template_name)
            return template.render(**context)
        except Exception as e: 
            print(f"Failed to render template {template_name}: {str(e)}")
            return ""
    
    # Authentication emails
    async def send_welcome_email(self, user: User) -> bool:
        """Send welcome email to new user."""
        context = {
            "user_name": user.full_name,
            "user_email": user.email,
            "app_name": "Plan et al",
            "login_url": f"{settings.FRONTEND_URL}/login"
        }
        
        html_content = self.render_template("welcome.html", context)
        
        return await self.send_email(
            to_email=user.email,
            subject="Welcome to Plan et al - Let's start planning!",
            html_content=html_content
        )
    
    async def send_email_verification(self, user: User, verification_token: str) -> bool:
        """Send email verification link."""
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
        
        context = {
            "user_name": user.full_name,
            "verification_url": verification_url,
            "app_name": "Plan et al"
        }
        
        html_content = self.render_template("email_verification.html", context)
        
        return await self.send_email(
            to_email=user.email,
            subject="Verify your Plan et al account",
            html_content=html_content
        )
    
    async def send_verification_otp(self, user: User, otp: str) -> bool:
        """Send email verification OTP."""
        context = {
            "user_name": user.full_name,
            "otp_code": otp,
            "app_name": "Plan et al",
            "expires_in": "10 minutes"
        }
        
        html_content = self.render_template("verification_otp.html", context)
        
        return await self.send_email(
            to_email=user.email,
            subject="Your Plan et al verification code",
            html_content=html_content
        )
    
    async def send_password_reset_otp(self, user: User, otp: str) -> bool:
        """Send password reset OTP."""
        context = {
            "user_name": user.full_name,
            "otp_code": otp,
            "app_name": "Plan et al",
            "expires_in": "10 minutes"
        }
        
        html_content = self.render_template("password_reset_otp.html", context)
        
        return await self.send_email(
            to_email=user.email,
            subject="Your Plan et al password reset code",
            html_content=html_content
        )
    
    async def send_password_reset(self, user: User, reset_token: str) -> bool:
        """Send password reset email."""
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        
        context = {
            "user_name": user.full_name,
            "reset_url": reset_url,
            "app_name": "Plan et al",
            "expires_in": "1 hour"
        }
        
        html_content = self.render_template("password_reset.html", context)
        
        return await self.send_email(
            to_email=user.email,
            subject="Reset your Plan et al password",
            html_content=html_content
        )
    
    async def send_password_changed_notification(self, user: User) -> bool:
        """Send notification when password is changed."""
        context = {
            "user_name": user.full_name,
            "app_name": "Plan et al",
            "support_email": settings.SUPPORT_EMAIL or "support@planetal.com",
            "changed_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        }
        
        html_content = self.render_template("password_changed.html", context)
        
        return await self.send_email(
            to_email=user.email,
            subject="Your Plan et al password was changed",
            html_content=html_content
        )
    
    # Event-related emails
    async def send_event_invitation(
        self, 
        event: Event, 
        invitation: EventInvitation, 
        invitee: User,
        inviter: User
    ) -> bool:
        """Send event invitation email."""
        event_url = f"{settings.FRONTEND_URL}/events/{event.id}"
        rsvp_url = f"{settings.FRONTEND_URL}/events/{event.id}/rsvp?token={invitation.id}"
        
        context = {
            "invitee_name": invitee.full_name,
            "inviter_name": inviter.full_name,
            "event_title": event.title,
            "event_description": event.description,
            "event_date": event.start_datetime.strftime("%A, %B %d, %Y"),
            "event_time": event.start_datetime.strftime("%I:%M %p"),
            "event_venue": event.venue_name or "TBD",
            "event_address": event.venue_address or "",
            "invitation_message": invitation.invitation_message or "",
            "event_url": event_url,
            "rsvp_url": rsvp_url,
            "plus_one_allowed": invitation.plus_one_allowed
        }
        
        html_content = self.render_template("event_invitation.html", context)
        
        return await self.send_email(
            to_email=invitee.email,
            subject=f"You're invited to {event.title}!",
            html_content=html_content,
            reply_to=inviter.email
        )
    
    async def send_rsvp_confirmation(
        self, 
        event: Event, 
        invitation: EventInvitation, 
        user: User
    ) -> bool:
        """Send RSVP confirmation email."""
        event_url = f"{settings.FRONTEND_URL}/events/{event.id}"
        
        status_messages = {
            "accepted": "Great! We're excited to see you there.",
            "declined": "Thanks for letting us know. You'll be missed!",
            "maybe": "Thanks for responding. We hope you can make it!"
        }
        
        context = {
            "user_name": user.full_name,
            "event_title": event.title,
            "event_date": event.start_datetime.strftime("%A, %B %d, %Y"),
            "event_time": event.start_datetime.strftime("%I:%M %p"),
            "event_venue": event.venue_name or "TBD",
            "rsvp_status": invitation.rsvp_status,
            "status_message": status_messages.get(invitation.rsvp_status, ""),
            "event_url": event_url,
            "response_message": invitation.response_message or "",
            "plus_one_name": invitation.plus_one_name or "",
            "dietary_restrictions": invitation.dietary_restrictions or ""
        }
        
        html_content = self.render_template("rsvp_confirmation.html", context)
        
        return await self.send_email(
            to_email=user.email,
            subject=f"RSVP confirmed for {event.title}",
            html_content=html_content
        )
    
    async def send_event_reminder(
        self, 
        event: Event, 
        user: User, 
        reminder_type: str = "24h"
    ) -> bool:
        """Send event reminder email."""
        event_url = f"{settings.FRONTEND_URL}/events/{event.id}"
        
        reminder_messages = {
            "24h": "Don't forget! Your event is tomorrow.",
            "1h": "Your event starts in 1 hour!",
            "1w": "Just a week to go until your event!"
        }
        
        context = {
            "user_name": user.full_name,
            "event_title": event.title,
            "event_date": event.start_datetime.strftime("%A, %B %d, %Y"),
            "event_time": event.start_datetime.strftime("%I:%M %p"),
            "event_venue": event.venue_name or "TBD",
            "event_address": event.venue_address or "",
            "reminder_message": reminder_messages.get(reminder_type, ""),
            "event_url": event_url
        }
        
        html_content = self.render_template("event_reminder.html", context)
        
        return await self.send_email(
            to_email=user.email,
            subject=f"Reminder: {event.title}",
            html_content=html_content
        )
    
    async def send_event_update_notification(
        self, 
        event: Event, 
        user: User, 
        changes: List[str]
    ) -> bool:
        """Send notification when event details are updated."""
        event_url = f"{settings.FRONTEND_URL}/events/{event.id}"
        
        context = {
            "user_name": user.full_name,
            "event_title": event.title,
            "event_date": event.start_datetime.strftime("%A, %B %d, %Y"),
            "event_time": event.start_datetime.strftime("%I:%M %p"),
            "changes": changes,
            "event_url": event_url
        }
        
        html_content = self.render_template("event_update.html", context)
        
        return await self.send_email(
            to_email=user.email,
            subject=f"Update: {event.title}",
            html_content=html_content
        )
    
    async def send_event_cancellation(
        self, 
        event: Event, 
        user: User, 
        reason: Optional[str] = None
    ) -> bool:
        """Send event cancellation notification."""
        context = {
            "user_name": user.full_name,
            "event_title": event.title,
            "event_date": event.start_datetime.strftime("%A, %B %d, %Y"),
            "cancellation_reason": reason or "No reason provided",
            "support_email": settings.SUPPORT_EMAIL or "support@planetal.com"
        }
        
        html_content = self.render_template("event_cancellation.html", context)
        
        return await self.send_email(
            to_email=user.email,
            subject=f"Event Cancelled: {event.title}",
            html_content=html_content
        )
    
    # Task and expense emails
    async def send_task_assignment(
        self, 
        event: Event, 
        task_title: str, 
        assignee: User, 
        assigner: User,
        due_date: Optional[datetime] = None
    ) -> bool:
        """Send task assignment notification."""
        event_url = f"{settings.FRONTEND_URL}/events/{event.id}"
        
        context = {
            "assignee_name": assignee.full_name,
            "assigner_name": assigner.full_name,
            "task_title": task_title,
            "event_title": event.title,
            "due_date": due_date.strftime("%A, %B %d, %Y") if due_date else "No due date",
            "event_url": event_url
        }
        
        html_content = self.render_template("task_assignment.html", context)
        
        return await self.send_email(
            to_email=assignee.email,
            subject=f"New task assigned: {task_title}",
            html_content=html_content,
            reply_to=assigner.email
        )
    
    async def send_expense_split_notification(
        self, 
        event: Event, 
        expense_title: str, 
        amount_owed: float, 
        currency: str,
        user: User, 
        paid_by: User
    ) -> bool:
        """Send expense split notification."""
        event_url = f"{settings.FRONTEND_URL}/events/{event.id}/expenses"
        
        context = {
            "user_name": user.full_name,
            "paid_by_name": paid_by.full_name,
            "expense_title": expense_title,
            "amount_owed": f"{currency} {amount_owed:.2f}",
            "event_title": event.title,
            "event_url": event_url
        }
        
        html_content = self.render_template("expense_split.html", context)
        
        return await self.send_email(
            to_email=user.email,
            subject=f"Expense split: {expense_title}",
            html_content=html_content,
            reply_to=paid_by.email
        )
    
    async def send_payment_reminder(
        self, 
        event: Event, 
        expense_title: str, 
        amount_owed: float, 
        currency: str,
        user: User
    ) -> bool:
        """Send payment reminder for outstanding expenses."""
        event_url = f"{settings.FRONTEND_URL}/events/{event.id}/expenses"
        
        context = {
            "user_name": user.full_name,
            "expense_title": expense_title,
            "amount_owed": f"{currency} {amount_owed:.2f}",
            "event_title": event.title,
            "event_url": event_url
        }
        
        html_content = self.render_template("payment_reminder.html", context)
        
        return await self.send_email(
            to_email=user.email,
            subject=f"Payment reminder: {expense_title}",
            html_content=html_content
        )
    
    # Notification emails
    async def send_friend_request_notification(
        self, 
        user: User, 
        requester: User
    ) -> bool:
        """Send friend request notification."""
        profile_url = f"{settings.FRONTEND_URL}/users/{requester.id}"
        
        context = {
            "user_name": user.full_name,
            "requester_name": requester.full_name,
            "requester_username": requester.username or requester.email,
            "profile_url": profile_url,
            "friends_url": f"{settings.FRONTEND_URL}/friends"
        }
        
        html_content = self.render_template("friend_request.html", context)
        
        return await self.send_email(
            to_email=user.email,
            subject=f"{requester.full_name} wants to be friends!",
            html_content=html_content
        )
    
    async def send_weekly_digest(
        self, 
        user: User, 
        upcoming_events: List[Event],
        pending_tasks: List[Dict],
        pending_rsvps: List[Dict]
    ) -> bool:
        """Send weekly digest email."""
        context = {
            "user_name": user.full_name,
            "upcoming_events": upcoming_events,
            "pending_tasks": pending_tasks,
            "pending_rsvps": pending_rsvps,
            "dashboard_url": f"{settings.FRONTEND_URL}/dashboard"
        }
        
        html_content = self.render_template("weekly_digest.html", context)
        
        return await self.send_email(
            to_email=user.email,
            subject="Your Plan et al weekly digest",
            html_content=html_content
        )

# Global email service instance
email_service = EmailService()