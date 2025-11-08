from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime,timedelta
from app.core.deps import get_db, get_current_user, get_current_active_user
from app.core.errors import (
    http_400_bad_request, http_404_not_found, http_403_forbidden
)
from app.services.event_service import EventService
from app.services.subscription_service import SubscriptionService, UsageLimitExceededError
from app.schemas.event import (
    EventCreate, EventUpdate, EventResponse, EventSummary, EventListResponse,
    EventInvitationCreate, EventInvitationUpdate, EventInvitationResponse,
    TaskCreate, TaskUpdate, TaskResponse, ExpenseCreate, ExpenseUpdate, ExpenseResponse,
    CommentCreate, CommentResponse, PollCreate, PollResponse, PollVoteCreate,
    EventSearchQuery, EventStatsResponse, EventLocationOptimizationRequest, EventLocationOptimizationResponse,
    EventDuplicateRequest
)
from app.repositories.event_repo import EventRepository
from app.schemas.location import (
    LocationAutocompleteRequest, LocationSuggestion, NearbyPlacesRequest, LocationUpdateRequest
)
from app.services.google_maps_service import google_maps_service
from app.schemas.pagination import PaginatedResponse, PaginationParams
from app.models.user_models import User
from app.models.shared_models import EventStatus, EventType
from app.models.event_models import Event, EventInvitation
from app.models.shared_models import RSVPStatus
from sqlalchemy import and_, or_

events_router = APIRouter()

# Event CRUD endpoints
@events_router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: EventCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new event"""
    try:
        # Check subscription limits before creating event
        subscription_service = SubscriptionService(db)
        subscription_service.check_event_limit(current_user.id)
        
        event_service = EventService(db)
        event = event_service.create_event(event_data, current_user.id)
        
        # Update usage after successful event creation
        subscription_service.increment_event_usage(current_user.id)
        
        return event
    except UsageLimitExceededError as e:
        raise http_403_forbidden(str(e))
    except Exception as e:
        if "after start date" in str(e).lower():
            raise http_400_bad_request("End date must be after start date")
        else:
            raise http_400_bad_request("Failed to create event")

@events_router.get("/", response_model=EventListResponse)
async def get_events(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Optional[EventStatus] = Query(None),
    event_type: Optional[EventType] = Query(None),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of events (public events or user's events)"""
    try:
        event_service = EventService(db)
        
        if current_user:
            # Get user's events
            events = event_service.get_user_events(
                current_user.id,
                status=status,
                skip=offset,
                limit=limit
            )
        else:
            # Get public events only
            events = event_service.search_events(
                query="",  # Empty query to get all
                user_id=None,
                skip=offset,
                limit=limit
            )
        
        # Convert to summary format
        event_summaries = [EventSummary.model_validate(event) for event in events]
        
        return EventListResponse(
            events=event_summaries,
            total=len(event_summaries),
            limit=limit,
            offset=offset
        )
    except Exception:
        raise http_400_bad_request("Failed to retrieve events")

