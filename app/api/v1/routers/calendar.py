"""
Calendar integration API endpoints.
Provides REST API for calendar integration management.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer

from app.schemas.calendar import (
    CalendarConnectionResponse, CalendarConnectionListResponse,
    CalendarEventResponse, CalendarEventListResponse,
    CalendarInfoResponse, CalendarInfoListResponse,
    CalendarAuthUrlResponse, CalendarSyncResponse, CalendarStatsResponse,
    GoogleCalendarAuthRequest, AppleCalendarAuthRequest,
    CalendarConnectionUpdateRequest, CalendarEventCreateRequest,
    CalendarEventUpdateRequest, CalendarSyncRequest
)
from app.services.calendar_service import CalendarServiceFactory, CalendarProvider
from app.services.google_calendar_service import GoogleCalendarService
from app.services.apple_calendar_service import AppleCalendarService
from app.repositories.calendar_repo import CalendarConnectionRepository, CalendarEventRepository, CalendarSyncLogRepository
from app.core.auth import get_current_user
from app.core.deps import get_db
from app.models.user import User
from sqlalchemy.orm import Session

router = APIRouter(prefix="/calendar", tags=["Calendar Integration"])
security = HTTPBearer()


# Calendar service factory instance
calendar_factory = CalendarServiceFactory()


@router.get("/auth/{provider}/url", response_model=CalendarAuthUrlResponse)
async def get_auth_url(
    provider: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get authorization URL for calendar provider.
    
    Args:
        provider: Calendar provider (google, apple, outlook)
        current_user: Current authenticated user
        
    Returns:
        Authorization URL and instructions
    """
    try:
        # Validate provider
        if provider not in ["google", "apple", "outlook"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid calendar provider. Supported: google, apple, outlook"
            )
        
        # Get service instance
        service = calendar_factory.get_service(CalendarProvider(provider.upper()))
        
        # Get authorization URL
        auth_url = service.get_authorization_url(current_user.id)
        
        # Prepare instructions based on provider
        instructions = {
            "google": "Click the link to authorize access to your Google Calendar",
            "apple": "Generate an app-specific password in your Apple ID settings and use it with your Apple ID",
            "outlook": "Click the link to authorize access to your Outlook Calendar"
        }
        
        return CalendarAuthUrlResponse(
            auth_url=auth_url,
            provider=provider,
            instructions=instructions.get(provider)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get authorization URL: {str(e)}"
        )


