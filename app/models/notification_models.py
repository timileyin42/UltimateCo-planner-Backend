from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLEnum, JSON, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from app.models.shared_models import BaseModel, TimestampMixin
import enum

class NotificationType(str, enum.Enum):
    """Types of notifications."""
    # Event-related notifications
    RSVP_REMINDER = "rsvp_reminder"
    PAYMENT_REMINDER = "payment_reminder"
    DRESS_CODE_REMINDER = "dress_code_reminder"
    EVENT_REMINDER = "event_reminder"
    TASK_REMINDER = "task_reminder"
    TIMELINE_REMINDER = "timeline_reminder"
    WEATHER_ALERT = "weather_alert"
    BUDGET_ALERT = "budget_alert"
    
    # Social notifications
    EVENT_INVITE = "event_invite"
    FRIEND_REQUEST = "friend_request"
    FRIEND_REQUEST_ACCEPTED = "friend_request_accepted"
    GROUP_INVITE = "group_invite"
    GROUP_JOIN_REQUEST = "group_join_request"
    SOCIAL_NOTIFICATION = "social_notification"
    
    # System notifications
    SYSTEM_ANNOUNCEMENT = "system_announcement"
    ACCOUNT_UPDATE = "account_update"
    SECURITY_ALERT = "security_alert"
    
    CUSTOM = "custom"

class NotificationStatus(str, enum.Enum):
    """Status of notifications."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ReminderFrequency(str, enum.Enum):
    """Frequency for recurring reminders."""
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    CUSTOM = "custom"

class NotificationChannel(str, enum.Enum):
    """Channels for sending notifications."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"

class DevicePlatform(str, enum.Enum):
    """Device platforms for push notifications."""
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"