@events_router.get("/search", response_model=EventListResponse)
async def search_events(
    q: str = Query(..., min_length=1, max_length=100, description="Search query"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search events by title, description, or venue"""
    try:
        event_service = EventService(db)
        events = event_service.search_events(
            query=q,
            user_id=current_user.id if current_user else None,
            skip=offset,
            limit=limit
        )
        
        event_summaries = [EventSummary.model_validate(event) for event in events]
        
        return EventListResponse(
            events=event_summaries,
            total=len(event_summaries),
            limit=limit,
            offset=offset
        )
    except Exception:
        raise http_400_bad_request("Search failed")

@events_router.get("/my", response_model=EventListResponse)
async def get_my_events(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Optional[EventStatus] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's events"""
    try:
        event_service = EventService(db)
        events = event_service.get_user_events(
            current_user.id,
            status=status,
            skip=offset,
            limit=limit
        )
        
        event_summaries = [EventSummary.model_validate(event) for event in events]
        
        return EventListResponse(
            events=event_summaries,
            total=len(event_summaries),
            limit=limit,
            offset=offset
        )
    except Exception:
        raise http_400_bad_request("Failed to retrieve user events")


@events_router.get("/my/upcoming", response_model=EventListResponse)
async def get_my_upcoming_events(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    days_ahead: int = Query(default=30, ge=1, le=365, description="Number of days ahead to look for events"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's upcoming events"""
    try:
        from app.repositories.event_repo import EventRepository
        from datetime import datetime, timedelta
        
        event_repo = EventRepository(db)
        
        # Get upcoming events for the user
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=days_ahead)
        
        # Use the existing get_events_by_date_range method with user filtering
        events = event_repo.get_events_by_date_range(
            start_date=start_date,
            end_date=end_date,
            user_id=current_user.id
        )
        
        # Apply pagination manually
        total_events = len(events)
        paginated_events = events[offset:offset + limit]
        
        event_summaries = [EventSummary.model_validate(event) for event in paginated_events]
        
        return EventListResponse(
            events=event_summaries,
            total=total_events,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        raise http_400_bad_request(f"Failed to retrieve upcoming events: {str(e)}")


@events_router.get("/my/past", response_model=EventListResponse)
async def get_my_past_events(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    days_back: int = Query(default=365, ge=1, le=3650, description="Number of days back to look for events"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's past events"""
    try:
        
        event_repo = EventRepository(db)
        
        # Get past events for the user
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        
        # Query past events (events that have ended)
        
        query = db.query(Event).filter(
            Event.end_datetime < end_date,
            Event.start_datetime >= start_date,
            Event.is_deleted == False
        )
        
        # Filter for user's events (created, collaborating, or invited)
        access_filter = or_(
            Event.creator_id == current_user.id,
            Event.collaborators.any(User.id == current_user.id),
            Event.invitations.any(EventInvitation.user_id == current_user.id)
        )
        query = query.filter(access_filter)
        
        # Order by most recent first
        query = query.order_by(Event.start_datetime.desc())
        
        # Get total count
        total_events = query.count()
        
        # Apply pagination
        events = query.offset(offset).limit(limit).all()
        
        event_summaries = [EventSummary.model_validate(event) for event in events]
        
        return EventListResponse(
            events=event_summaries,
            total=total_events,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        raise http_400_bad_request(f"Failed to retrieve past events: {str(e)}")

@events_router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get event by ID"""
    try:
        event_service = EventService(db)
        event = event_service.get_event_by_id(
            event_id, 
            user_id=current_user.id if current_user else None
        )
        
        if not event:
            raise http_404_not_found("Event not found")
        
        return event
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("Event not found")
        elif "access denied" in str(e).lower():
            raise http_403_forbidden("Access denied to this poll")
        else:
            raise http_400_bad_request("Failed to vote on poll")

# Location optimization endpoints
@events_router.post("/location/optimize", response_model=EventLocationOptimizationResponse)
async def optimize_event_location(
    request: EventLocationOptimizationRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Optimize event location using Google Maps API"""
    try:
        # Use Google Maps service to optimize location
        optimization_result = await google_maps_service.optimize_location_input(
            user_input=request.user_input,
            user_coordinates=request.user_coordinates,
            include_nearby=request.include_nearby,
            max_suggestions=request.max_suggestions
        )
        
        # Create event-specific response
        response = EventLocationOptimizationResponse(
            optimized=optimization_result.optimized,
            original_input=optimization_result.original_input,
            validation=optimization_result.validation,
            autocomplete_suggestions=optimization_result.autocomplete_suggestions,
            nearby_suggestions=optimization_result.nearby_suggestions,
            error=optimization_result.error
        )
        
        # Add recommended location if optimization was successful
        if optimization_result.optimized and optimization_result.validation.is_valid:
            from app.schemas.location import EnhancedLocation
            response.recommended_location = EnhancedLocation(
                venue_name=optimization_result.validation.formatted_address,
                venue_address=optimization_result.validation.formatted_address,
                coordinates=optimization_result.validation.coordinates,
                place_id=optimization_result.validation.place_id,
                formatted_address=optimization_result.validation.formatted_address,
                location_type=optimization_result.validation.location_type,
                is_verified=True
            )
        
        return response
    except Exception as e:
        raise http_400_bad_request(f"Failed to optimize location: {str(e)}")

@events_router.post("/location/autocomplete", response_model=List[LocationSuggestion])
async def autocomplete_location(
    request: LocationAutocompleteRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get location autocomplete suggestions"""
    try:
        suggestions = await google_maps_service.get_place_autocomplete(
            query=request.query,
            user_coordinates=request.user_coordinates,
            radius_meters=request.radius_meters,
            place_types=request.place_types
        )
        return suggestions
    except Exception as e:
        raise http_400_bad_request(f"Failed to get autocomplete suggestions: {str(e)}")

@events_router.post("/location/nearby", response_model=List[LocationSuggestion])
async def get_nearby_places(
    request: NearbyPlacesRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get nearby places for event location"""
    try:
        places = await google_maps_service.search_nearby_places(
            coordinates=request.coordinates,
            radius_meters=request.radius_meters,
            place_type=request.place_type,
            keyword=request.keyword
        )
        return places
    except Exception as e:
        raise http_400_bad_request(f"Failed to get nearby places: {str(e)}")

@events_router.put("/{event_id}/location", response_model=EventResponse)
async def update_event_location(
    event_id: int,
    request: LocationUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update event location with optimization"""
    try:
        event_service = EventService(db)
        
        # First optimize the location input
        if request.auto_verify:
            optimization_result = await google_maps_service.optimize_location_input(
                user_input=request.location_input,
                user_coordinates=request.user_coordinates,
                include_nearby=False,
                max_suggestions=1
            )
            
            if optimization_result.optimized and optimization_result.validation.is_valid:
                # Update event with optimized location data
                update_data = EventUpdate(
                    venue_address=optimization_result.validation.formatted_address,
                    latitude=optimization_result.validation.coordinates.latitude if optimization_result.validation.coordinates else None,
                    longitude=optimization_result.validation.coordinates.longitude if optimization_result.validation.coordinates else None
                )
                
                event = event_service.update_event(event_id, update_data, current_user.id)
                
                # Update additional location fields if the event model supports them
                # This would require updating the Event model to include place_id, etc.
                
                return event
            else:
                raise http_400_bad_request("Could not verify location. Please check the address.")
        else:
            # Simple location update without verification
            update_data = EventUpdate(venue_address=request.location_input)
            event = event_service.update_event(event_id, update_data, current_user.id)
            return event
            
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("Event not found")
        elif "permission" in str(e).lower() or "access denied" in str(e).lower():
            raise http_403_forbidden("Permission denied to update this event")
        else:
            raise http_400_bad_request(f"Failed to update event location: {str(e)}")

@events_router.put("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: int,
    event_data: EventUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update event"""
    try:
        event_service = EventService(db)
        event = event_service.update_event(event_id, event_data, current_user.id)
        return event
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("Event not found")
        elif "permission denied" in str(e).lower():
            raise http_403_forbidden("Permission denied to edit this event")
        elif "after start date" in str(e).lower():
            raise http_400_bad_request("End date must be after start date")
        else:
            raise http_400_bad_request("Failed to update event")

@events_router.delete("/{event_id}")
async def delete_event(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete event"""
    try:
        event_service = EventService(db)
        success = event_service.delete_event(event_id, current_user.id)
        
        return {
            "message": "Event deleted successfully",
            "success": success
        }
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("Event not found")
        elif "only event creator" in str(e).lower():
            raise http_403_forbidden("Only event creator can delete the event")
        else:
            raise http_400_bad_request("Failed to delete event")

@events_router.post("/{event_id}/duplicate", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_event(
    event_id: int,
    duplicate_data: EventDuplicateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Duplicate an existing event"""
    try:
        # Check subscription limits before duplicating event
        subscription_service = SubscriptionService(db)
        subscription_service.check_event_limit(current_user.id)
        
        event_service = EventService(db)
        duplicated_event = event_service.duplicate_event(
            event_id, 
            current_user.id, 
            duplicate_data.new_title
        )
        
        # Update usage after successful event duplication
        subscription_service.increment_event_usage(current_user.id)
        
        return duplicated_event
    except UsageLimitExceededError as e:
        raise http_403_forbidden(str(e))
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("Event not found")
        elif "permission denied" in str(e).lower():
            raise http_403_forbidden("Permission denied to access this event")
        else:
            raise http_400_bad_request("Failed to duplicate event")

@events_router.get("/{event_id}/stats", response_model=EventStatsResponse)
async def get_event_stats(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get event statistics"""
    try:
        event_service = EventService(db)
        stats = event_service.get_event_stats(event_id, current_user.id)
        return stats
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("Event not found")
        elif "access denied" in str(e).lower():
            raise http_403_forbidden("Access denied to this event")
        else:
            raise http_400_bad_request("Failed to retrieve event statistics")

# Event invitation endpoints
@events_router.post("/{event_id}/invitations", response_model=List[EventInvitationResponse], status_code=status.HTTP_201_CREATED)
async def invite_users(
    event_id: int,
    invitation_data: EventInvitationCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Invite users to an event"""
    try:
        event_service = EventService(db)
        invitations = event_service.invite_users(event_id, invitation_data, current_user.id)
        return invitations
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("Event not found")
        elif "permission denied" in str(e).lower():
            raise http_403_forbidden("Permission denied to invite users")
        else:
            raise http_400_bad_request("Failed to send invitations")

@events_router.get("/{event_id}/invitations", response_model=List[EventInvitationResponse])
async def get_event_invitations(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all invitations for an event"""
    try:
        event_service = EventService(db)
        invitations = event_service.get_event_invitations(event_id, current_user.id)
        return invitations
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("Event not found")
        elif "permission denied" in str(e).lower():
            raise http_403_forbidden("Permission denied to view invitations")
        else:
            raise http_400_bad_request("Failed to retrieve invitations")

@events_router.put("/invitations/{invitation_id}", response_model=EventInvitationResponse)
async def respond_to_invitation(
    invitation_id: int,
    response_data: EventInvitationUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Respond to event invitation"""
    try:
        event_service = EventService(db)
        invitation = event_service.respond_to_invitation(invitation_id, response_data, current_user.id)
        return invitation
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("Invitation not found")
        else:
            raise http_400_bad_request("Failed to respond to invitation")

# Task management endpoints
@events_router.post("/{event_id}/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    event_id: int,
    task_data: TaskCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a task for an event"""
    try:
        event_service = EventService(db)
        task = event_service.create_task(event_id, task_data, current_user.id)
        return task
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("Event or assignee not found")
        elif "permission denied" in str(e).lower():
            raise http_403_forbidden("Permission denied to create tasks")
        else:
            raise http_400_bad_request("Failed to create task")

@events_router.get("/{event_id}/tasks", response_model=List[TaskResponse])
async def get_event_tasks(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all tasks for an event"""
    try:
        event_service = EventService(db)
        tasks = event_service.get_event_tasks(event_id, current_user.id)
        return tasks
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("Event not found")
        elif "access denied" in str(e).lower():
            raise http_403_forbidden("Access denied to this event")
        else:
            raise http_400_bad_request("Failed to retrieve tasks")

@events_router.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a task"""
    try:
        event_service = EventService(db)
        task = event_service.update_task(task_id, task_data, current_user.id)
        return task
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("Task not found")
        elif "permission denied" in str(e).lower():
            raise http_403_forbidden("Permission denied to edit this task")
        else:
            raise http_400_bad_request("Failed to update task")

# Expense management endpoints
@events_router.post("/{event_id}/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    event_id: int,
    expense_data: ExpenseCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create an expense for an event"""
    try:
        event_service = EventService(db)
        expense = event_service.create_expense(event_id, expense_data, current_user.id)
        return expense
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("Event not found")
        elif "permission denied" in str(e).lower():
            raise http_403_forbidden("Permission denied to add expenses")
        else:
            raise http_400_bad_request("Failed to create expense")

@events_router.get("/{event_id}/expenses", response_model=List[ExpenseResponse])
async def get_event_expenses(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all expenses for an event"""
    try:
        event_service = EventService(db)
        expenses = event_service.get_event_expenses(event_id, current_user.id)
        return expenses
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("Event not found")
        elif "access denied" in str(e).lower():
            raise http_403_forbidden("Access denied to this event")
        else:
            raise http_400_bad_request("Failed to retrieve expenses")

# Comment endpoints
@events_router.post("/{event_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    event_id: int,
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a comment on an event"""
    try:
        event_service = EventService(db)
        comment = event_service.create_comment(event_id, comment_data, current_user.id)
        return comment
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("Event not found")
        elif "access denied" in str(e).lower():
            raise http_403_forbidden("Access denied to this event")
        else:
            raise http_400_bad_request("Failed to create comment")

@events_router.get("/{event_id}/comments", response_model=List[CommentResponse])
async def get_event_comments(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all comments for an event"""
    try:
        event_service = EventService(db)
        comments = event_service.get_event_comments(event_id, current_user.id)
        return comments
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("Event not found")
        elif "access denied" in str(e).lower():
            raise http_403_forbidden("Access denied to this event")
        else:
            raise http_400_bad_request("Failed to retrieve comments")

# Poll endpoints
@events_router.post("/{event_id}/polls", response_model=PollResponse, status_code=status.HTTP_201_CREATED)
async def create_poll(
    event_id: int,
    poll_data: PollCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a poll for an event"""
    try:
        event_service = EventService(db)
        poll = event_service.create_poll(event_id, poll_data, current_user.id)
        return poll
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("Event not found")
        elif "permission denied" in str(e).lower():
            raise http_403_forbidden("Permission denied to create polls")
        else:
            raise http_400_bad_request("Failed to create poll")

@events_router.post("/polls/{poll_id}/vote")
async def vote_on_poll(
    poll_id: int,
    vote_data: PollVoteCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Vote on a poll"""
    try:
        event_service = EventService(db)
        votes = event_service.vote_on_poll(poll_id, vote_data, current_user.id)
        
        return {
            "message": "Vote recorded successfully",
            "votes_count": len(votes)
        }
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found("Poll not found")
        elif "access denied" in str(e).lower():
            raise http_403_forbidden("Access denied to this poll")
        elif "closed" in str(e).lower():
            raise http_400_bad_request("Poll is closed")
        else:
            raise http_400_bad_request("Failed to record vote")