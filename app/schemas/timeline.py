from pydantic import BaseModel, Field, ConfigDict, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, time
from app.models.timeline_models import (
    TimelineItemType, TimelineStatus
)

# Base schemas
class UserBasic(BaseModel):
    """Basic user info for timeline responses."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    full_name: str
    username: Optional[str] = None
    avatar_url: Optional[str] = None

# Timeline schemas
class EventTimelineBase(BaseModel):
    """Base event timeline schema."""
    title: str = Field(..., min_length=1, max_length=200, description="Timeline title")
    description: Optional[str] = Field(None, max_length=1000, description="Timeline description")
    is_active: bool = Field(default=True, description="Whether timeline is active")
    start_time: Optional[time] = Field(None, description="Timeline start time")
    end_time: Optional[time] = Field(None, description="Timeline end time")
    default_buffer_minutes: int = Field(default=15, ge=0, le=120, description="Default buffer between items")
    setup_buffer_minutes: int = Field(default=30, ge=0, le=180, description="Setup time before event")
    cleanup_buffer_minutes: int = Field(default=30, ge=0, le=180, description="Cleanup time after event")

class EventTimelineCreate(EventTimelineBase):
    """Schema for creating an event timeline."""
    pass

class EventTimelineUpdate(BaseModel):
    """Schema for updating an event timeline."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    default_buffer_minutes: Optional[int] = Field(None, ge=0, le=120)
    setup_buffer_minutes: Optional[int] = Field(None, ge=0, le=180)
    cleanup_buffer_minutes: Optional[int] = Field(None, ge=0, le=180)

# Timeline item schemas
class TimelineItemBase(BaseModel):
    """Base timeline item schema."""
    title: str = Field(..., min_length=1, max_length=200, description="Item title")
    description: Optional[str] = Field(None, max_length=1000, description="Item description")
    item_type: TimelineItemType = Field(..., description="Type of timeline item")
    start_time: time = Field(..., description="Start time")
    end_time: Optional[time] = Field(None, description="End time")
    duration_minutes: int = Field(..., ge=1, le=1440, description="Duration in minutes")
    buffer_minutes: int = Field(default=0, ge=0, le=120, description="Buffer time after item")
    is_critical: bool = Field(default=False, description="Whether item is critical")
    is_flexible: bool = Field(default=True, description="Whether timing is flexible")
    requirements: Optional[List[str]] = Field(None, description="Requirements for this item")
    notes: Optional[str] = Field(None, description="Additional notes")
    location: Optional[str] = Field(None, max_length=200, description="Location for this item")
    assigned_to_id: Optional[int] = Field(None, description="User assigned to this item")
    task_id: Optional[int] = Field(None, description="Related task ID")

class TimelineItemCreate(TimelineItemBase):
    """Schema for creating a timeline item."""
    order_index: Optional[int] = Field(None, description="Position in timeline")
    
    @validator('end_time')
    def validate_end_time(cls, v, values):
        if v and 'start_time' in values and v <= values['start_time']:
            raise ValueError('End time must be after start time')
        return v

class TimelineItemUpdate(BaseModel):
    """Schema for updating a timeline item."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    item_type: Optional[TimelineItemType] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    duration_minutes: Optional[int] = Field(None, ge=1, le=1440)
    buffer_minutes: Optional[int] = Field(None, ge=0, le=120)
    status: Optional[TimelineStatus] = None
    is_critical: Optional[bool] = None
    is_flexible: Optional[bool] = None
    requirements: Optional[List[str]] = None
    notes: Optional[str] = None
    location: Optional[str] = Field(None, max_length=200)
    assigned_to_id: Optional[int] = None
    task_id: Optional[int] = None
    order_index: Optional[int] = None

class TimelineItemStatusUpdate(BaseModel):
    """Schema for updating timeline item status."""
    status: TimelineStatus = Field(..., description="New status")
    actual_start_time: Optional[time] = Field(None, description="Actual start time")
    actual_end_time: Optional[time] = Field(None, description="Actual end time")
    notes: Optional[str] = Field(None, description="Status update notes")

class TimelineItemResponse(TimelineItemBase):
    """Schema for timeline item response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    timeline_id: int
    status: TimelineStatus
    order_index: int
    actual_start_time: Optional[time] = None
    actual_end_time: Optional[time] = None
    assigned_to: Optional[UserBasic] = None
    is_overdue: bool
    actual_duration_minutes: Optional[int] = None
    created_at: datetime
    updated_at: datetime

