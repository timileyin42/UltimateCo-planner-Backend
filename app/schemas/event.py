from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from app.models.shared_models import EventType, EventStatus, RSVPStatus, TaskStatus, TaskPriority
from app.schemas.user import UserSummary
from app.schemas.location import EnhancedLocation, LocationOptimizationRequest, LocationOptimizationResponse

# Base event schemas
class EventBase(BaseModel):
    """Base event schema with common fields"""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    event_type: EventType = EventType.OTHER
    start_datetime: datetime
    end_datetime: Optional[datetime] = None
    timezone: Optional[str] = None
    venue_name: Optional[str] = None
    venue_address: Optional[str] = None
    venue_city: Optional[str] = None
    venue_country: Optional[str] = None
    is_public: bool = False
    max_attendees: Optional[int] = Field(None, ge=1)
    requires_approval: bool = False
    allow_guest_invites: bool = True
    total_budget: Optional[float] = Field(None, ge=0)
    currency: str = "USD"
    theme_color: Optional[str] = Field(None, regex=r'^#[0-9A-Fa-f]{6}$')

class EventCreate(EventBase):
    """Schema for creating a new event"""
    location_input: Optional[str] = Field(None, description="Raw location input for optimization")
    user_coordinates: Optional[dict] = Field(None, description="User's current coordinates for location optimization")
    auto_optimize_location: bool = Field(True, description="Whether to automatically optimize location using Google Maps")

class EventUpdate(BaseModel):
    """Schema for updating event information"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    event_type: Optional[EventType] = None
    status: Optional[EventStatus] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    timezone: Optional[str] = None
    venue_name: Optional[str] = None
    venue_address: Optional[str] = None
    venue_city: Optional[str] = None
    venue_country: Optional[str] = None
    is_public: Optional[bool] = None
    max_attendees: Optional[int] = Field(None, ge=1)
    requires_approval: Optional[bool] = None

class EventDuplicateRequest(BaseModel):
    """Schema for duplicating an event"""
    new_title: Optional[str] = Field(None, min_length=1, max_length=255, description="New title for the duplicated event")
    
    model_config = ConfigDict(from_attributes=True)
    allow_guest_invites: Optional[bool] = None
    total_budget: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = None
    theme_color: Optional[str] = Field(None, regex=r'^#[0-9A-Fa-f]{6}$')

class EventResponse(EventBase):
    """Schema for event response"""
    id: int
    status: EventStatus
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    cover_image_url: Optional[str] = None
    creator_id: int
    creator: UserSummary
    attendee_count: int
    total_expenses: float
    created_at: datetime
    updated_at: datetime
    
    # Enhanced location fields
    place_id: Optional[str] = None
    formatted_address: Optional[str] = None
    location_verified: bool = False
    location_verification_timestamp: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class EventSummary(BaseModel):
    """Schema for event summary (minimal fields)"""
    id: int
    title: str
    event_type: EventType
    status: EventStatus
    start_datetime: datetime
    venue_name: Optional[str] = None
    venue_city: Optional[str] = None
    cover_image_url: Optional[str] = None
    attendee_count: int
    
    model_config = ConfigDict(from_attributes=True)

# Event invitation schemas
class EventInvitationBase(BaseModel):
    """Base event invitation schema"""
    invitation_message: Optional[str] = None
    plus_one_allowed: bool = False

class EventInvitationCreate(EventInvitationBase):
    """Schema for creating event invitation"""
    user_ids: List[int] = Field(..., min_items=1)

class EventInvitationUpdate(BaseModel):
    """Schema for updating invitation response"""
    rsvp_status: RSVPStatus
    response_message: Optional[str] = None
    plus_one_name: Optional[str] = None
    dietary_restrictions: Optional[str] = None
    special_requests: Optional[str] = None

class EventInvitationResponse(EventInvitationBase):
    """Schema for event invitation response"""
    id: int
    event_id: int
    user_id: int
    user: UserSummary
    rsvp_status: RSVPStatus
    response_message: Optional[str] = None
    plus_one_name: Optional[str] = None
    dietary_restrictions: Optional[str] = None
    special_requests: Optional[str] = None
    invited_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Task schemas
class TaskBase(BaseModel):
    """Base task schema"""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[datetime] = None
    estimated_cost: Optional[float] = Field(None, ge=0)
    category: Optional[str] = None

class TaskCreate(TaskBase):
    """Schema for creating a new task"""
    assignee_id: Optional[int] = None

class TaskUpdate(BaseModel):
    """Schema for updating task information"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    due_date: Optional[datetime] = None
    estimated_cost: Optional[float] = Field(None, ge=0)
    actual_cost: Optional[float] = Field(None, ge=0)
    category: Optional[str] = None
    assignee_id: Optional[int] = None

