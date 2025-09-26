"""
Base calendar service with abstract interface for different calendar providers.
Provides a unified interface for Google Calendar, Apple Calendar, and other providers.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CalendarProvider(str, Enum):
    """Supported calendar providers."""
    GOOGLE = "google"
    APPLE = "apple"
    OUTLOOK = "outlook"


class SyncStatus(str, Enum):
    """Calendar sync status."""
    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"
    DISCONNECTED = "disconnected"


@dataclass
class CalendarEvent:
    """Unified calendar event representation."""
    id: Optional[str] = None
    title: str = ""
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    attendees: List[str] = None
    all_day: bool = False
    timezone: Optional[str] = None
    recurrence: Optional[str] = None
    external_id: Optional[str] = None  # ID from external calendar
    provider: Optional[CalendarProvider] = None
    
    def __post_init__(self):
        if self.attendees is None:
            self.attendees = []


@dataclass
class CalendarConnection:
    """Calendar connection information."""
    id: Optional[int] = None
    user_id: int = 0
    provider: CalendarProvider = CalendarProvider.GOOGLE
    calendar_id: str = ""
    calendar_name: str = ""
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    sync_status: SyncStatus = SyncStatus.DISCONNECTED
    last_sync_at: Optional[datetime] = None
    sync_enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CalendarServiceError(Exception):
    """Base exception for calendar service errors."""
    pass


class CalendarAuthError(CalendarServiceError):
    """Calendar authentication error."""
    pass


class CalendarSyncError(CalendarServiceError):
    """Calendar synchronization error."""
    pass


class BaseCalendarService(ABC):
    """Abstract base class for calendar service implementations."""
    
    def __init__(self):
        self.provider: CalendarProvider = None
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    async def authenticate(self, user_id: int, auth_code: str) -> CalendarConnection:
        """
        Authenticate user with calendar provider.
        
        Args:
            user_id: User ID
            auth_code: Authorization code from OAuth flow
            
        Returns:
            CalendarConnection object with authentication details
        """
        pass
    
    @abstractmethod
    async def refresh_token(self, connection: CalendarConnection) -> CalendarConnection:
        """
        Refresh access token for calendar connection.
        
        Args:
            connection: Calendar connection to refresh
            
        Returns:
            Updated CalendarConnection object
        """
        pass
    
    @abstractmethod
    async def get_calendars(self, connection: CalendarConnection) -> List[Dict[str, Any]]:
        """
        Get list of available calendars for the user.
        
        Args:
            connection: Calendar connection
            
        Returns:
            List of calendar dictionaries
        """
        pass
    
    @abstractmethod
    async def create_event(self, connection: CalendarConnection, event: CalendarEvent) -> str:
        """
        Create event in external calendar.
        
        Args:
            connection: Calendar connection
            event: Event to create
            
        Returns:
            External event ID
        """
        pass
    
    @abstractmethod
    async def update_event(self, connection: CalendarConnection, event: CalendarEvent) -> bool:
        """
        Update event in external calendar.
        
        Args:
            connection: Calendar connection
            event: Event to update (must have external_id)
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    async def delete_event(self, connection: CalendarConnection, external_event_id: str) -> bool:
        """
        Delete event from external calendar.
        
        Args:
            connection: Calendar connection
            external_event_id: External event ID to delete
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    async def get_events(
        self, 
        connection: CalendarConnection, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[CalendarEvent]:
        """
        Get events from external calendar within date range.
        
        Args:
            connection: Calendar connection
            start_date: Start date for event retrieval
            end_date: End date for event retrieval
            
        Returns:
            List of CalendarEvent objects
        """
        pass
    
    async def validate_connection(self, connection: CalendarConnection) -> bool:
        """
        Validate calendar connection by making a test API call.
        
        Args:
            connection: Calendar connection to validate
            
        Returns:
            True if connection is valid
        """
        try:
            await self.get_calendars(connection)
            return True
        except Exception as e:
            self.logger.error(f"Connection validation failed: {str(e)}")
            return False
    
    def _handle_api_error(self, error: Exception, operation: str) -> None:
        """
        Handle API errors and convert to appropriate exceptions.
        
        Args:
            error: Original exception
            operation: Operation that failed
        """
        error_msg = f"{operation} failed: {str(error)}"
        self.logger.error(error_msg)
        
        if "auth" in str(error).lower() or "unauthorized" in str(error).lower():
            raise CalendarAuthError(error_msg)
        else:
            raise CalendarSyncError(error_msg)


class CalendarServiceFactory:
    """Factory for creating calendar service instances."""
    
    _services: Dict[CalendarProvider, BaseCalendarService] = {}
    
    @classmethod
    def register_service(cls, provider: CalendarProvider, service_class: type):
        """Register a calendar service implementation."""
        cls._services[provider] = service_class
    
    @classmethod
    def get_service(cls, provider: CalendarProvider) -> BaseCalendarService:
        """Get calendar service instance for provider."""
        if provider not in cls._services:
            raise ValueError(f"No service registered for provider: {provider}")
        
        service_class = cls._services[provider]
        return service_class()
    
    @classmethod
    def get_available_providers(cls) -> List[CalendarProvider]:
        """Get list of available calendar providers."""
        return list(cls._services.keys())