class EventTimelineResponse(EventTimelineBase):
    """Schema for event timeline response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    event_id: int
    creator: UserBasic
    auto_generated: bool
    total_duration_minutes: Optional[int] = None
    item_count: int
    completion_percentage: float
    created_at: datetime
    updated_at: datetime
    items: List[TimelineItemResponse] = []

# Timeline template schemas
class TimelineTemplateBase(BaseModel):
    """Base timeline template schema."""
    name: str = Field(..., min_length=1, max_length=200, description="Template name")
    description: Optional[str] = Field(None, max_length=1000, description="Template description")
    event_type: str = Field(..., description="Event type this template is for")
    is_public: bool = Field(default=False, description="Whether template is public")
    default_duration_hours: int = Field(default=4, ge=1, le=24, description="Default event duration")
    setup_time_minutes: int = Field(default=60, ge=0, le=300, description="Setup time")
    cleanup_time_minutes: int = Field(default=30, ge=0, le=180, description="Cleanup time")

class TimelineTemplateCreate(TimelineTemplateBase):
    """Schema for creating a timeline template."""
    template_data: Dict[str, Any] = Field(..., description="Template structure data")

class TimelineTemplateUpdate(BaseModel):
    """Schema for updating a timeline template."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    event_type: Optional[str] = None
    is_public: Optional[bool] = None
    default_duration_hours: Optional[int] = Field(None, ge=1, le=24)
    setup_time_minutes: Optional[int] = Field(None, ge=0, le=300)
    cleanup_time_minutes: Optional[int] = Field(None, ge=0, le=180)
    template_data: Optional[Dict[str, Any]] = None

class TimelineTemplateResponse(TimelineTemplateBase):
    """Schema for timeline template response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    creator: UserBasic
    is_verified: bool
    usage_count: int
    created_at: datetime
    updated_at: datetime

# AI generation schemas
class AITimelineRequest(BaseModel):
    """Schema for AI timeline generation request."""
    event_type: str = Field(..., description="Type of event")
    duration_hours: int = Field(..., ge=1, le=24, description="Event duration in hours")
    guest_count: int = Field(..., ge=1, description="Number of guests")
    budget: Optional[float] = Field(None, ge=0, description="Event budget")
    venue_type: Optional[str] = Field(None, description="Type of venue")
    special_requirements: Optional[List[str]] = Field(None, description="Special requirements")
    preferences: Optional[List[str]] = Field(None, description="User preferences")
    start_time: Optional[time] = Field(None, description="Preferred start time")

class AITimelineResponse(BaseModel):
    """Schema for AI-generated timeline response."""
    timeline: Dict[str, Any] = Field(..., description="Generated timeline structure")
    suggestions: List[str] = Field(default=[], description="Additional suggestions")
    estimated_costs: Optional[Dict[str, float]] = Field(None, description="Cost estimates")
    critical_items: List[str] = Field(default=[], description="Critical timeline items")
    flexibility_notes: List[str] = Field(default=[], description="Flexibility recommendations")

# Dependency schemas
class TimelineDependencyCreate(BaseModel):
    """Schema for creating timeline dependencies."""
    depends_on_id: int = Field(..., description="ID of item this depends on")
    dependency_type: str = Field(default="finish_to_start", description="Type of dependency")
    lag_minutes: int = Field(default=0, description="Lag time in minutes")

class TimelineDependencyResponse(BaseModel):
    """Schema for timeline dependency response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    item_id: int
    depends_on_id: int
    dependency_type: str
    lag_minutes: int