@router.post("/auth/google", response_model=CalendarConnectionResponse)
async def authenticate_google_calendar(
    request: GoogleCalendarAuthRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Authenticate with Google Calendar using OAuth code.
    
    Args:
        request: Google Calendar authentication request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Calendar connection details
    """
    try:
        service = GoogleCalendarService()
        connection = await service.authenticate(current_user.id, request.auth_code)
        
        # Save connection to database
        connection_repo = CalendarConnectionRepository(db)
        
        # Check if connection already exists
        existing_connection = connection_repo.get_by_provider_and_calendar_id(
            current_user.id, 
            connection.provider, 
            connection.calendar_id
        )
        
        if existing_connection:
            # Update existing connection
            existing_connection.access_token = connection.access_token
            existing_connection.refresh_token = connection.refresh_token
            existing_connection.expires_at = connection.expires_at
            existing_connection.sync_status = connection.sync_status
            existing_connection.last_sync_at = connection.last_sync_at
            saved_connection = connection_repo.update(existing_connection)
        else:
            # Create new connection
            connection_data = {
                'user_id': connection.user_id,
                'provider': connection.provider,
                'calendar_id': connection.calendar_id,
                'calendar_name': connection.calendar_name,
                'access_token': connection.access_token,
                'refresh_token': connection.refresh_token,
                'expires_at': connection.expires_at,
                'sync_status': connection.sync_status,
                'sync_enabled': connection.sync_enabled,
                'last_sync_at': connection.last_sync_at,
                'created_at': connection.created_at,
                'updated_at': connection.updated_at
            }
            saved_connection = connection_repo.create(connection_data)
        
        return CalendarConnectionResponse(
            id=saved_connection.id,
            user_id=saved_connection.user_id,
            provider=saved_connection.provider.value.lower(),
            calendar_id=saved_connection.calendar_id,
            calendar_name=saved_connection.calendar_name,
            sync_status=saved_connection.sync_status.value.lower(),
            sync_enabled=saved_connection.sync_enabled,
            last_sync_at=saved_connection.last_sync_at,
            created_at=saved_connection.created_at,
            updated_at=saved_connection.updated_at
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google Calendar authentication failed: {str(e)}"
        )


@router.post("/auth/apple", response_model=CalendarConnectionResponse)
async def authenticate_apple_calendar(
    request: AppleCalendarAuthRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Authenticate with Apple Calendar using Apple ID and app password.
    
    Args:
        request: Apple Calendar authentication request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Calendar connection details
    """
    try:
        service = AppleCalendarService()
        connection = await service.authenticate(
            current_user.id, 
            request.apple_id, 
            request.app_password
        )
        
        # Save connection to database
        connection_repo = CalendarConnectionRepository(db)
        
        # Check if connection already exists
        existing_connection = connection_repo.get_by_provider_and_calendar_id(
            current_user.id, 
            connection.provider, 
            connection.calendar_id
        )
        
        if existing_connection:
            # Update existing connection
            existing_connection.access_token = connection.access_token
            existing_connection.refresh_token = connection.refresh_token
            existing_connection.sync_status = connection.sync_status
            existing_connection.last_sync_at = connection.last_sync_at
            saved_connection = connection_repo.update(existing_connection)
        else:
            # Create new connection
            connection_data = {
                'user_id': connection.user_id,
                'provider': connection.provider,
                'calendar_id': connection.calendar_id,
                'calendar_name': connection.calendar_name,
                'access_token': connection.access_token,
                'refresh_token': connection.refresh_token,
                'expires_at': connection.expires_at,
                'sync_status': connection.sync_status,
                'sync_enabled': connection.sync_enabled,
                'last_sync_at': connection.last_sync_at,
                'created_at': connection.created_at,
                'updated_at': connection.updated_at
            }
            saved_connection = connection_repo.create(connection_data)
        
        return CalendarConnectionResponse(
            id=saved_connection.id,
            user_id=saved_connection.user_id,
            provider=saved_connection.provider.value.lower(),
            calendar_id=saved_connection.calendar_id,
            calendar_name=saved_connection.calendar_name,
            sync_status=saved_connection.sync_status.value.lower(),
            sync_enabled=saved_connection.sync_enabled,
            last_sync_at=saved_connection.last_sync_at,
            created_at=saved_connection.created_at,
            updated_at=saved_connection.updated_at
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Apple Calendar authentication failed: {str(e)}"
        )


@router.get("/connections", response_model=CalendarConnectionListResponse)
async def get_calendar_connections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    active_only: bool = Query(False, description="Show only active connections")
):
    """
    Get user's calendar connections.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        provider: Optional provider filter
        active_only: Show only active connections
        
    Returns:
        List of calendar connections
    """
    try:
        connection_repo = CalendarConnectionRepository(db)
        connections = connection_repo.get_by_user_id(
            current_user.id, 
            provider=provider, 
            active_only=active_only
        )
        
        connection_responses = [
            CalendarConnectionResponse(
                id=conn.id,
                user_id=conn.user_id,
                provider=conn.provider.value.lower(),
                calendar_id=conn.calendar_id,
                calendar_name=conn.calendar_name,
                sync_status=conn.sync_status.value.lower(),
                sync_enabled=conn.sync_enabled,
                last_sync_at=conn.last_sync_at,
                created_at=conn.created_at,
                updated_at=conn.updated_at
            )
            for conn in connections
        ]
        
        return CalendarConnectionListResponse(
            connections=connection_responses,
            total=len(connection_responses)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get calendar connections: {str(e)}"
        )


