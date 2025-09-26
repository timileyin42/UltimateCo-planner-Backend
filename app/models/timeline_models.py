from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLEnum, Time, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from datetime import datetime, time, timedelta
from typing import Optional, List
from app.models.shared_models import BaseModel, TimestampMixin
import enum

class TimelineItemType(str, enum.Enum):
    """Types of timeline items."""
    SETUP = "setup"
    ARRIVAL = "arrival"
    ACTIVITY = "activity"
    MEAL = "meal"
    ENTERTAINMENT = "entertainment"
    SPEECH = "speech"
    CEREMONY = "ceremony"
    BREAK = "break"
    CLEANUP = "cleanup"
    DEPARTURE = "departure"
    CUSTOM = "custom"

class TimelineStatus(str, enum.Enum):
    """Status of timeline items."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    DELAYED = "delayed"

class EventTimeline(BaseModel, TimestampMixin):
    """Main timeline for an event."""
    __tablename__ = "event_timelines"
    
    # Basic info
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timeline settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timing
    start_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    end_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    total_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Buffer settings
    default_buffer_minutes: Mapped[int] = mapped_column(Integer, default=15)
    setup_buffer_minutes: Mapped[int] = mapped_column(Integer, default=30)
    cleanup_buffer_minutes: Mapped[int] = mapped_column(Integer, default=30)
    
    # Relationships
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    event = relationship("Event", back_populates="timelines")
    creator = relationship("User", foreign_keys=[creator_id], back_populates="created_timelines")
    items = relationship("TimelineItem", back_populates="timeline", cascade="all, delete-orphan", order_by="TimelineItem.start_time")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_event_timeline_event_id', 'event_id'),
        Index('idx_event_timeline_creator_id', 'creator_id'),
        Index('idx_event_timeline_is_active', 'is_active'),
        Index('idx_event_timeline_is_template', 'is_template'),
        Index('idx_event_timeline_auto_generated', 'auto_generated'),
        Index('idx_event_timeline_start_time', 'start_time'),
        Index('idx_event_timeline_end_time', 'end_time'),
        Index('idx_event_timeline_created_at', 'created_at'),
        Index('idx_event_timeline_updated_at', 'updated_at'),
        
        # Combined indexes for common queries
        Index('idx_event_timeline_event_active', 'event_id', 'is_active'),
        Index('idx_event_timeline_creator_created', 'creator_id', 'created_at'),
        Index('idx_event_timeline_event_template', 'event_id', 'is_template'),
        Index('idx_event_timeline_active_template', 'is_active', 'is_template'),
    )
    
    def __repr__(self):
        return f"<EventTimeline(id={self.id}, title='{self.title}', event_id={self.event_id})>"
    
    @property
    def item_count(self) -> int:
        """Get number of items in timeline."""
        return len(self.items) if self.items else 0
    
    @property
    def completion_percentage(self) -> float:
        """Get completion percentage of timeline."""
        if not self.items:
            return 0.0
        
        completed_items = sum(1 for item in self.items if item.status == TimelineStatus.COMPLETED)
        return (completed_items / len(self.items)) * 100

class TimelineItem(BaseModel, TimestampMixin):
    """Individual items within a timeline."""
    __tablename__ = "timeline_items"
    
    # Basic info
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    item_type: Mapped[TimelineItemType] = mapped_column(SQLEnum(TimelineItemType), nullable=False)
    
    # Timing
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    buffer_minutes: Mapped[int] = mapped_column(Integer, default=0)
    
    # Status and tracking
    status: Mapped[TimelineStatus] = mapped_column(SQLEnum(TimelineStatus), default=TimelineStatus.PENDING)
    actual_start_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    actual_end_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    
    # Organization
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    is_flexible: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Requirements and notes
    requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    # Relationships
    timeline_id: Mapped[int] = mapped_column(ForeignKey("event_timelines.id"), nullable=False)
    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    
    # Relationships
    timeline = relationship("EventTimeline", back_populates="items")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id], back_populates="assigned_timeline_items")
    task = relationship("Task", back_populates="timeline_items")
    dependencies = relationship("TimelineDependency", foreign_keys="TimelineDependency.item_id", back_populates="item")
    dependent_items = relationship("TimelineDependency", foreign_keys="TimelineDependency.depends_on_id", back_populates="depends_on")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_timeline_item_timeline_id', 'timeline_id'),
        Index('idx_timeline_item_assigned_to_id', 'assigned_to_id'),
        Index('idx_timeline_item_task_id', 'task_id'),
        Index('idx_timeline_item_type', 'item_type'),
        Index('idx_timeline_item_status', 'status'),
        Index('idx_timeline_item_start_time', 'start_time'),
        Index('idx_timeline_item_end_time', 'end_time'),
        Index('idx_timeline_item_order_index', 'order_index'),
        Index('idx_timeline_item_is_critical', 'is_critical'),
        Index('idx_timeline_item_is_flexible', 'is_flexible'),
        Index('idx_timeline_item_created_at', 'created_at'),
        Index('idx_timeline_item_updated_at', 'updated_at'),
        
        # Combined indexes for common queries
        Index('idx_timeline_item_timeline_order', 'timeline_id', 'order_index'),
        Index('idx_timeline_item_timeline_start', 'timeline_id', 'start_time'),
        Index('idx_timeline_item_timeline_status', 'timeline_id', 'status'),
        Index('idx_timeline_item_assigned_status', 'assigned_to_id', 'status'),
        Index('idx_timeline_item_type_status', 'item_type', 'status'),
        Index('idx_timeline_item_critical_status', 'is_critical', 'status'),
        Index('idx_timeline_item_timeline_critical', 'timeline_id', 'is_critical'),
    )
    
    def __repr__(self):
        return f"<TimelineItem(id={self.id}, title='{self.title}', start_time='{self.start_time}')>"
    
    @property
    def is_overdue(self) -> bool:
        """Check if item is overdue based on current time."""
        if self.status in [TimelineStatus.COMPLETED, TimelineStatus.SKIPPED]:
            return False
        

        current_time = datetime.now().time()
        return current_time > self.end_time if self.end_time else current_time > self.start_time
    
    @property
    def actual_duration_minutes(self) -> Optional[int]:
        """Get actual duration if both start and end times are recorded."""
        if not (self.actual_start_time and self.actual_end_time):
            return None
        

        start_dt = datetime.combine(datetime.today(), self.actual_start_time)
        end_dt = datetime.combine(datetime.today(), self.actual_end_time)
        
        # Handle overnight events
        if end_dt < start_dt:
            end_dt += timedelta(days=1)
        
        return int((end_dt - start_dt).total_seconds() / 60)

class TimelineDependency(BaseModel, TimestampMixin):
    """Dependencies between timeline items."""
    __tablename__ = "timeline_dependencies"
    
    # Dependency info
    dependency_type: Mapped[str] = mapped_column(String(50), default="finish_to_start")  # finish_to_start, start_to_start, etc.
    lag_minutes: Mapped[int] = mapped_column(Integer, default=0)  # Delay between dependent items
    
    # Relationships
    item_id: Mapped[int] = mapped_column(ForeignKey("timeline_items.id"), nullable=False)
    depends_on_id: Mapped[int] = mapped_column(ForeignKey("timeline_items.id"), nullable=False)
    
    # Relationships
    item = relationship("TimelineItem", foreign_keys=[item_id], back_populates="dependencies")
    depends_on = relationship("TimelineItem", foreign_keys=[depends_on_id], back_populates="dependent_items")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_timeline_dependency_item_id', 'item_id'),
        Index('idx_timeline_dependency_depends_on_id', 'depends_on_id'),
        Index('idx_timeline_dependency_type', 'dependency_type'),
        Index('idx_timeline_dependency_created_at', 'created_at'),
        
        # Combined indexes for common queries
        Index('idx_timeline_dependency_item_depends', 'item_id', 'depends_on_id'),
        Index('idx_timeline_dependency_type_item', 'dependency_type', 'item_id'),
    )
    
    def __repr__(self):
        return f"<TimelineDependency(item_id={self.item_id}, depends_on_id={self.depends_on_id})>"

class TimelineTemplate(BaseModel, TimestampMixin):
    """Reusable timeline templates for different event types."""
    __tablename__ = "timeline_templates"
    
    # Basic info
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)  # birthday, wedding, etc.
    
    # Template settings
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timing defaults
    default_duration_hours: Mapped[int] = mapped_column(Integer, default=4)
    setup_time_minutes: Mapped[int] = mapped_column(Integer, default=60)
    cleanup_time_minutes: Mapped[int] = mapped_column(Integer, default=30)
    
    # Template data (JSON)
    template_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON structure of timeline items
    
    # Relationships
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    creator = relationship("User", foreign_keys=[creator_id], back_populates="created_timeline_templates")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_timeline_template_creator_id', 'creator_id'),
        Index('idx_timeline_template_event_type', 'event_type'),
        Index('idx_timeline_template_is_public', 'is_public'),
        Index('idx_timeline_template_is_verified', 'is_verified'),
        Index('idx_timeline_template_usage_count', 'usage_count'),
        Index('idx_timeline_template_created_at', 'created_at'),
        Index('idx_timeline_template_updated_at', 'updated_at'),
        
        # Combined indexes for common queries
        Index('idx_timeline_template_public_type', 'is_public', 'event_type'),
        Index('idx_timeline_template_verified_public', 'is_verified', 'is_public'),
        Index('idx_timeline_template_creator_type', 'creator_id', 'event_type'),
        Index('idx_timeline_template_usage_public', 'usage_count', 'is_public'),
    )
    
    def __repr__(self):
        return f"<TimelineTemplate(id={self.id}, name='{self.name}', event_type='{self.event_type}')>"

class TimelineNotification(BaseModel, TimestampMixin):
    """Notifications for timeline items."""
    __tablename__ = "timeline_notifications"
    
    # Notification info
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)  # reminder, delay_alert, completion
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Timing
    scheduled_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Settings
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    send_email: Mapped[bool] = mapped_column(Boolean, default=True)
    send_push: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    timeline_item_id: Mapped[int] = mapped_column(ForeignKey("timeline_items.id"), nullable=False)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    timeline_item = relationship("TimelineItem")
    recipient = relationship("User", back_populates="timeline_notifications")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_timeline_notification_timeline_item_id', 'timeline_item_id'),
        Index('idx_timeline_notification_recipient_id', 'recipient_id'),
        Index('idx_timeline_notification_type', 'notification_type'),
        Index('idx_timeline_notification_scheduled_time', 'scheduled_time'),
        Index('idx_timeline_notification_sent_at', 'sent_at'),
        Index('idx_timeline_notification_is_sent', 'is_sent'),
        Index('idx_timeline_notification_created_at', 'created_at'),
        
        # Combined indexes for common queries
        Index('idx_timeline_notification_recipient_sent', 'recipient_id', 'is_sent'),
        Index('idx_timeline_notification_scheduled_sent', 'scheduled_time', 'is_sent'),
        Index('idx_timeline_notification_type_sent', 'notification_type', 'is_sent'),
        Index('idx_timeline_notification_item_recipient', 'timeline_item_id', 'recipient_id'),
    )
    
    def __repr__(self):
        return f"<TimelineNotification(id={self.id}, type='{self.notification_type}', sent={self.is_sent})>"

class TimelineUpdate(BaseModel, TimestampMixin):
    """Track updates and changes to timeline items."""
    __tablename__ = "timeline_updates"
    
    # Update info
    update_type: Mapped[str] = mapped_column(String(50), nullable=False)  # status_change, time_change, etc.
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    timeline_item_id: Mapped[int] = mapped_column(ForeignKey("timeline_items.id"), nullable=False)
    updated_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    timeline_item = relationship("TimelineItem")
    updated_by = relationship("User", back_populates="timeline_updates")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_timeline_update_timeline_item_id', 'timeline_item_id'),
        Index('idx_timeline_update_updated_by_id', 'updated_by_id'),
        Index('idx_timeline_update_type', 'update_type'),
        Index('idx_timeline_update_created_at', 'created_at'),
        
        # Combined indexes for common queries
        Index('idx_timeline_update_item_type', 'timeline_item_id', 'update_type'),
        Index('idx_timeline_update_item_created', 'timeline_item_id', 'created_at'),
        Index('idx_timeline_update_user_created', 'updated_by_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<TimelineUpdate(id={self.id}, type='{self.update_type}', item_id={self.timeline_item_id})>"