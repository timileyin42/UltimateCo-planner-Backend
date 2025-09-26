"""
Calendar integration database models.
Defines SQLAlchemy models for calendar connections and sync data.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class CalendarProviderEnum(str, enum.Enum):
    """Calendar provider enumeration."""
    GOOGLE = "google"
    APPLE = "apple"
    OUTLOOK = "outlook"


class SyncStatusEnum(str, enum.Enum):
    """Sync status enumeration."""
    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"
    DISABLED = "disabled"


class CalendarConnection(Base):
    """
    Calendar connection model.
    Stores user's calendar provider connections and authentication data.
    """
    __tablename__ = "calendar_connections"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Provider information
    provider = Column(SQLEnum(CalendarProviderEnum), nullable=False)
    calendar_id = Column(String(255), nullable=False)  # External calendar ID
    calendar_name = Column(String(255), nullable=False)
    
    # Authentication data
    access_token = Column(Text, nullable=False)  # OAuth access token or Apple ID
    refresh_token = Column(Text, nullable=True)  # OAuth refresh token or app password
    expires_at = Column(DateTime, nullable=True)  # Token expiration (None for Apple)
    
    # Sync settings
    sync_enabled = Column(Boolean, default=True, nullable=False)
    sync_status = Column(SQLEnum(SyncStatusEnum), default=SyncStatusEnum.PENDING, nullable=False)
    last_sync_at = Column(DateTime, nullable=True)
    sync_error_message = Column(Text, nullable=True)
    sync_error_count = Column(Integer, default=0, nullable=False)
    
    # Sync configuration
    sync_direction = Column(String(20), default="bidirectional", nullable=False)  # bidirectional, import_only, export_only
    auto_sync_enabled = Column(Boolean, default=True, nullable=False)
    sync_frequency_minutes = Column(Integer, default=15, nullable=False)  # Sync frequency in minutes
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="calendar_connections")
    calendar_events = relationship("CalendarEvent", back_populates="calendar_connection", cascade="all, delete-orphan")
    sync_logs = relationship("CalendarSyncLog", back_populates="calendar_connection", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_calendar_connections_user_id", "user_id"),
        Index("idx_calendar_connections_provider", "provider"),
        Index("idx_calendar_connections_sync_status", "sync_status"),
        Index("idx_calendar_connections_user_provider", "user_id", "provider"),
        # Additional strategic indexes
        Index("idx_calendar_connections_sync_enabled", "sync_enabled"),
        Index("idx_calendar_connections_last_sync_at", "last_sync_at"),
        Index("idx_calendar_connections_expires_at", "expires_at"),
        Index("idx_calendar_connections_sync_enabled_status", "sync_enabled", "sync_status"),
        Index("idx_calendar_connections_user_sync_enabled", "user_id", "sync_enabled"),
    )
    
    def __repr__(self):
        return f"<CalendarConnection(id={self.id}, user_id={self.user_id}, provider={self.provider}, calendar_name='{self.calendar_name}')>"


class CalendarEvent(Base):
    """
    Calendar event model.
    Stores events that are synced with external calendars.
    """
    __tablename__ = "calendar_events"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    calendar_connection_id = Column(Integer, ForeignKey("calendar_connections.id", ondelete="CASCADE"), nullable=True)
    
    # Event data
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(500), nullable=True)
    
    # Time information
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    all_day = Column(Boolean, default=False, nullable=False)
    timezone = Column(String(50), default="UTC", nullable=False)
    
    # Recurrence
    recurrence_rule = Column(String(500), nullable=True)  # RRULE format
    recurrence_parent_id = Column(Integer, ForeignKey("calendar_events.id"), nullable=True)
    
    # External sync data
    external_event_id = Column(String(255), nullable=True)  # External calendar event ID
    external_etag = Column(String(255), nullable=True)  # For change detection
    
    # Sync status
    sync_status = Column(SQLEnum(SyncStatusEnum), default=SyncStatusEnum.PENDING, nullable=False)
    last_synced_at = Column(DateTime, nullable=True)
    sync_error_message = Column(Text, nullable=True)
    
    # Event metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="calendar_events")
    calendar_connection = relationship("CalendarConnection", back_populates="calendar_events")
    recurrence_parent = relationship("CalendarEvent", remote_side=[id], back_populates="recurrence_instances")
    recurrence_instances = relationship("CalendarEvent", back_populates="recurrence_parent")
    attendees = relationship("CalendarEventAttendee", back_populates="calendar_event", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_calendar_events_user_id", "user_id"),
        Index("idx_calendar_events_connection_id", "calendar_connection_id"),
        Index("idx_calendar_events_start_time", "start_time"),
        Index("idx_calendar_events_external_id", "external_event_id"),
        Index("idx_calendar_events_sync_status", "sync_status"),
        Index("idx_calendar_events_user_time", "user_id", "start_time"),
        # Additional strategic indexes
        Index("idx_calendar_events_end_time", "end_time"),
        Index("idx_calendar_events_all_day", "all_day"),
        Index("idx_calendar_events_recurrence_parent_id", "recurrence_parent_id"),
        Index("idx_calendar_events_last_synced_at", "last_synced_at"),
        Index("idx_calendar_events_user_end_time", "user_id", "end_time"),
        Index("idx_calendar_events_external_connection", "external_event_id", "calendar_connection_id"),
        Index("idx_calendar_events_time_range", "start_time", "end_time"),
    )
    
    def __repr__(self):
        return f"<CalendarEvent(id={self.id}, title='{self.title}', start_time={self.start_time})>"


class CalendarEventAttendee(Base):
    """
    Calendar event attendee model.
    Stores attendee information for calendar events.
    """
    __tablename__ = "calendar_event_attendees"
    
    id = Column(Integer, primary_key=True, index=True)
    calendar_event_id = Column(Integer, ForeignKey("calendar_events.id", ondelete="CASCADE"), nullable=False)
    
    # Attendee information
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    response_status = Column(String(20), default="needsAction", nullable=False)  # needsAction, accepted, declined, tentative
    is_organizer = Column(Boolean, default=False, nullable=False)
    is_optional = Column(Boolean, default=False, nullable=False)
    
    # External data
    external_attendee_id = Column(String(255), nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    calendar_event = relationship("CalendarEvent", back_populates="attendees")
    
    # Indexes
    __table_args__ = (
        Index("idx_calendar_event_attendees_event_id", "calendar_event_id"),
        Index("idx_calendar_event_attendees_email", "email"),
        # Additional strategic indexes
        Index("idx_calendar_event_attendees_response_status", "response_status"),
        Index("idx_calendar_event_attendees_is_organizer", "is_organizer"),
        Index("idx_calendar_event_attendees_event_response", "calendar_event_id", "response_status"),
    )
    
    def __repr__(self):
        return f"<CalendarEventAttendee(id={self.id}, email='{self.email}', response_status='{self.response_status}')>"


class CalendarSyncLog(Base):
    """
    Calendar sync log model.
    Stores sync operation logs for debugging and monitoring.
    """
    __tablename__ = "calendar_sync_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    calendar_connection_id = Column(Integer, ForeignKey("calendar_connections.id", ondelete="CASCADE"), nullable=False)
    
    # Sync operation details
    sync_type = Column(String(20), nullable=False)  # full, incremental, manual
    sync_direction = Column(String(20), nullable=False)  # import, export, bidirectional
    sync_status = Column(SQLEnum(SyncStatusEnum), nullable=False)
    
    # Sync results
    events_processed = Column(Integer, default=0, nullable=False)
    events_created = Column(Integer, default=0, nullable=False)
    events_updated = Column(Integer, default=0, nullable=False)
    events_deleted = Column(Integer, default=0, nullable=False)
    events_skipped = Column(Integer, default=0, nullable=False)
    
    # Time tracking
    sync_started_at = Column(DateTime, nullable=False)
    sync_completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Error information
    error_message = Column(Text, nullable=True)
    error_details = Column(Text, nullable=True)  # JSON formatted error details
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    calendar_connection = relationship("CalendarConnection", back_populates="sync_logs")
    
    # Indexes
    __table_args__ = (
        Index("idx_calendar_sync_logs_connection_id", "calendar_connection_id"),
        Index("idx_calendar_sync_logs_status", "sync_status"),
        Index("idx_calendar_sync_logs_started_at", "sync_started_at"),
        # Additional strategic indexes
        Index("idx_calendar_sync_logs_completed_at", "sync_completed_at"),
        Index("idx_calendar_sync_logs_sync_type", "sync_type"),
        Index("idx_calendar_sync_logs_connection_started", "calendar_connection_id", "sync_started_at"),
        Index("idx_calendar_sync_logs_status_started", "sync_status", "sync_started_at"),
    )
    
    def __repr__(self):
        return f"<CalendarSyncLog(id={self.id}, connection_id={self.calendar_connection_id}, status='{self.sync_status}')>"


class CalendarWebhook(Base):
    """
    Calendar webhook model.
    Stores webhook configurations for real-time calendar updates.
    """
    __tablename__ = "calendar_webhooks"
    
    id = Column(Integer, primary_key=True, index=True)
    calendar_connection_id = Column(Integer, ForeignKey("calendar_connections.id", ondelete="CASCADE"), nullable=False)
    
    # Webhook configuration
    webhook_id = Column(String(255), nullable=False)  # External webhook ID
    webhook_url = Column(String(500), nullable=False)  # Our webhook endpoint URL
    resource_id = Column(String(255), nullable=False)  # External resource ID being watched
    resource_uri = Column(String(500), nullable=False)  # External resource URI
    
    # Webhook status
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # Webhook expiration time
    last_notification_at = Column(DateTime, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    calendar_connection = relationship("CalendarConnection")
    
    # Indexes
    __table_args__ = (
        Index("idx_calendar_webhooks_connection_id", "calendar_connection_id"),
        Index("idx_calendar_webhooks_webhook_id", "webhook_id"),
        Index("idx_calendar_webhooks_active", "is_active"),
        # Additional strategic indexes
        Index("idx_calendar_webhooks_expires_at", "expires_at"),
        Index("idx_calendar_webhooks_active_expires", "is_active", "expires_at"),
    )
    
    def __repr__(self):
        return f"<CalendarWebhook(id={self.id}, webhook_id='{self.webhook_id}', is_active={self.is_active})>"