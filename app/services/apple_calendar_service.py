"""
Apple Calendar (iCloud) integration service using CalDAV protocol.
Provides Apple Calendar synchronization functionality.
"""

import re
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from urllib.parse import urljoin
import requests
from requests.auth import HTTPBasicAuth
import xml.etree.ElementTree as ET
from icalendar import Calendar, Event as ICalEvent, vDatetime
import pytz

from app.services.calendar_service import (
    BaseCalendarService, CalendarEvent, CalendarConnection, 
    CalendarProvider, SyncStatus, CalendarAuthError, CalendarSyncError
)

class AppleCalendarService(BaseCalendarService):
    """Apple Calendar (iCloud) CalDAV service implementation."""
    
    def __init__(self):
        super().__init__()
        self.provider = CalendarProvider.APPLE
        self.caldav_base_url = "https://caldav.icloud.com"
        self.principal_url = "/principals/"
        
    def get_authorization_url(self, user_id: int) -> str:
        """
        Apple Calendar uses app-specific passwords, not OAuth.
        Returns instruction URL for users.
        
        Args:
            user_id: User ID (not used for Apple)
            
        Returns:
            URL with instructions for generating app-specific password
        """
        return "https://support.apple.com/en-us/HT204397"
    
    async def authenticate(self, user_id: int, apple_id: str, app_password: str) -> CalendarConnection:
        """
        Authenticate user with Apple Calendar using app-specific password.
        
        Args:
            user_id: User ID
            apple_id: Apple ID (email)
            app_password: App-specific password
            
        Returns:
            CalendarConnection object
        """
        try:
            # Test authentication by getting principal
            principal_url = await self._discover_principal(apple_id, app_password)
            
            if not principal_url:
                raise CalendarAuthError("Invalid Apple ID or app-specific password")
            
            # Get calendar home URL
            calendar_home_url = await self._get_calendar_home(apple_id, app_password, principal_url)
            
            # Get primary calendar info
            calendars = await self._get_calendars_info(apple_id, app_password, calendar_home_url)
            
            if not calendars:
                raise CalendarSyncError("No calendars found")
            
            # Use first calendar as primary
            primary_calendar = calendars[0]
            
            # Create connection object
            connection = CalendarConnection(
                user_id=user_id,
                provider=CalendarProvider.APPLE,
                calendar_id=primary_calendar['href'],
                calendar_name=primary_calendar['displayname'],
                access_token=apple_id,  # Store Apple ID as access token
                refresh_token=app_password,  # Store app password as refresh token
                expires_at=None,  # App passwords don't expire
                sync_status=SyncStatus.SYNCED,
                last_sync_at=datetime.utcnow(),
                sync_enabled=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            return connection
            
        except Exception as e:
            self._handle_api_error(e, "Apple Calendar authentication")
    
    async def refresh_token(self, connection: CalendarConnection) -> CalendarConnection:
        """
        Apple Calendar app passwords don't expire, so just update sync status.
        
        Args:
            connection: Calendar connection to refresh
            
        Returns:
            Updated CalendarConnection object
        """
        try:
            # Test connection by making a simple request
            apple_id = connection.access_token
            app_password = connection.refresh_token
            
            # Try to get calendar info to verify connection
            calendars = await self._get_calendars_info(
                apple_id, 
                app_password, 
                connection.calendar_id.rsplit('/', 1)[0] + '/'
            )
            
            if calendars:
                connection.sync_status = SyncStatus.SYNCED
                connection.updated_at = datetime.utcnow()
                connection.last_sync_at = datetime.utcnow()
            else:
                connection.sync_status = SyncStatus.FAILED
            
            return connection
            
        except Exception as e:
            connection.sync_status = SyncStatus.FAILED
            self._handle_api_error(e, "Apple Calendar connection test")
    
    async def get_calendars(self, connection: CalendarConnection) -> List[Dict[str, Any]]:
        """
        Get list of user's Apple Calendars.
        
        Args:
            connection: Calendar connection
            
        Returns:
            List of calendar dictionaries
        """
        try:
            apple_id = connection.access_token
            app_password = connection.refresh_token
            
            # Get calendar home URL from connection
            calendar_home_url = connection.calendar_id.rsplit('/', 1)[0] + '/'
            
            calendars = await self._get_calendars_info(apple_id, app_password, calendar_home_url)
            
            return [
                {
                    'id': cal['href'],
                    'name': cal['displayname'],
                    'description': cal.get('description', ''),
                    'primary': cal.get('primary', False),
                    'color': cal.get('color', '#ffffff')
                }
                for cal in calendars
            ]
            
        except Exception as e:
            self._handle_api_error(e, "Get Apple Calendars")
    
    async def create_event(self, connection: CalendarConnection, event: CalendarEvent) -> str:
        """
        Create event in Apple Calendar.
        
        Args:
            connection: Calendar connection
            event: Event to create
            
        Returns:
            Event UID
        """
        try:
            apple_id = connection.access_token
            app_password = connection.refresh_token
            
            # Generate unique UID for the event
            event_uid = str(uuid.uuid4())
            
            # Convert to iCalendar format
            ical_data = self._to_ical_event(event, event_uid)
            
            # Create event URL
            event_url = f"{connection.calendar_id}{event_uid}.ics"
            
            # Send PUT request to create event
            response = requests.put(
                event_url,
                data=ical_data,
                auth=HTTPBasicAuth(apple_id, app_password),
                headers={
                    'Content-Type': 'text/calendar; charset=utf-8',
                    'If-None-Match': '*'
                }
            )
            
            if response.status_code not in [201, 204]:
                raise CalendarSyncError(f"Failed to create event: {response.status_code}")
            
            return event_uid
            
        except Exception as e:
            self._handle_api_error(e, "Create Apple Calendar event")
    
    async def update_event(self, connection: CalendarConnection, event: CalendarEvent) -> bool:
        """
        Update event in Apple Calendar.
        
        Args:
            connection: Calendar connection
            event: Event to update (must have external_id)
            
        Returns:
            True if successful
        """
        try:
            if not event.external_id:
                raise ValueError("Event must have external_id for updates")
            
            apple_id = connection.access_token
            app_password = connection.refresh_token
            
            # Convert to iCalendar format
            ical_data = self._to_ical_event(event, event.external_id)
            
            # Create event URL
            event_url = f"{connection.calendar_id}{event.external_id}.ics"
            
            # Send PUT request to update event
            response = requests.put(
                event_url,
                data=ical_data,
                auth=HTTPBasicAuth(apple_id, app_password),
                headers={
                    'Content-Type': 'text/calendar; charset=utf-8'
                }
            )
            
            if response.status_code not in [200, 204]:
                raise CalendarSyncError(f"Failed to update event: {response.status_code}")
            
            return True
            
        except Exception as e:
            self._handle_api_error(e, "Update Apple Calendar event")
    
    async def delete_event(self, connection: CalendarConnection, external_event_id: str) -> bool:
        """
        Delete event from Apple Calendar.
        
        Args:
            connection: Calendar connection
            external_event_id: Event UID
            
        Returns:
            True if successful
        """
        try:
            apple_id = connection.access_token
            app_password = connection.refresh_token
            
            # Create event URL
            event_url = f"{connection.calendar_id}{external_event_id}.ics"
            
            # Send DELETE request
            response = requests.delete(
                event_url,
                auth=HTTPBasicAuth(apple_id, app_password)
            )
            
            if response.status_code not in [200, 204, 404]:
                raise CalendarSyncError(f"Failed to delete event: {response.status_code}")
            
            return True
            
        except Exception as e:
            self._handle_api_error(e, "Delete Apple Calendar event")
    
    async def get_events(
        self, 
        connection: CalendarConnection, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[CalendarEvent]:
        """
        Get events from Apple Calendar within date range.
        
        Args:
            connection: Calendar connection
            start_date: Start date for event retrieval
            end_date: End date for event retrieval
            
        Returns:
            List of CalendarEvent objects
        """
        try:
            apple_id = connection.access_token
            app_password = connection.refresh_token
            
            # Create REPORT request body for date range query
            report_body = f'''<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop>
        <D:getetag />
        <C:calendar-data />
    </D:prop>
    <C:filter>
        <C:comp-filter name="VCALENDAR">
            <C:comp-filter name="VEVENT">
                <C:time-range start="{start_date.strftime('%Y%m%dT%H%M%SZ')}" 
                             end="{end_date.strftime('%Y%m%dT%H%M%SZ')}" />
            </C:comp-filter>
        </C:comp-filter>
    </C:filter>
</C:calendar-query>'''
            
            # Send REPORT request
            response = requests.request(
                'REPORT',
                connection.calendar_id,
                data=report_body,
                auth=HTTPBasicAuth(apple_id, app_password),
                headers={
                    'Content-Type': 'application/xml; charset=utf-8',
                    'Depth': '1'
                }
            )
            
            if response.status_code != 207:
                raise CalendarSyncError(f"Failed to get events: {response.status_code}")
            
            # Parse XML response
            events = self._parse_calendar_events(response.text)
            
            return events
            
        except Exception as e:
            self._handle_api_error(e, "Get Apple Calendar events")
    
    async def _discover_principal(self, apple_id: str, app_password: str) -> Optional[str]:
        """Discover principal URL for the user."""
        try:
            response = requests.request(
                'PROPFIND',
                f"{self.caldav_base_url}{self.principal_url}",
                auth=HTTPBasicAuth(apple_id, app_password),
                headers={
                    'Content-Type': 'application/xml; charset=utf-8',
                    'Depth': '0'
                },
                data='''<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:">
    <D:prop>
        <D:current-user-principal />
    </D:prop>
</D:propfind>'''
            )
            
            if response.status_code == 207:
                # Parse XML to get principal URL
                root = ET.fromstring(response.text)
                for response_elem in root.findall('.//{DAV:}response'):
                    href_elem = response_elem.find('.//{DAV:}current-user-principal/{DAV:}href')
                    if href_elem is not None:
                        return href_elem.text
            
            return None
            
        except Exception:
            return None
    
    async def _get_calendar_home(self, apple_id: str, app_password: str, principal_url: str) -> str:
        """Get calendar home URL."""
        try:
            response = requests.request(
                'PROPFIND',
                f"{self.caldav_base_url}{principal_url}",
                auth=HTTPBasicAuth(apple_id, app_password),
                headers={
                    'Content-Type': 'application/xml; charset=utf-8',
                    'Depth': '0'
                },
                data='''<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop>
        <C:calendar-home-set />
    </D:prop>
</D:propfind>'''
            )
            
            if response.status_code == 207:
                root = ET.fromstring(response.text)
                for response_elem in root.findall('.//{DAV:}response'):
                    href_elem = response_elem.find('.//{urn:ietf:params:xml:ns:caldav}calendar-home-set/{DAV:}href')
                    if href_elem is not None:
                        return f"{self.caldav_base_url}{href_elem.text}"
            
            raise CalendarSyncError("Could not find calendar home URL")
            
        except Exception as e:
            raise CalendarSyncError(f"Failed to get calendar home: {str(e)}")
    
    async def _get_calendars_info(self, apple_id: str, app_password: str, calendar_home_url: str) -> List[Dict[str, Any]]:
        """Get information about user's calendars."""
        try:
            response = requests.request(
                'PROPFIND',
                calendar_home_url,
                auth=HTTPBasicAuth(apple_id, app_password),
                headers={
                    'Content-Type': 'application/xml; charset=utf-8',
                    'Depth': '1'
                },
                data='''<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:CS="http://calendarserver.org/ns/">
    <D:prop>
        <D:displayname />
        <D:resourcetype />
        <C:supported-calendar-component-set />
        <CS:getctag />
    </D:prop>
</D:propfind>'''
            )
            
            if response.status_code != 207:
                return []
            
            calendars = []
            root = ET.fromstring(response.text)
            
            for response_elem in root.findall('.//{DAV:}response'):
                href_elem = response_elem.find('.//{DAV:}href')
                displayname_elem = response_elem.find('.//{DAV:}displayname')
                resourcetype_elem = response_elem.find('.//{DAV:}resourcetype')
                
                if (href_elem is not None and 
                    displayname_elem is not None and 
                    resourcetype_elem is not None):
                    
                    # Check if it's a calendar
                    if resourcetype_elem.find('.//{urn:ietf:params:xml:ns:caldav}calendar') is not None:
                        calendars.append({
                            'href': f"{self.caldav_base_url}{href_elem.text}",
                            'displayname': displayname_elem.text or 'Untitled Calendar',
                            'primary': len(calendars) == 0  # First calendar is primary
                        })
            
            return calendars
            
        except Exception as e:
            raise CalendarSyncError(f"Failed to get calendars info: {str(e)}")
    
    def _to_ical_event(self, event: CalendarEvent, event_uid: str) -> str:
        """Convert CalendarEvent to iCalendar format."""
        cal = Calendar()
        cal.add('prodid', '-//Ultimate Co-planner//Calendar Integration//EN')
        cal.add('version', '2.0')
        
        ical_event = ICalEvent()
        ical_event.add('uid', event_uid)
        ical_event.add('summary', event.title)
        ical_event.add('description', event.description or '')
        ical_event.add('location', event.location or '')
        ical_event.add('dtstamp', datetime.utcnow())
        ical_event.add('created', datetime.utcnow())
        ical_event.add('last-modified', datetime.utcnow())
        
        if event.all_day:
            ical_event.add('dtstart', event.start_time.date())
            if event.end_time:
                ical_event.add('dtend', event.end_time.date())
            else:
                ical_event.add('dtend', (event.start_time + timedelta(days=1)).date())
        else:
            timezone = pytz.timezone(event.timezone or 'UTC')
            start_dt = timezone.localize(event.start_time) if event.start_time.tzinfo is None else event.start_time
            end_dt = timezone.localize(event.end_time) if event.end_time and event.end_time.tzinfo is None else event.end_time
            
            ical_event.add('dtstart', start_dt)
            ical_event.add('dtend', end_dt or start_dt + timedelta(hours=1))
        
        # Add attendees
        for attendee_email in event.attendees or []:
            ical_event.add('attendee', f'mailto:{attendee_email}')
        
        # Add recurrence if specified
        if event.recurrence:
            ical_event.add('rrule', event.recurrence)
        
        cal.add_component(ical_event)
        
        return cal.to_ical().decode('utf-8')
    
    def _parse_calendar_events(self, xml_response: str) -> List[CalendarEvent]:
        """Parse CalDAV XML response to extract calendar events."""
        events = []
        
        try:
            root = ET.fromstring(xml_response)
            
            for response_elem in root.findall('.//{DAV:}response'):
                calendar_data_elem = response_elem.find('.//{urn:ietf:params:xml:ns:caldav}calendar-data')
                
                if calendar_data_elem is not None and calendar_data_elem.text:
                    try:
                        # Parse iCalendar data
                        cal = Calendar.from_ical(calendar_data_elem.text)
                        
                        for component in cal.walk():
                            if component.name == "VEVENT":
                                event = self._from_ical_event(component)
                                if event:
                                    events.append(event)
                    except Exception:
                        continue  # Skip malformed events
            
        except Exception:
            pass  # Return empty list if parsing fails
        
        return events
    
    def _from_ical_event(self, ical_event) -> Optional[CalendarEvent]:
        """Convert iCalendar event to CalendarEvent."""
        try:
            uid = str(ical_event.get('uid', ''))
            title = str(ical_event.get('summary', ''))
            description = str(ical_event.get('description', ''))
            location = str(ical_event.get('location', ''))
            
            # Parse start and end times
            dtstart = ical_event.get('dtstart')
            dtend = ical_event.get('dtend')
            
            if not dtstart:
                return None
            
            start_time = dtstart.dt
            end_time = dtend.dt if dtend else None
            
            # Determine if all-day event
            all_day = isinstance(start_time, datetime) == False
            
            # Convert to datetime if needed
            if all_day:
                start_time = datetime.combine(start_time, datetime.min.time())
                if end_time:
                    end_time = datetime.combine(end_time, datetime.min.time())
            
            # Extract timezone
            timezone = None
            if hasattr(start_time, 'tzinfo') and start_time.tzinfo:
                timezone = str(start_time.tzinfo)
            
            # Extract attendees
            attendees = []
            attendee_list = ical_event.get('attendee')
            if attendee_list:
                if not isinstance(attendee_list, list):
                    attendee_list = [attendee_list]
                
                for attendee in attendee_list:
                    email_match = re.search(r'mailto:([^@]+@[^@]+\.[^@]+)', str(attendee))
                    if email_match:
                        attendees.append(email_match.group(1))
            
            # Extract recurrence
            recurrence = None
            rrule = ical_event.get('rrule')
            if rrule:
                recurrence = str(rrule)
            
            return CalendarEvent(
                id=uid,
                title=title,
                description=description,
                start_time=start_time,
                end_time=end_time,
                location=location,
                attendees=attendees,
                all_day=all_day,
                timezone=timezone,
                recurrence=recurrence,
                external_id=uid,
                provider=CalendarProvider.APPLE
            )
            
        except Exception:
            return None