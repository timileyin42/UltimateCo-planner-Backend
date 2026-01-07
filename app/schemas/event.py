from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict, field_validator, FieldValidationInfo
from app.models.shared_models import EventType, EventStatus, RSVPStatus, TaskStatus, TaskPriority
from app.schemas.user import UserSummary
from app.schemas.location import EnhancedLocation, LocationOptimizationRequest, LocationOptimizationResponse, Coordinates

# Base event schemas
class EventBase(BaseModel):
    """Base event schema with common fields"""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    event_type: EventType = EventType.OTHER
    
    @field_validator('event_type', mode='before')
    @classmethod
    def normalize_event_type(cls, v):
        """Normalize event type to lowercase for case-insensitive matching"""
        if isinstance(v, str):
            return v.lower()
        return v
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
    currency: str = Field(default="USD", pattern=r'^(USD|GBP)$', description="Currency code (USD or GBP)")
    theme_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    
    @field_validator('currency', mode='before')
    @classmethod
    def validate_currency(cls, v):
        if v:
            v = v.upper()
            if v not in ['USD', 'GBP']:
                raise ValueError('Currency must be USD or GBP')
            return v
        return 'USD'

class EventCreate(EventBase):
    """Schema for creating a new event"""
    cover_image_url: Optional[str] = Field(None, description="URL of the event cover image (from upload endpoint)")
    location_input: Optional[str] = Field(None, description="Raw location input for optimization. Can be just an address or 'Venue - Address'. Backend will extract venue name if present.")
    user_coordinates: Optional[Coordinates] = Field(None, description="User's current coordinates for location optimization")
    auto_optimize_location: bool = Field(True, description="Whether to automatically optimize location using Google Maps")
    task_categories: Optional[List["TaskCategory"]] = Field(
        default=None,
        description="Optional task categories to seed tasks during event creation"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Paint and Sip",
                "description": "Unwind with an evening of painting, wine, and good vibes",
                "event_type": "party",
                "start_datetime": "2024-08-18T12:00:00Z",
                "end_datetime": "2024-08-18T13:00:00Z",
                "timezone": "Africa/Lagos",
                "venue_name": "Cafe Bloom",
                "venue_address": "26 Olaniyi St, Ikeja",
                "venue_city": "Lagos",
                "venue_country": "Nigeria",
                "is_public": True,
                "max_attendees": 50,
                "cover_image_url": "https://storage.googleapis.com/.../event-cover.jpg",
                "location_input": "Cafe Bloom - 26 Olaniyi St, Lagos",
                "user_coordinates": {
                    "latitude": 6.5244,
                    "longitude": 3.3792
                },
                "auto_optimize_location": True
            }
        }