@router.get("/connections/{connection_id}", response_model=CalendarConnectionResponse)
async def get_calendar_connection(
    connection_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Get specific calendar connection.
    
    Args:
        connection_id: Calendar connection ID
        current_user: Current authenticated user
        
    Returns:
        Calendar connection details
    """
    try:
        # TODO: Implement database query
        # connection = connection_repo.get_by_id_and_user(connection_id, current_user.id)
        # if not connection:
        #     raise HTTPException(status_code=404, detail="Calendar connection not found")
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendar connection not found"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get calendar connection: {str(e)}"
        )


@router.put("/connections/{connection_id}", response_model=CalendarConnectionResponse)
async def update_calendar_connection(
    connection_id: int,
    update_data: CalendarConnectionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a calendar connection.
    
    Args:
        connection_id: ID of the connection to update
        update_data: Update data
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Updated calendar connection
    """
    try:
        connection_repo = CalendarConnectionRepository(db)
        
        # Get existing connection and verify ownership
        connection = connection_repo.get_by_id(connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Calendar connection not found"
            )
        
        if connection.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this connection"
            )
        
        # Update connection
        updated_connection = connection_repo.update(connection_id, update_data.model_dump(exclude_unset=True))
        
        return CalendarConnectionResponse(
            id=updated_connection.id,
            user_id=updated_connection.user_id,
            provider=updated_connection.provider.value.lower(),
            calendar_id=updated_connection.calendar_id,
            calendar_name=updated_connection.calendar_name,
            sync_status=updated_connection.sync_status.value.lower(),
            sync_enabled=updated_connection.sync_enabled,
            last_sync_at=updated_connection.last_sync_at,
            created_at=updated_connection.created_at,
            updated_at=updated_connection.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update calendar connection: {str(e)}"
        )


@router.delete("/connections/{connection_id}")
async def delete_calendar_connection(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a calendar connection.
    
    Args:
        connection_id: ID of the connection to delete
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Success message
    """
    try:
        connection_repo = CalendarConnectionRepository(db)
        
        # Get existing connection and verify ownership
        connection = connection_repo.get_by_id(connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Calendar connection not found"
            )
        
        if connection.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this connection"
            )
        
        # Delete connection
        connection_repo.delete(connection_id)
        
        return {"message": "Calendar connection deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete calendar connection: {str(e)}"
        )


@router.get("/connections/{connection_id}/calendars", response_model=CalendarInfoListResponse)
async def get_external_calendars(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of external calendars for a connection.
    
    Args:
        connection_id: Calendar connection ID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        List of external calendars
    """
    try:
        connection_repo = CalendarConnectionRepository(db)
        
        # Get connection and verify ownership
        connection = connection_repo.get_by_id(connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Calendar connection not found"
            )
        
        if connection.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this connection"
            )
        
        # Get calendar service based on provider
        if connection.provider.value.lower() == "google":
            from app.services.google_calendar_service import GoogleCalendarService
            service = GoogleCalendarService()
            calendars = await service.get_calendars(connection)
        elif connection.provider.value.lower() == "apple":
            from app.services.apple_calendar_service import AppleCalendarService
            service = AppleCalendarService()
            calendars = await service.get_calendars(connection)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported provider: {connection.provider.value}"
            )
        
        return CalendarInfoListResponse(
            calendars=calendars,
            provider=connection.provider.value.lower()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get external calendars: {str(e)}"
        )


