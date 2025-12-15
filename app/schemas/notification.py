from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.notification_models import (
    NotificationType, NotificationStatus, NotificationChannel, ReminderFrequency
)

# Base schemas
class UserBasic(BaseModel):
    """Basic user info for notification responses."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    full_name: str
    email: str
    avatar_url: Optional[str] = None

# Smart Reminder schemas
class SmartReminderBase(BaseModel):
    """Base smart reminder schema."""
    title: str = Field(..., min_length=1, max_length=200, description="Reminder title")
    message: str = Field(..., min_length=1, max_length=1000, description="Reminder message")
    notification_type: NotificationType = Field(..., description="Type of notification")
    scheduled_time: datetime = Field(..., description="When to send the reminder")
    frequency: ReminderFrequency = Field(default=ReminderFrequency.ONCE, description="Reminder frequency")
    recurrence_count: int = Field(default=1, ge=1, le=10, description="Number of times to repeat")
    target_all_guests: bool = Field(default=False, description="Send to all event guests")
    target_specific_users: Optional[List[int]] = Field(None, description="Specific user IDs to target")
    target_rsvp_status: Optional[str] = Field(None, description="Filter by RSVP status")
    send_email: bool = Field(default=True, description="Send via email")
    send_sms: bool = Field(default=False, description="Send via SMS")
    send_push: bool = Field(default=True, description="Send push notification")
    send_in_app: bool = Field(default=True, description="Send in-app notification")

class SmartReminderCreate(SmartReminderBase):
    """Schema for creating a smart reminder."""
    pass

class SmartReminderUpdate(BaseModel):
    """Schema for updating a smart reminder."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    message: Optional[str] = Field(None, min_length=1, max_length=1000)
    scheduled_time: Optional[datetime] = None
    frequency: Optional[ReminderFrequency] = None
    recurrence_count: Optional[int] = Field(None, ge=1, le=10)
    is_active: Optional[bool] = None
    target_all_guests: Optional[bool] = None
    target_specific_users: Optional[List[int]] = None
    target_rsvp_status: Optional[str] = None
    send_email: Optional[bool] = None
    send_sms: Optional[bool] = None
    send_push: Optional[bool] = None
    send_in_app: Optional[bool] = None

class SmartReminderResponse(SmartReminderBase):
    """Schema for smart reminder response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    event_id: int
    creator: UserBasic
    status: NotificationStatus
    is_active: bool
    auto_generated: bool
    recurrence_sent: int
    sent_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

# Notification Preference schemas
class NotificationPreferenceBase(BaseModel):
    """Base notification preference schema."""
    notification_type: NotificationType = Field(..., description="Type of notification")
    email_enabled: bool = Field(default=True, description="Enable email notifications")
    sms_enabled: bool = Field(default=False, description="Enable SMS notifications")
    push_enabled: bool = Field(default=True, description="Enable push notifications")
    in_app_enabled: bool = Field(default=True, description="Enable in-app notifications")
    advance_notice_hours: int = Field(default=24, ge=1, le=168, description="Hours before event")
    quiet_hours_start: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', description="Quiet hours start (HH:MM)")
    quiet_hours_end: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', description="Quiet hours end (HH:MM)")
    max_daily_notifications: int = Field(default=10, ge=1, le=50, description="Max notifications per day")

class NotificationPreferenceCreate(NotificationPreferenceBase):
    """Schema for creating notification preferences."""
    pass

class NotificationPreferenceResponse(NotificationPreferenceBase):
    """Schema for notification preference response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

# Reminder Template schemas
class ReminderTemplateBase(BaseModel):
    """Base reminder template schema."""
    name: str = Field(..., min_length=1, max_length=200, description="Template name")
    description: Optional[str] = Field(None, max_length=1000, description="Template description")
    notification_type: NotificationType = Field(..., description="Type of notification")
    subject_template: str = Field(..., min_length=1, max_length=200, description="Subject template")
    message_template: str = Field(..., min_length=1, max_length=2000, description="Message template")
    default_advance_hours: int = Field(default=24, ge=1, le=168, description="Default advance notice")
    default_frequency: ReminderFrequency = Field(default=ReminderFrequency.ONCE, description="Default frequency")
    template_variables: Optional[List[str]] = Field(None, description="Available template variables")

class ReminderTemplateCreate(ReminderTemplateBase):
    """Schema for creating a reminder template."""
    pass

class ReminderTemplateUpdate(BaseModel):
    """Schema for updating a reminder template."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    subject_template: Optional[str] = Field(None, min_length=1, max_length=200)
    message_template: Optional[str] = Field(None, min_length=1, max_length=2000)
    is_active: Optional[bool] = None
    default_advance_hours: Optional[int] = Field(None, ge=1, le=168)
    default_frequency: Optional[ReminderFrequency] = None
    template_variables: Optional[List[str]] = None

class ReminderTemplateResponse(ReminderTemplateBase):
    """Schema for reminder template response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    creator: Optional[UserBasic] = None
    is_system_template: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

