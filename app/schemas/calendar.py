"""
Calendar integration Pydantic schemas.
Defines request and response models for calendar integration API endpoints.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum

from app.services.calendar_service import CalendarProvider, SyncStatus


class CalendarProviderEnum(str, Enum):
    """Calendar provider enumeration for API."""
    GOOGLE = "google"
    APPLE = "apple"
    OUTLOOK = "outlook"


class SyncStatusEnum(str, Enum):
    """Sync status enumeration for API."""
    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"
    DISABLED = "disabled"


# Base schemas
class CalendarEventBase(BaseModel):
    """Base calendar event schema."""
    title: str = Field(..., min_length=1, max_length=255, description="Event title")
    description: Optional[str] = Field(None, max_length=2000, description="Event description")
    start_time: datetime = Field(..., description="Event start time")
    end_time: Optional[datetime] = Field(None, description="Event end time")
    location: Optional[str] = Field(None, max_length=500, description="Event location")
    attendees: Optional[List[str]] = Field(default_factory=list, description="List of attendee emails")
    all_day: bool = Field(False, description="Whether this is an all-day event")
    timezone: Optional[str] = Field("UTC", description="Event timezone")
    recurrence: Optional[str] = Field(None, description="Recurrence rule (RRULE format)")


class CalendarConnectionBase(BaseModel):
    """Base calendar connection schema."""
    provider: CalendarProviderEnum = Field(..., description="Calendar provider")
    calendar_name: str = Field(..., min_length=1, max_length=255, description="Calendar display name")
    sync_enabled: bool = Field(True, description="Whether sync is enabled for this calendar")


# Request schemas
class GoogleCalendarAuthRequest(BaseModel):
    """Google Calendar authentication request."""
    auth_code: str = Field(..., description="OAuth authorization code from Google")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "auth_code": "4/0AX4XfWjYZ1234567890abcdef..."
            }
        }
    )


class AppleCalendarAuthRequest(BaseModel):
    """Apple Calendar authentication request."""
    apple_id: str = Field(..., description="Apple ID (email address)")
    app_password: str = Field(..., description="App-specific password")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "apple_id": "user@icloud.com",
                "app_password": "abcd-efgh-ijkl-mnop"
            }
        }
    )


class CalendarConnectionUpdateRequest(BaseModel):
    """Calendar connection update request."""
    calendar_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Calendar display name")
    sync_enabled: Optional[bool] = Field(None, description="Whether sync is enabled")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "calendar_name": "My Work Calendar",
                "sync_enabled": True
            }
        }
    )


class CalendarEventCreateRequest(CalendarEventBase):
    """Calendar event creation request."""
    sync_to_external: bool = Field(True, description="Whether to sync this event to external calendars")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Team Meeting",
                "description": "Weekly team sync meeting",
                "start_time": "2024-01-15T10:00:00Z",
                "end_time": "2024-01-15T11:00:00Z",
                "location": "Conference Room A",
                "attendees": ["john@example.com", "jane@example.com"],
                "all_day": False,
                "timezone": "UTC",
                "sync_to_external": True
            }
        }
    )


class CalendarEventUpdateRequest(BaseModel):
    """Calendar event update request."""
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Event title")
    description: Optional[str] = Field(None, max_length=2000, description="Event description")
    start_time: Optional[datetime] = Field(None, description="Event start time")
    end_time: Optional[datetime] = Field(None, description="Event end time")
    location: Optional[str] = Field(None, max_length=500, description="Event location")
    attendees: Optional[List[str]] = Field(None, description="List of attendee emails")
    all_day: Optional[bool] = Field(None, description="Whether this is an all-day event")
    timezone: Optional[str] = Field(None, description="Event timezone")
    recurrence: Optional[str] = Field(None, description="Recurrence rule (RRULE format)")
    sync_to_external: Optional[bool] = Field(None, description="Whether to sync this event to external calendars")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Updated Team Meeting",
                "start_time": "2024-01-15T14:00:00Z",
                "end_time": "2024-01-15T15:00:00Z",
                "sync_to_external": True
            }
        }
    )


class CalendarSyncRequest(BaseModel):
    """Calendar sync request."""
    start_date: Optional[datetime] = Field(None, description="Start date for sync range")
    end_date: Optional[datetime] = Field(None, description="End date for sync range")
    force_sync: bool = Field(False, description="Force full sync even if recently synced")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-01-31T23:59:59Z",
                "force_sync": False
            }
        }
    )


# Response schemas
class CalendarEventResponse(CalendarEventBase):
    """Calendar event response."""
    id: int = Field(..., description="Internal event ID")
    external_id: Optional[str] = Field(None, description="External calendar event ID")
    provider: Optional[CalendarProviderEnum] = Field(None, description="Calendar provider")
    user_id: int = Field(..., description="User ID who owns this event")
    created_at: datetime = Field(..., description="Event creation timestamp")
    updated_at: datetime = Field(..., description="Event last update timestamp")
    
    model_config = ConfigDict(from_attributes=True)


class CalendarConnectionResponse(CalendarConnectionBase):
    """Calendar connection response."""
    id: int = Field(..., description="Connection ID")
    user_id: int = Field(..., description="User ID")
    calendar_id: str = Field(..., description="External calendar ID")
    sync_status: SyncStatusEnum = Field(..., description="Current sync status")
    last_sync_at: Optional[datetime] = Field(None, description="Last successful sync timestamp")
    created_at: datetime = Field(..., description="Connection creation timestamp")
    updated_at: datetime = Field(..., description="Connection last update timestamp")
    
    model_config = ConfigDict(from_attributes=True)


class CalendarInfoResponse(BaseModel):
    """External calendar information response."""
    id: str = Field(..., description="External calendar ID")
    name: str = Field(..., description="Calendar name")
    description: Optional[str] = Field(None, description="Calendar description")
    primary: bool = Field(False, description="Whether this is the primary calendar")
    access_role: Optional[str] = Field(None, description="User's access role")
    color: Optional[str] = Field(None, description="Calendar color")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "primary",
                "name": "My Calendar",
                "description": "Primary calendar",
                "primary": True,
                "access_role": "owner",
                "color": "#3174ad"
            }
        }
    )


class CalendarAuthUrlResponse(BaseModel):
    """Calendar authentication URL response."""
    auth_url: str = Field(..., description="Authorization URL")
    provider: CalendarProviderEnum = Field(..., description="Calendar provider")
    instructions: Optional[str] = Field(None, description="Additional instructions for user")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "auth_url": "https://accounts.google.com/o/oauth2/auth?...",
                "provider": "google",
                "instructions": "Click the link to authorize access to your Google Calendar"
            }
        }
    )


class CalendarSyncResponse(BaseModel):
    """Calendar sync response."""
    connection_id: int = Field(..., description="Calendar connection ID")
    sync_status: SyncStatusEnum = Field(..., description="Sync status")
    events_synced: int = Field(..., description="Number of events synced")
    events_created: int = Field(..., description="Number of events created")
    events_updated: int = Field(..., description="Number of events updated")
    events_deleted: int = Field(..., description="Number of events deleted")
    sync_started_at: datetime = Field(..., description="Sync start timestamp")
    sync_completed_at: Optional[datetime] = Field(None, description="Sync completion timestamp")
    error_message: Optional[str] = Field(None, description="Error message if sync failed")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "connection_id": 1,
                "sync_status": "synced",
                "events_synced": 25,
                "events_created": 5,
                "events_updated": 3,
                "events_deleted": 1,
                "sync_started_at": "2024-01-15T10:00:00Z",
                "sync_completed_at": "2024-01-15T10:02:30Z",
                "error_message": None
            }
        }
    )


class CalendarStatsResponse(BaseModel):
    """Calendar statistics response."""
    total_connections: int = Field(..., description="Total number of calendar connections")
    active_connections: int = Field(..., description="Number of active connections")
    total_events: int = Field(..., description="Total number of synced events")
    last_sync_at: Optional[datetime] = Field(None, description="Last sync timestamp across all calendars")
    sync_errors: int = Field(..., description="Number of recent sync errors")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_connections": 3,
                "active_connections": 2,
                "total_events": 150,
                "last_sync_at": "2024-01-15T10:00:00Z",
                "sync_errors": 0
            }
        }
    )


# List response schemas
class CalendarConnectionListResponse(BaseModel):
    """Calendar connections list response."""
    connections: List[CalendarConnectionResponse] = Field(..., description="List of calendar connections")
    total: int = Field(..., description="Total number of connections")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "connections": [
                    {
                        "id": 1,
                        "user_id": 1,
                        "provider": "google",
                        "calendar_id": "primary",
                        "calendar_name": "My Google Calendar",
                        "sync_status": "synced",
                        "sync_enabled": True,
                        "last_sync_at": "2024-01-15T10:00:00Z",
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-15T10:00:00Z"
                    }
                ],
                "total": 1
            }
        }
    )


class CalendarEventListResponse(BaseModel):
    """Calendar events list response."""
    events: List[CalendarEventResponse] = Field(..., description="List of calendar events")
    total: int = Field(..., description="Total number of events")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "events": [
                    {
                        "id": 1,
                        "title": "Team Meeting",
                        "description": "Weekly team sync",
                        "start_time": "2024-01-15T10:00:00Z",
                        "end_time": "2024-01-15T11:00:00Z",
                        "location": "Conference Room A",
                        "attendees": ["john@example.com"],
                        "all_day": False,
                        "timezone": "UTC",
                        "external_id": "abc123",
                        "provider": "google",
                        "user_id": 1,
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-15T10:00:00Z"
                    }
                ],
                "total": 1
            }
        }
    )


class CalendarInfoListResponse(BaseModel):
    """External calendars list response."""
    calendars: List[CalendarInfoResponse] = Field(..., description="List of external calendars")
    provider: CalendarProviderEnum = Field(..., description="Calendar provider")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "calendars": [
                    {
                        "id": "primary",
                        "name": "My Calendar",
                        "description": "Primary calendar",
                        "primary": True,
                        "access_role": "owner",
                        "color": "#3174ad"
                    }
                ],
                "provider": "google"
            }
        }
    )