@router.post("/connections/{connection_id}/sync", response_model=CalendarSyncResponse)
async def sync_calendar(
    connection_id: int,
    request: CalendarSyncRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sync calendar events with external calendar.
    
    Args:
        connection_id: Calendar connection ID
        request: Sync request parameters
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Sync results
    """
    try:
        connection_repo = CalendarConnectionRepository(db)
        sync_log_repo = CalendarSyncLogRepository(db)
        
        # Get connection and verify ownership
        connection = connection_repo.get_by_id(connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Calendar connection not found"
            )
        
        if connection.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to sync this connection"
            )
        
        # Set default date range if not provided
        start_date = request.start_date or datetime.utcnow() - timedelta(days=30)
        end_date = request.end_date or datetime.utcnow() + timedelta(days=90)
        
        sync_started_at = datetime.utcnow()
        
        try:
            # Update connection status to syncing
            connection_repo.update(connection_id, {"sync_status": "syncing"})
            
            # Get calendar service based on provider
            if connection.provider.value.lower() == "google":
                from app.services.google_calendar_service import GoogleCalendarService
                service = GoogleCalendarService()
            elif connection.provider.value.lower() == "apple":
                from app.services.apple_calendar_service import AppleCalendarService
                service = AppleCalendarService()
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported provider: {connection.provider.value}"
                )
            
            # Perform sync
            sync_result = await service.sync_events(connection, start_date, end_date, request.force_sync)
            
            # Update connection status and last sync time
            connection_repo.update(connection_id, {
                "sync_status": "active",
                "last_sync_at": datetime.utcnow()
            })
            
            # Log sync result
            sync_log_repo.create({
                "connection_id": connection_id,
                "sync_type": "manual" if request.force_sync else "incremental",
                "status": "success",
                "events_processed": sync_result.get("events_synced", 0),
                "events_created": sync_result.get("events_created", 0),
                "events_updated": sync_result.get("events_updated", 0),
                "events_deleted": sync_result.get("events_deleted", 0),
                "started_at": sync_started_at,
                "completed_at": datetime.utcnow()
            })
            
            return CalendarSyncResponse(
                connection_id=connection_id,
                sync_status="synced",
                events_synced=sync_result.get("events_synced", 0),
                events_created=sync_result.get("events_created", 0),
                events_updated=sync_result.get("events_updated", 0),
                events_deleted=sync_result.get("events_deleted", 0),
                sync_started_at=sync_started_at,
                sync_completed_at=datetime.utcnow(),
                error_message=None
            )
            
        except Exception as sync_error:
            # Update connection status to error
            connection_repo.update(connection_id, {"sync_status": "error"})
            
            # Log sync error
            sync_log_repo.create({
                "connection_id": connection_id,
                "sync_type": "manual" if request.force_sync else "incremental",
                "status": "error",
                "error_message": str(sync_error),
                "started_at": sync_started_at,
                "completed_at": datetime.utcnow()
            })
            
            return CalendarSyncResponse(
                connection_id=connection_id,
                sync_status="error",
                events_synced=0,
                events_created=0,
                events_updated=0,
                events_deleted=0,
                sync_started_at=sync_started_at,
                sync_completed_at=datetime.utcnow(),
                error_message=str(sync_error)
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync calendar: {str(e)}"
        )


@router.get("/events", response_model=CalendarEventListResponse)
async def get_calendar_events(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    provider: Optional[str] = Query(None, description="Provider filter"),
    limit: int = Query(50, ge=1, le=100, description="Number of events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip")
):
    """
    Get user's calendar events.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        start_date: Start date filter
        end_date: End date filter
        provider: Provider filter
        limit: Number of events to return
        offset: Number of events to skip
        
    Returns:
        List of calendar events
    """
    try:
        event_repo = CalendarEventRepository(db)
        
        events = event_repo.get_by_user_id(
            current_user.id,
            start_date=start_date,
            end_date=end_date,
            provider=provider,
            limit=limit,
            offset=offset
        )
        
        event_responses = [
            CalendarEventResponse(
                id=event.id,
                connection_id=event.connection_id,
                external_event_id=event.external_event_id,
                title=event.title,
                description=event.description,
                start_time=event.start_time,
                end_time=event.end_time,
                all_day=event.all_day,
                location=event.location,
                attendees=event.attendees or [],
                recurrence_rule=event.recurrence_rule,
                status=event.status.value.lower() if event.status else "confirmed",
                created_at=event.created_at,
                updated_at=event.updated_at
            )
            for event in events
        ]
        
        return CalendarEventListResponse(
            events=event_responses,
            total=len(event_responses)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get calendar events: {str(e)}"
        )


@router.post("/events", response_model=CalendarEventResponse)
async def create_calendar_event(
    request: CalendarEventCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new calendar event.
    
    Args:
        request: Event creation request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Created calendar event
    """
    try:
        event_repo = CalendarEventRepository(db)
        connection_repo = CalendarConnectionRepository(db)
        
        # Create event data
        event_data = {
            "title": request.title,
            "description": request.description,
            "start_time": request.start_time,
            "end_time": request.end_time,
            "location": request.location,
            "attendees": request.attendees,
            "all_day": request.all_day,
            "timezone": request.timezone,
            "recurrence_rule": request.recurrence,
            "status": "confirmed"
        }
        
        # Create the event in database
        created_event = event_repo.create(event_data)
        
        # Sync to external calendars if requested
        if request.sync_to_external:
            connections = connection_repo.get_by_user_id(current_user.id, active_only=True)
            
            for connection in connections:
                try:
                    # Get calendar service based on provider
                    if connection.provider.value.lower() == "google":
                        from app.services.google_calendar_service import GoogleCalendarService
                        service = GoogleCalendarService()
                    elif connection.provider.value.lower() == "apple":
                        from app.services.apple_calendar_service import AppleCalendarService
                        service = AppleCalendarService()
                    else:
                        continue  # Skip unsupported providers
                    
                    # Create event in external calendar
                    external_id = await service.create_event(connection, created_event)
                    
                    # Update event with external ID and connection
                    event_repo.update(created_event.id, {
                        "external_event_id": external_id,
                        "connection_id": connection.id
                    })
                    
                except Exception as sync_error:
                    # Log sync error but don't fail the entire operation
                    print(f"Failed to sync event to {connection.provider.value}: {sync_error}")
        
        # Refresh event to get updated data
        updated_event = event_repo.get_by_id(created_event.id)
        
        return CalendarEventResponse(
            id=updated_event.id,
            connection_id=updated_event.connection_id,
            external_event_id=updated_event.external_event_id,
            title=updated_event.title,
            description=updated_event.description,
            start_time=updated_event.start_time,
            end_time=updated_event.end_time,
            all_day=updated_event.all_day,
            location=updated_event.location,
            attendees=updated_event.attendees or [],
            recurrence_rule=updated_event.recurrence_rule,
            status=updated_event.status.value.lower() if updated_event.status else "confirmed",
            created_at=updated_event.created_at,
            updated_at=updated_event.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create calendar event: {str(e)}"
        )


@router.put("/events/{event_id}", response_model=CalendarEventResponse)
async def update_calendar_event(
    event_id: int,
    request: CalendarEventUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a calendar event.
    
    Args:
        event_id: Event ID
        request: Event update request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Updated calendar event
    """
    try:
        event_repo = CalendarEventRepository(db)
        connection_repo = CalendarConnectionRepository(db)
        
        # Get existing event and verify ownership
        event = event_repo.get_by_id(event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Calendar event not found"
            )
        
        # Verify ownership through connection
        if event.connection_id:
            connection = connection_repo.get_by_id(event.connection_id)
            if not connection or connection.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to update this event"
                )
        
        # Update event in database
        update_data = request.model_dump(exclude_unset=True)
        updated_event = event_repo.update(event_id, update_data)
        
        # Sync to external calendar if event has external ID
        if updated_event.external_event_id and updated_event.connection_id:
            connection = connection_repo.get_by_id(updated_event.connection_id)
            if connection:
                try:
                    # Get calendar service based on provider
                    if connection.provider.value.lower() == "google":
                        from app.services.google_calendar_service import GoogleCalendarService
                        service = GoogleCalendarService()
                    elif connection.provider.value.lower() == "apple":
                        from app.services.apple_calendar_service import AppleCalendarService
                        service = AppleCalendarService()
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Unsupported provider: {connection.provider.value}"
                        )
                    
                    # Update event in external calendar
                    await service.update_event(connection, updated_event)
                    
                except Exception as sync_error:
                    # Log sync error but don't fail the entire operation
                    print(f"Failed to sync event update to {connection.provider.value}: {sync_error}")
        
        return CalendarEventResponse(
            id=updated_event.id,
            connection_id=updated_event.connection_id,
            external_event_id=updated_event.external_event_id,
            title=updated_event.title,
            description=updated_event.description,
            start_time=updated_event.start_time,
            end_time=updated_event.end_time,
            all_day=updated_event.all_day,
            location=updated_event.location,
            attendees=updated_event.attendees or [],
            recurrence_rule=updated_event.recurrence_rule,
            status=updated_event.status.value.lower() if updated_event.status else "confirmed",
            created_at=updated_event.created_at,
            updated_at=updated_event.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update calendar event: {str(e)}"
        )


@router.delete("/events/{event_id}")
async def delete_calendar_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a calendar event.
    
    Args:
        event_id: Event ID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Success message
    """
    try:
        event_repo = CalendarEventRepository(db)
        connection_repo = CalendarConnectionRepository(db)
        
        # Get existing event and verify ownership
        event = event_repo.get_by_id(event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Calendar event not found"
            )
        
        # Verify ownership through connection
        if event.connection_id:
            connection = connection_repo.get_by_id(event.connection_id)
            if not connection or connection.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to delete this event"
                )
        
        # Delete from external calendar if event has external ID
        if event.external_event_id and event.connection_id:
            connection = connection_repo.get_by_id(event.connection_id)
            if connection:
                try:
                    # Get calendar service based on provider
                    if connection.provider.value.lower() == "google":
                        from app.services.google_calendar_service import GoogleCalendarService
                        service = GoogleCalendarService()
                    elif connection.provider.value.lower() == "apple":
                        from app.services.apple_calendar_service import AppleCalendarService
                        service = AppleCalendarService()
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Unsupported provider: {connection.provider.value}"
                        )
                    
                    # Delete event from external calendar
                    await service.delete_event(connection, event.external_event_id)
                    
                except Exception as sync_error:
                    # Log sync error but don't fail the entire operation
                    print(f"Failed to delete event from {connection.provider.value}: {sync_error}")
        
        # Delete event from database
        event_repo.delete(event_id)
        
        return {"message": "Calendar event deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete calendar event: {str(e)}"
        )