# Notification Log schemas
class NotificationLogResponse(BaseModel):
    """Schema for notification log response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    notification_type: NotificationType
    channel: NotificationChannel
    subject: Optional[str] = None
    message: str
    status: NotificationStatus
    sent_at: datetime
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    error_message: Optional[str] = None
    recipient: UserBasic

# Analytics schemas
class NotificationAnalytics(BaseModel):
    """Schema for notification analytics."""
    total_sent: int
    delivery_rate: float
    by_type: Dict[str, int]
    by_channel: Dict[str, int]
    by_status: Dict[str, int]
    period_days: int

# Bulk operations
class BulkReminderCreate(BaseModel):
    """Schema for bulk creating reminders."""
    reminders: List[SmartReminderCreate] = Field(..., min_items=1, max_items=10)

class BulkPreferenceUpdate(BaseModel):
    """Schema for bulk updating preferences."""
    preferences: List[NotificationPreferenceCreate] = Field(..., min_items=1, max_items=20)

# Search and filter schemas
class ReminderSearchParams(BaseModel):
    """Schema for reminder search parameters."""
    notification_type: Optional[NotificationType] = None
    status: Optional[NotificationStatus] = None
    is_active: Optional[bool] = None
    auto_generated: Optional[bool] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)

# List response schemas
class ReminderListResponse(BaseModel):
    """Schema for paginated reminder list."""
    reminders: List[SmartReminderResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool

class TemplateListResponse(BaseModel):
    """Schema for paginated template list."""
    templates: List[ReminderTemplateResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool

class NotificationLogListResponse(BaseModel):
    """Schema for paginated notification log list."""
    logs: List[NotificationLogResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool

class UserNotificationListResponse(BaseModel):
    """Schema for user notification list."""
    notifications: List[NotificationLogResponse]
    total: int
    unread_count: int
    limit: int

# Test notification schema
class TestNotificationRequest(BaseModel):
    """Schema for testing notifications."""
    notification_type: NotificationType
    channel: NotificationChannel
    recipient_email: str = Field(..., description="Email to send test notification")
    subject: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=1000)

# Automation rule schemas
class AutomationRuleBase(BaseModel):
    """Base automation rule schema."""
    name: str = Field(..., min_length=1, max_length=200, description="Rule name")
    description: Optional[str] = Field(None, max_length=1000, description="Rule description")
    trigger_event: str = Field(..., description="Event that triggers the rule")
    trigger_conditions: Optional[Dict[str, Any]] = Field(None, description="Trigger conditions")
    notification_type: NotificationType = Field(..., description="Type of notification to send")
    template_id: int = Field(..., description="Template to use")
    delay_hours: int = Field(default=0, ge=0, le=168, description="Delay after trigger")
    advance_hours: int = Field(default=24, ge=1, le=168, description="Hours before event")
    is_active: bool = Field(default=True, description="Whether rule is active")
    apply_to_all_events: bool = Field(default=False, description="Apply to all events")

class AutomationRuleCreate(AutomationRuleBase):
    """Schema for creating automation rules."""
    pass

class AutomationRuleUpdate(BaseModel):
    """Schema for updating automation rules."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    trigger_conditions: Optional[Dict[str, Any]] = None
    delay_hours: Optional[int] = Field(None, ge=0, le=168)
    advance_hours: Optional[int] = Field(None, ge=1, le=168)
    is_active: Optional[bool] = None
    apply_to_all_events: Optional[bool] = None

class AutomationRuleResponse(AutomationRuleBase):
    """Schema for automation rule response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    creator: UserBasic
    template: ReminderTemplateResponse
    created_at: datetime
    updated_at: datetime

# In-App Notification schemas
class InAppNotificationResponse(BaseModel):
    """Schema for in-app notification response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = None
    type: str = Field(..., description="Notification type")
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    notification_type: str = Field(..., description="Category of notification")
    event_id: Optional[int] = Field(None, description="Associated event ID")
    timestamp: datetime = Field(..., description="When notification was created")
    priority: int = Field(default=5, ge=1, le=10, description="Notification priority")
    read: bool = Field(default=False, description="Whether notification has been read")

class InAppNotificationListResponse(BaseModel):
    """Schema for paginated in-app notifications."""
    notifications: List[InAppNotificationResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool
    unread_count: int

class MarkNotificationReadRequest(BaseModel):
    """Schema for marking notifications as read."""
    notification_ids: List[int] = Field(..., min_items=1, description="List of notification IDs to mark as read")

# Device Management schemas
class DeviceRegistrationRequest(BaseModel):
    """Schema for device registration."""
    device_token: str = Field(..., min_length=1, description="FCM device token")
    device_type: str = Field(..., description="Device type (ios/android)")
    device_name: Optional[str] = Field(None, description="Device name")
    app_version: Optional[str] = Field(None, description="App version")

class DeviceResponse(BaseModel):
    """Schema for device response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    device_token: str
    device_type: str
    device_name: Optional[str] = None
    app_version: Optional[str] = None
    is_active: bool
    last_used: Optional[datetime] = None
    created_at: datetime

# Queue status schema
class NotificationQueueStatus(BaseModel):
    """Schema for notification queue status."""
    queued_count: int
    processing_count: int
    sent_count: int
    failed_count: int
    next_scheduled: Optional[datetime] = None
    last_processed: Optional[datetime] = None

class WebSocketStatsResponse(BaseModel):
    """Schema for WebSocket connection statistics."""
    total_connections: int
    active_connections: int
    connections_by_user: Dict[str, int]
    total_messages_sent: int
    uptime_seconds: int