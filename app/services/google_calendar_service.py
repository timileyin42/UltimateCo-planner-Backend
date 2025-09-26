"""
Google Calendar API integration service.
Provides Google Calendar synchronization functionality.
"""

import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pytz

from app.services.calendar_service import (
    BaseCalendarService, CalendarEvent, CalendarConnection, 
    CalendarProvider, SyncStatus, CalendarAuthError, CalendarSyncError
)
from app.core.config import get_settings
from app.core.circuit_breaker import google_api_circuit_breaker

settings = get_settings()


class GoogleCalendarService(BaseCalendarService):
    """Google Calendar API service implementation."""
    
    def __init__(self):
        super().__init__()
        self.provider = CalendarProvider.GOOGLE
        self.scopes = [
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/calendar.events'
        ]
        
        # Google OAuth2 configuration
        self.client_config = {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [f"{settings.FRONTEND_URL}/auth/google/callback"]
            }
        }
    
    def get_authorization_url(self, user_id: int) -> str:
        """
        Get Google OAuth2 authorization URL.
        
        Args:
            user_id: User ID for state parameter
            
        Returns:
            Authorization URL
        """
        flow = Flow.from_client_config(
            self.client_config,
            scopes=self.scopes,
            redirect_uri=self.client_config["web"]["redirect_uris"][0]
        )
        
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=str(user_id)
        )
        
        return authorization_url
    
    async def authenticate(self, user_id: int, auth_code: str) -> CalendarConnection:
        """
        Authenticate user with Google Calendar.
        
        Args:
            user_id: User ID
            auth_code: Authorization code from OAuth flow
            
        Returns:
            CalendarConnection object
        """
        try:
            flow = Flow.from_client_config(
                self.client_config,
                scopes=self.scopes,
                redirect_uri=self.client_config["web"]["redirect_uris"][0]
            )
            
            # Exchange authorization code for tokens
            flow.fetch_token(code=auth_code)
            credentials = flow.credentials
            
            # Get user's primary calendar info
            service = build('calendar', 'v3', credentials=credentials)
            calendar_info = service.calendars().get(calendarId='primary').execute()
            
            # Create connection object
            connection = CalendarConnection(
                user_id=user_id,
                provider=CalendarProvider.GOOGLE,
                calendar_id='primary',
                calendar_name=calendar_info.get('summary', 'Primary Calendar'),
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                expires_at=credentials.expiry,
                sync_status=SyncStatus.SYNCED,
                last_sync_at=datetime.utcnow(),
                sync_enabled=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            return connection
            
        except Exception as e:
            self._handle_api_error(e, "Google Calendar authentication")
    
    async def refresh_token(self, connection: CalendarConnection) -> CalendarConnection:
        """
        Refresh Google Calendar access token.
        
        Args:
            connection: Calendar connection to refresh
            
        Returns:
            Updated CalendarConnection object
        """
        try:
            credentials = Credentials(
                token=connection.access_token,
                refresh_token=connection.refresh_token,
                token_uri=self.client_config["web"]["token_uri"],
                client_id=self.client_config["web"]["client_id"],
                client_secret=self.client_config["web"]["client_secret"]
            )
            
            # Refresh the token
            credentials.refresh(Request())
            
            # Update connection
            connection.access_token = credentials.token
            connection.expires_at = credentials.expiry
            connection.updated_at = datetime.utcnow()
            connection.sync_status = SyncStatus.SYNCED
            
            return connection
            
        except Exception as e:
            connection.sync_status = SyncStatus.FAILED
            self._handle_api_error(e, "Google Calendar token refresh")
    
    async def get_calendars(self, connection: CalendarConnection) -> List[Dict[str, Any]]:
        """
        Get list of user's Google Calendars.
        
        Args:
            connection: Calendar connection
            
        Returns:
            List of calendar dictionaries
        """
        try:
            service = self._get_service(connection)
            
            calendars_result = service.calendarList().list().execute()
            calendars = calendars_result.get('items', [])
            
            return [
                {
                    'id': cal['id'],
                    'name': cal['summary'],
                    'description': cal.get('description', ''),
                    'primary': cal.get('primary', False),
                    'access_role': cal.get('accessRole', ''),
                    'color': cal.get('backgroundColor', '#ffffff')
                }
                for cal in calendars
            ]
            
        except Exception as e:
            self._handle_api_error(e, "Get Google Calendars")
    
    @google_api_circuit_breaker()
    async def create_event(self, connection: CalendarConnection, event: CalendarEvent) -> str:
        """
        Create event in Google Calendar.
        
        Args:
            connection: Calendar connection
            event: Event to create
            
        Returns:
            Google Calendar event ID
        """
        try:
            service = self._get_service(connection)
            
            # Convert to Google Calendar event format
            google_event = self._to_google_event(event)
            
            # Create event
            created_event = service.events().insert(
                calendarId=connection.calendar_id,
                body=google_event
            ).execute()
            
            return created_event['id']
            
        except Exception as e:
            self._handle_api_error(e, "Create Google Calendar event")
    
    @google_api_circuit_breaker()
    async def update_event(self, connection: CalendarConnection, event: CalendarEvent) -> bool:
        """
        Update event in Google Calendar.
        
        Args:
            connection: Calendar connection
            event: Event to update (must have external_id)
            
        Returns:
            True if successful
        """
        try:
            if not event.external_id:
                raise ValueError("Event must have external_id for updates")
            
            service = self._get_service(connection)
            
            # Convert to Google Calendar event format
            google_event = self._to_google_event(event)
            
            # Update event
            service.events().update(
                calendarId=connection.calendar_id,
                eventId=event.external_id,
                body=google_event
            ).execute()
            
            return True
            
        except Exception as e:
            self._handle_api_error(e, "Update Google Calendar event")
    
    @google_api_circuit_breaker()
    async def delete_event(self, connection: CalendarConnection, external_event_id: str) -> bool:
        """
        Delete event from Google Calendar.
        
        Args:
            connection: Calendar connection
            external_event_id: Google Calendar event ID
            
        Returns:
            True if successful
        """
        try:
            service = self._get_service(connection)
            
            service.events().delete(
                calendarId=connection.calendar_id,
                eventId=external_event_id
            ).execute()
            
            return True
            
        except Exception as e:
            self._handle_api_error(e, "Delete Google Calendar event")
    
    @google_api_circuit_breaker()
    async def get_events(
        self, 
        connection: CalendarConnection, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[CalendarEvent]:
        """
        Get events from Google Calendar within date range.
        
        Args:
            connection: Calendar connection
            start_date: Start date for event retrieval
            end_date: End date for event retrieval
            
        Returns:
            List of CalendarEvent objects
        """
        try:
            service = self._get_service(connection)
            
            # Format dates for Google Calendar API
            time_min = start_date.isoformat() + 'Z'
            time_max = end_date.isoformat() + 'Z'
            
            events_result = service.events().list(
                calendarId=connection.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            return [self._from_google_event(event) for event in events]
            
        except Exception as e:
            self._handle_api_error(e, "Get Google Calendar events")
    
    def _get_service(self, connection: CalendarConnection):
        """Get authenticated Google Calendar service."""
        credentials = Credentials(
            token=connection.access_token,
            refresh_token=connection.refresh_token,
            token_uri=self.client_config["web"]["token_uri"],
            client_id=self.client_config["web"]["client_id"],
            client_secret=self.client_config["web"]["client_secret"]
        )
        
        return build('calendar', 'v3', credentials=credentials)
    
    def _to_google_event(self, event: CalendarEvent) -> Dict[str, Any]:
        """Convert CalendarEvent to Google Calendar event format."""
        google_event = {
            'summary': event.title,
            'description': event.description or '',
            'location': event.location or ''
        }
        
        if event.all_day:
            # All-day event
            google_event['start'] = {
                'date': event.start_time.date().isoformat()
            }
            google_event['end'] = {
                'date': (event.end_time or event.start_time + timedelta(days=1)).date().isoformat()
            }
        else:
            # Timed event
            timezone = event.timezone or 'UTC'
            google_event['start'] = {
                'dateTime': event.start_time.isoformat(),
                'timeZone': timezone
            }
            google_event['end'] = {
                'dateTime': (event.end_time or event.start_time + timedelta(hours=1)).isoformat(),
                'timeZone': timezone
            }
        
        # Add attendees
        if event.attendees:
            google_event['attendees'] = [
                {'email': email} for email in event.attendees
            ]
        
        # Add recurrence if specified
        if event.recurrence:
            google_event['recurrence'] = [event.recurrence]
        
        return google_event
    
    def _from_google_event(self, google_event: Dict[str, Any]) -> CalendarEvent:
        """Convert Google Calendar event to CalendarEvent."""
        # Parse start and end times
        start_info = google_event.get('start', {})
        end_info = google_event.get('end', {})
        
        if 'date' in start_info:
            # All-day event
            start_time = datetime.fromisoformat(start_info['date'])
            end_time = datetime.fromisoformat(end_info['date'])
            all_day = True
            timezone = None
        else:
            # Timed event
            start_time = datetime.fromisoformat(start_info['dateTime'].replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(end_info['dateTime'].replace('Z', '+00:00'))
            all_day = False
            timezone = start_info.get('timeZone', 'UTC')
        
        # Extract attendees
        attendees = []
        for attendee in google_event.get('attendees', []):
            if 'email' in attendee:
                attendees.append(attendee['email'])
        
        # Extract recurrence
        recurrence = None
        if 'recurrence' in google_event and google_event['recurrence']:
            recurrence = google_event['recurrence'][0]
        
        return CalendarEvent(
            id=google_event['id'],
            title=google_event.get('summary', ''),
            description=google_event.get('description', ''),
            start_time=start_time,
            end_time=end_time,
            location=google_event.get('location', ''),
            attendees=attendees,
            all_day=all_day,
            timezone=timezone,
            recurrence=recurrence,
            external_id=google_event['id'],
            provider=CalendarProvider.GOOGLE
        )