class UserDevice(BaseModel, TimestampMixin):
    """User device information for push notifications."""
    __tablename__ = "notification_devices"
    
    # Device identification
    device_token: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # Unique device identifier
    platform: Mapped[DevicePlatform] = mapped_column(SQLEnum(DevicePlatform), nullable=False)
    
    # Device info
    device_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # "John's iPhone"
    app_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    os_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # User relationship
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="devices")
    
    # Indexes
    __table_args__ = (
        Index('idx_userdevice_user_id', 'user_id'),
        Index('idx_userdevice_device_token', 'device_token'),
        Index('idx_userdevice_platform', 'platform'),
        Index('idx_userdevice_is_active', 'is_active'),
        Index('idx_userdevice_last_used', 'last_used_at'),
        Index('idx_userdevice_user_active', 'user_id', 'is_active'),
        Index('idx_userdevice_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<UserDevice(id={self.id}, user_id={self.user_id}, platform={self.platform}, active={self.is_active})>"

class SmartReminder(BaseModel, TimestampMixin):
    """Smart reminder system for automated notifications."""
    __tablename__ = "smart_reminders"
    
    # Basic info
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[NotificationType] = mapped_column(SQLEnum(NotificationType), nullable=False)
    
    # Timing
    scheduled_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Recurrence
    frequency: Mapped[ReminderFrequency] = mapped_column(SQLEnum(ReminderFrequency), default=ReminderFrequency.ONCE)
    recurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    recurrence_sent: Mapped[int] = mapped_column(Integer, default=0)
    
    # Status and settings
    status: Mapped[NotificationStatus] = mapped_column(SQLEnum(NotificationStatus), default=NotificationStatus.PENDING)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Channels
    send_email: Mapped[bool] = mapped_column(Boolean, default=True)
    send_sms: Mapped[bool] = mapped_column(Boolean, default=False)
    send_push: Mapped[bool] = mapped_column(Boolean, default=True)
    send_in_app: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Targeting
    target_all_guests: Mapped[bool] = mapped_column(Boolean, default=False)
    target_specific_users: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of user IDs
    target_rsvp_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Filter by RSVP status
    
    # Conditions
    conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON object for complex conditions
    
    # Relationships
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    event = relationship("Event", back_populates="smart_reminders")
    creator = relationship("User", foreign_keys=[creator_id], back_populates="created_reminders")
    notifications = relationship("NotificationLog", back_populates="reminder", cascade="all, delete-orphan")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_smartreminder_event_id', 'event_id'),
        Index('idx_smartreminder_creator_id', 'creator_id'),
        Index('idx_smartreminder_notification_type', 'notification_type'),
        Index('idx_smartreminder_status', 'status'),
        Index('idx_smartreminder_is_active', 'is_active'),
        Index('idx_smartreminder_scheduled_time', 'scheduled_time'),
        Index('idx_smartreminder_frequency', 'frequency'),
        Index('idx_smartreminder_created_at', 'created_at'),
        # Combined indexes for common queries
        Index('idx_smartreminder_event_status', 'event_id', 'status'),
        Index('idx_smartreminder_active_scheduled', 'is_active', 'scheduled_time'),
        Index('idx_smartreminder_type_status', 'notification_type', 'status'),
        Index('idx_smartreminder_creator_active', 'creator_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<SmartReminder(id={self.id}, title='{self.title}', type='{self.notification_type}')>"
    
    @property
    def is_due(self) -> bool:
        """Check if reminder is due to be sent."""
        if self.status != NotificationStatus.PENDING or not self.is_active:
            return False
        return datetime.utcnow() >= self.scheduled_time
    
    @property
    def target_user_ids(self) -> List[int]:
        """Get list of target user IDs."""
        if not self.target_specific_users:
            return []
        try:
            import json
            return json.loads(self.target_specific_users)
        except:
            return []

class NotificationLog(BaseModel, TimestampMixin):
    """Log of sent notifications for tracking and analytics."""
    __tablename__ = "notification_logs"
    
    # Notification details
    notification_type: Mapped[NotificationType] = mapped_column(SQLEnum(NotificationType), nullable=False)
    channel: Mapped[NotificationChannel] = mapped_column(SQLEnum(NotificationChannel), nullable=False)
    
    # Content
    subject: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Delivery info
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Status
    status: Mapped[NotificationStatus] = mapped_column(SQLEnum(NotificationStatus), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Additional data  
    extra_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON object for additional data
    
    # Relationships
    reminder_id: Mapped[Optional[int]] = mapped_column(ForeignKey("smart_reminders.id"), nullable=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    reminder = relationship("SmartReminder", back_populates="notifications")
    event = relationship("Event", back_populates="notification_logs")
    recipient = relationship("User", back_populates="received_notifications")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_notificationlog_reminder_id', 'reminder_id'),
        Index('idx_notificationlog_event_id', 'event_id'),
        Index('idx_notificationlog_recipient_id', 'recipient_id'),
        Index('idx_notificationlog_notification_type', 'notification_type'),
        Index('idx_notificationlog_channel', 'channel'),
        Index('idx_notificationlog_status', 'status'),
        Index('idx_notificationlog_sent_at', 'sent_at'),
        Index('idx_notificationlog_delivered_at', 'delivered_at'),
        Index('idx_notificationlog_read_at', 'read_at'),
        Index('idx_notificationlog_created_at', 'created_at'),
        # Combined indexes for common queries
        Index('idx_notificationlog_recipient_type', 'recipient_id', 'notification_type'),
        Index('idx_notificationlog_event_status', 'event_id', 'status'),
        Index('idx_notificationlog_recipient_sent', 'recipient_id', 'sent_at'),
        Index('idx_notificationlog_channel_status', 'channel', 'status'),
    )
    
    def __repr__(self):
        return f"<NotificationLog(id={self.id}, type='{self.notification_type}', status='{self.status}')>"

class NotificationPreference(BaseModel, TimestampMixin):
    """User preferences for notifications."""
    __tablename__ = "notification_preferences"
    
    # Preference settings
    notification_type: Mapped[NotificationType] = mapped_column(SQLEnum(NotificationType), nullable=False)
    
    # Channel preferences
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timing preferences
    advance_notice_hours: Mapped[int] = mapped_column(Integer, default=24)  # Hours before event
    quiet_hours_start: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # "22:00"
    quiet_hours_end: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # "08:00"
    
    # Frequency limits
    max_daily_notifications: Mapped[int] = mapped_column(Integer, default=10)
    
    # Relationships
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="notification_preferences")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_notificationpref_user_id', 'user_id'),
        Index('idx_notificationpref_notification_type', 'notification_type'),
        Index('idx_notificationpref_email_enabled', 'email_enabled'),
        Index('idx_notificationpref_sms_enabled', 'sms_enabled'),
        Index('idx_notificationpref_push_enabled', 'push_enabled'),
        Index('idx_notificationpref_in_app_enabled', 'in_app_enabled'),
        Index('idx_notificationpref_created_at', 'created_at'),
        # Combined indexes for common queries
        Index('idx_notificationpref_user_type', 'user_id', 'notification_type'),
        Index('idx_notificationpref_user_email', 'user_id', 'email_enabled'),
        Index('idx_notificationpref_user_push', 'user_id', 'push_enabled'),
    )
    
    def __repr__(self):
        return f"<NotificationPreference(user_id={self.user_id}, type='{self.notification_type}')>"

class ReminderTemplate(BaseModel, TimestampMixin):
    """Templates for different types of reminders."""
    __tablename__ = "reminder_templates"
    
    # Template info
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notification_type: Mapped[NotificationType] = mapped_column(SQLEnum(NotificationType), nullable=False)
    
    # Template content
    subject_template: Mapped[str] = mapped_column(String(200), nullable=False)
    message_template: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Template settings
    is_system_template: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timing defaults
    default_advance_hours: Mapped[int] = mapped_column(Integer, default=24)
    default_frequency: Mapped[ReminderFrequency] = mapped_column(SQLEnum(ReminderFrequency), default=ReminderFrequency.ONCE)
    
    # Variables used in template
    template_variables: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of variable names
    
    # Relationships
    creator_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    # Relationships
    creator = relationship("User", back_populates="created_reminder_templates")
    
    def __repr__(self):
        return f"<ReminderTemplate(id={self.id}, name='{self.name}', type='{self.notification_type}')>"
    
    def render_subject(self, variables: Dict[str, Any]) -> str:
        """Render subject template with variables."""
        try:
            return self.subject_template.format(**variables)
        except KeyError:
            return self.subject_template
    
    def render_message(self, variables: Dict[str, Any]) -> str:
        """Render message template with variables."""
        try:
            return self.message_template.format(**variables)
        except KeyError:
            return self.message_template

class AutomationRule(BaseModel, TimestampMixin):
    """Rules for automatic reminder creation."""
    __tablename__ = "automation_rules"
    
    # Rule info
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Trigger conditions
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False)  # event_created, rsvp_pending, etc.
    trigger_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON object
    
    # Reminder settings
    notification_type: Mapped[NotificationType] = mapped_column(SQLEnum(NotificationType), nullable=False)
    template_id: Mapped[int] = mapped_column(ForeignKey("reminder_templates.id"), nullable=False)
    
    # Timing
    delay_hours: Mapped[int] = mapped_column(Integer, default=0)  # Delay after trigger
    advance_hours: Mapped[int] = mapped_column(Integer, default=24)  # Hours before event
    
    # Settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    apply_to_all_events: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    creator = relationship("User", back_populates="created_automation_rules")
    template = relationship("ReminderTemplate")
    
    def __repr__(self):
        return f"<AutomationRule(id={self.id}, name='{self.name}', trigger='{self.trigger_event}')>"

class NotificationQueue(BaseModel, TimestampMixin):
    """Queue for processing notifications."""
    __tablename__ = "notification_queue"
    
    # Queue item info
    notification_type: Mapped[NotificationType] = mapped_column(SQLEnum(NotificationType), nullable=False)
    channel: Mapped[NotificationChannel] = mapped_column(SQLEnum(NotificationChannel), nullable=False)
    
    # Content
    subject: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Scheduling
    scheduled_for: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=5)  # 1-10, 1 is highest
    
    # Processing
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued, processing, sent, failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Additional data
    extra_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON object
    
    # Relationships
    reminder_id: Mapped[Optional[int]] = mapped_column(ForeignKey("smart_reminders.id"), nullable=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    reminder = relationship("SmartReminder")
    event = relationship("Event")
    recipient = relationship("User")
    
    def __repr__(self):
        return f"<NotificationQueue(id={self.id}, type='{self.notification_type}', status='{self.status}')>"
    
    @property
    def is_ready_to_send(self) -> bool:
        """Check if notification is ready to be sent."""
        return (
            self.status == "queued" and
            datetime.utcnow() >= self.scheduled_for and
            self.attempts < self.max_attempts
        )
    
    @property
    def should_retry(self) -> bool:
        """Check if failed notification should be retried."""
        return (
            self.status == "failed" and
            self.attempts < self.max_attempts and
            (not self.last_attempt_at or 
             datetime.utcnow() - self.last_attempt_at > timedelta(minutes=30))
        )