class EventUpdate(BaseModel):
    """Schema for updating event information"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    event_type: Optional[EventType] = None
    status: Optional[EventStatus] = None
    cover_image_url: Optional[str] = Field(None, description="URL of the event cover image")
    
    @field_validator('event_type', 'status', mode='before')
    @classmethod
    def normalize_enums(cls, v):
        """Normalize enum values to lowercase for case-insensitive matching"""
        if isinstance(v, str):
            return v.lower()
        return v
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
    currency: Optional[str] = Field(None, pattern=r'^(USD|GBP)$', description="Currency code (USD or GBP)")
    theme_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    
    @field_validator('currency', mode='before')
    @classmethod
    def validate_currency_update(cls, v):
        if v:
            v = v.upper()
            if v not in ['USD', 'GBP']:
                raise ValueError('Currency must be USD or GBP')
            return v
        return v

class TaskCategoryItem(BaseModel):
    """Individual task item within a category"""
    id: Optional[int] = None
    title: str
    description: Optional[str] = None
    completed: bool = False
    assignee_id: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)

class TaskCategory(BaseModel):
    """Task category with items"""
    name: str
    items: List[TaskCategoryItem] = Field(default_factory=list)
    
    model_config = ConfigDict(from_attributes=True)


EventCreate.model_rebuild()

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
    
    # Task categories for mobile app
    task_categories: List[TaskCategory] = Field(default_factory=list)
    
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
    
    @field_validator('rsvp_status', mode='before')
    @classmethod
    def normalize_rsvp_status(cls, v):
        """Normalize RSVP status to lowercase for case-insensitive matching"""
        if isinstance(v, str):
            return v.lower()
        return v

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

class CollaboratorAddRequest(BaseModel):
    """Schema for adding collaborators to an event"""
    user_ids: List[int] = Field(..., min_items=1)
    send_notifications: bool = Field(False, description="Whether to notify newly added collaborators")

# Task schemas
class TaskBase(BaseModel):
    """Base task schema"""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[datetime] = None
    estimated_cost: Optional[float] = Field(None, ge=0)
    category: Optional[str] = None
    
    @field_validator('priority', mode='before')
    @classmethod
    def normalize_priority(cls, v):
        """Normalize priority to lowercase for case-insensitive matching"""
        if isinstance(v, str):
            return v.lower()
        return v

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
    
    @field_validator('status', 'priority', mode='before')
    @classmethod
    def normalize_enums(cls, v, info: FieldValidationInfo):
        """Normalize enum values and map common aliases"""
        if not isinstance(v, str):
            return v

        normalized = v.strip().lower().replace("-", "_").replace(" ", "_")

        if info.field_name == 'status':
            status_aliases = {
                'pending': 'in_progress',
                'incomplete': 'in_progress',
                'not_complete': 'in_progress',
                'resume': 'in_progress',
                'not_started': 'todo',
                'todo': 'todo',
                'inprogress': 'in_progress',
                'in_progress': 'in_progress',
                'complete': 'completed',
                'completed': 'completed',
                'done': 'completed',
                'canceled': 'cancelled',
            }
            return status_aliases.get(normalized, normalized)

        if info.field_name == 'priority':
            priority_aliases = {
                'normal': 'medium',
            }
            return priority_aliases.get(normalized, normalized)

        return normalized

class TaskResponse(TaskBase):
    """Schema for task response"""
    id: int
    event_id: int
    creator_id: int
    assignee_id: Optional[int] = Field(default=None, alias="assigned_to_id", serialization_alias="assignee_id")
    status: TaskStatus
    completed: bool = False

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator("completed", mode="before")
    @classmethod
    def derive_completed(cls, v, values):
        if v is not None:
            return v
        status = values.get("status")
        if isinstance(status, TaskStatus):
            return status == TaskStatus.COMPLETED
        if isinstance(status, str):
            try:
                return TaskStatus(status) == TaskStatus.COMPLETED
            except ValueError:
                return False
        return False

class TaskCategoriesResponse(BaseModel):
    """Schema for tasks grouped by categories"""
    task_categories: List[TaskCategory] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

# Expense schemas
class ExpenseBase(BaseModel):
    """Base expense schema"""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    amount: float = Field(..., gt=0)
    currency: str = Field(default="USD", pattern=r'^(USD|GBP)$', description="Currency code (USD or GBP)")
    category: Optional[str] = None
    vendor_name: Optional[str] = None
    expense_date: datetime
    is_shared: bool = False
    split_equally: bool = True
    
    @field_validator('currency', mode='before')
    @classmethod
    def validate_currency(cls, v):
        if v:
            v = v.upper()
            if v not in ['USD', 'GBP']:
                raise ValueError('Currency must be USD or GBP')
            return v
        return 'USD'

class ExpenseCreate(ExpenseBase):
    """Schema for creating a new expense"""
    split_with_user_ids: Optional[List[int]] = None

class ExpenseUpdate(BaseModel):
    """Schema for updating expense information"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    amount: Optional[float] = Field(None, gt=0)
    currency: Optional[str] = Field(None, pattern=r'^(USD|GBP)$', description="Currency code (USD or GBP)")
    category: Optional[str] = None
    vendor_name: Optional[str] = None
    expense_date: Optional[datetime] = None
    is_shared: Optional[bool] = None
    split_equally: Optional[bool] = None
    
    @field_validator('currency', mode='before')
    @classmethod
    def validate_currency(cls, v):
        if v:
            v = v.upper()
            if v not in ['USD', 'GBP']:
                raise ValueError('Currency must be USD or GBP')
            return v
        return v

class ExpenseResponse(ExpenseBase):
    """Schema for expense response"""
    id: int
    event_id: int
    paid_by_user_id: int
    receipt_url: Optional[str] = None
    paid_by: UserSummary = Field(..., alias="paid_by_user")
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

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
    replies: List['CommentResponse'] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

    @field_validator("replies", mode="before")
    @classmethod
    def ensure_replies_list(cls, value):
        """Normalize replies so ResponseValidation always receives a list."""
        if value is None:
            return []
        return value

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
    rsvp_counts: Dict[str, int]
    task_counts: Dict[str, int]
    total_expenses: float
    budget_remaining: Optional[float] = None
    total_invitations: int
    total_tasks: int
    total_comments: int
    total_polls: int

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