@router.get("/stats", response_model=CalendarStatsResponse)
async def get_calendar_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get calendar integration statistics.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Calendar statistics
    """
    try:
        connection_repo = CalendarConnectionRepository(db)
        event_repo = CalendarEventRepository(db)
        sync_log_repo = CalendarSyncLogRepository(db)
        
        # Get connection statistics
        all_connections = connection_repo.get_by_user_id(current_user.id)
        active_connections = connection_repo.get_by_user_id(current_user.id, active_only=True)
        
        # Get event statistics
        total_events = event_repo.count_by_user_id(current_user.id)
        
        # Get last sync time
        last_sync_at = None
        if active_connections:
            # Get the most recent sync time from active connections
            for connection in active_connections:
                if connection.last_sync_at:
                    if last_sync_at is None or connection.last_sync_at > last_sync_at:
                        last_sync_at = connection.last_sync_at
        
        # Get sync error count (errors in the last 24 hours)
        from datetime import datetime, timedelta
        error_cutoff = datetime.utcnow() - timedelta(hours=24)
        sync_errors = sync_log_repo.count_errors_since(error_cutoff)
        
        return CalendarStatsResponse(
            total_connections=len(all_connections),
            active_connections=len(active_connections),
            total_events=total_events,
            last_sync_at=last_sync_at,
            sync_errors=sync_errors
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get calendar stats: {str(e)}"
        )