class TaskResponse(TaskBase):
    """Schema for task response"""
    id: int
    event_id: int
    creator_id: int
    assignee_id: Optional[int] = None
    status: TaskStatus
    actual_cost: Optional[float] = None
    completed_at: Optional[datetime] = None
    creator: UserSummary
    assignee: Optional[UserSummary] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Expense schemas
class ExpenseBase(BaseModel):
    """Base expense schema"""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    amount: float = Field(..., gt=0)
    currency: str = "USD"
    category: Optional[str] = None
    vendor_name: Optional[str] = None
    expense_date: datetime
    is_shared: bool = False
    split_equally: bool = True

class ExpenseCreate(ExpenseBase):
    """Schema for creating a new expense"""
    split_with_user_ids: Optional[List[int]] = None

class ExpenseUpdate(BaseModel):
    """Schema for updating expense information"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    amount: Optional[float] = Field(None, gt=0)
    currency: Optional[str] = None
    category: Optional[str] = None
    vendor_name: Optional[str] = None
    expense_date: Optional[datetime] = None
    is_shared: Optional[bool] = None
    split_equally: Optional[bool] = None

class ExpenseResponse(ExpenseBase):
    """Schema for expense response"""
    id: int
    event_id: int
    paid_by_user_id: int
    receipt_url: Optional[str] = None
    paid_by: UserSummary
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Comment schemas
class CommentBase(BaseModel):
    """Base comment schema"""
    content: str = Field(..., min_length=1, max_length=1000)

class CommentCreate(CommentBase):
    """Schema for creating a new comment"""
    parent_id: Optional[int] = None

class CommentUpdate(BaseModel):
    """Schema for updating comment"""
    content: str = Field(..., min_length=1, max_length=1000)

class CommentResponse(CommentBase):
    """Schema for comment response"""
    id: int
    event_id: int
    author_id: int
    parent_id: Optional[int] = None
    author: UserSummary
    replies: List['CommentResponse'] = []
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Poll schemas
class PollOptionBase(BaseModel):
    """Base poll option schema"""
    text: str = Field(..., min_length=1, max_length=255)

class PollOptionCreate(PollOptionBase):
    """Schema for creating poll option"""
    pass

class PollOptionResponse(PollOptionBase):
    """Schema for poll option response"""
    id: int
    poll_id: int
    order_index: int
    vote_count: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class PollBase(BaseModel):
    """Base poll schema"""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    multiple_choice: bool = False
    anonymous: bool = False
    closes_at: Optional[datetime] = None

class PollCreate(PollBase):
    """Schema for creating a new poll"""
    options: List[PollOptionCreate] = Field(..., min_items=2, max_items=10)

class PollUpdate(BaseModel):
    """Schema for updating poll"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    closes_at: Optional[datetime] = None

class PollResponse(PollBase):
    """Schema for poll response"""
    id: int
    event_id: int
    creator_id: int
    creator: UserSummary
    options: List[PollOptionResponse]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class PollVoteCreate(BaseModel):
    """Schema for creating poll vote"""
    option_ids: List[int] = Field(..., min_items=1)

# Event search and listing schemas
class EventSearchQuery(BaseModel):
    """Schema for event search query"""
    query: Optional[str] = None
    event_type: Optional[EventType] = None
    status: Optional[EventStatus] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    city: Optional[str] = None
    country: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

class EventListResponse(BaseModel):
    """Schema for event list response"""
    events: List[EventSummary]
    total: int
    limit: int
    offset: int

class EventStatsResponse(BaseModel):
    """Schema for event statistics"""
    total_attendees: int
    confirmed_attendees: int
    pending_responses: int

# Location optimization schemas for events
class EventLocationOptimizationRequest(LocationOptimizationRequest):
    """Request for optimizing event location"""
    event_type: Optional[EventType] = Field(None, description="Event type for better location suggestions")
    
class EventLocationOptimizationResponse(LocationOptimizationResponse):
    """Response from event location optimization"""
    recommended_location: Optional[EnhancedLocation] = Field(None, description="Recommended optimized location for the event")
    total_tasks: int
    completed_tasks: int
    total_expenses: float
    budget_remaining: Optional[float] = None
    
    model_config = ConfigDict(from_attributes=True)

# Enable forward references for recursive models
CommentResponse.model_rebuild()