# Notification schemas
class TimelineNotificationCreate(BaseModel):
    """Schema for creating timeline notifications."""
    notification_type: str = Field(..., description="Type of notification")
    message: str = Field(..., description="Notification message")
    scheduled_time: datetime = Field(..., description="When to send notification")
    send_email: bool = Field(default=True, description="Send email notification")
    send_push: bool = Field(default=True, description="Send push notification")
    recipient_id: int = Field(..., description="Recipient user ID")

class TimelineNotificationResponse(BaseModel):
    """Schema for timeline notification response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    notification_type: str
    message: str
    scheduled_time: datetime
    sent_at: Optional[datetime] = None
    is_sent: bool
    recipient: UserBasic

# Search and filter schemas
class TimelineSearchParams(BaseModel):
    """Schema for timeline search parameters."""
    query: Optional[str] = Field(None, description="Search query")
    item_type: Optional[TimelineItemType] = Field(None, description="Filter by item type")
    status: Optional[TimelineStatus] = Field(None, description="Filter by status")
    assigned_to_id: Optional[int] = Field(None, description="Filter by assignee")
    is_critical: Optional[bool] = Field(None, description="Filter critical items")
    date_from: Optional[datetime] = Field(None, description="Filter from date")
    date_to: Optional[datetime] = Field(None, description="Filter to date")
    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")

# List response schemas
class TimelineListResponse(BaseModel):
    """Schema for paginated timeline list."""
    timelines: List[EventTimelineResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool

class TimelineTemplateListResponse(BaseModel):
    """Schema for paginated timeline template list."""
    templates: List[TimelineTemplateResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool

# Statistics schemas
class TimelineStatistics(BaseModel):
    """Schema for timeline statistics."""
    total_items: int
    completed_items: int
    pending_items: int
    overdue_items: int
    completion_percentage: float
    average_item_duration: Optional[float] = None
    critical_items_count: int
    on_schedule_percentage: float
    estimated_total_duration: int  # in minutes
    actual_total_duration: Optional[int] = None  # in minutes

# Bulk operations
class BulkTimelineItemCreate(BaseModel):
    """Schema for bulk creating timeline items."""
    items: List[TimelineItemCreate] = Field(..., min_items=1, max_items=50)

class BulkTimelineItemUpdate(BaseModel):
    """Schema for bulk updating timeline items."""
    updates: List[Dict[str, Any]] = Field(..., min_items=1, max_items=50)

class TimelineReorderRequest(BaseModel):
    """Schema for reordering timeline items."""
    item_orders: List[Dict[str, int]] = Field(..., description="List of {item_id: new_order} mappings")

# Export schemas
class TimelineExportRequest(BaseModel):
    """Schema for timeline export request."""
    format: str = Field(default="pdf", description="Export format: pdf, csv, json")
    include_completed: bool = Field(default=True, description="Include completed items")
    include_notes: bool = Field(default=True, description="Include notes and requirements")
    include_assignments: bool = Field(default=True, description="Include assignee information")

class TimelineExportResponse(BaseModel):
    """Schema for timeline export response."""
    export_url: str = Field(..., description="URL to download export")
    expires_at: datetime = Field(..., description="Export expiration time")
    file_size_bytes: int = Field(..., description="Export file size")
    format: str = Field(..., description="Export format")

# Real-time update schemas
class TimelineUpdateEvent(BaseModel):
    """Schema for real-time timeline updates."""
    event_type: str = Field(..., description="Type of update")
    timeline_id: int = Field(..., description="Timeline ID")
    item_id: Optional[int] = Field(None, description="Item ID if applicable")
    data: Dict[str, Any] = Field(..., description="Update data")
    updated_by: UserBasic = Field(..., description="User who made the update")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Update timestamp")

# Progress tracking
class TimelineProgress(BaseModel):
    """Schema for timeline progress tracking."""
    timeline_id: int
    total_items: int
    completed_items: int
    in_progress_items: int
    pending_items: int
    overdue_items: int
    completion_percentage: float
    estimated_completion_time: Optional[datetime] = None
    current_item: Optional[TimelineItemResponse] = None
    next_items: List[TimelineItemResponse] = []