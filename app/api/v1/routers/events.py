from fastapi import APIRouter, Depends, HTTPException, status, Query, Response, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Optional, List
from datetime import datetime,timedelta
from app.core.deps import get_db, get_current_user, get_current_active_user
from app.core.errors import (
    http_400_bad_request, http_404_not_found, http_403_forbidden,
    AuthorizationError, NotFoundError, ValidationError
)
from app.services.event_service import EventService
from app.services.subscription_service import SubscriptionService, UsageLimitExceededError
from app.schemas.event import (
    EventCreate, EventUpdate, EventResponse, EventSummary, EventListResponse,
    EventInvitationCreate, EventInvitationUpdate, EventInvitationResponse,
    TaskCreate, TaskUpdate, TaskResponse, TaskCategoriesResponse, TaskCategory, TaskCategoryItem, TaskStatus,
    ExpenseCreate, ExpenseUpdate, ExpenseResponse,
    CommentCreate, CommentResponse, PollCreate, PollResponse, PollVoteCreate,
    EventSearchQuery, EventStatsResponse, EventLocationOptimizationRequest, EventLocationOptimizationResponse,
    EventDuplicateRequest, CollaboratorAddRequest
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
from app.schemas.user import UserSummary

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
        # TODO: Re-enable subscription limits after development
        # Check subscription limits before creating event
        # subscription_service = SubscriptionService()
        # can_create_event = await subscription_service.check_event_creation_limit(db, current_user.id)
        # if not can_create_event:
        #     raise http_403_forbidden("Event creation limit reached for current plan")
        
        event_service = EventService(db)
        event = event_service.create_event(event_data, current_user.id)
        
        # TODO: Re-enable usage tracking after development
        # Update usage after successful event creation
        # await subscription_service.increment_event_usage(db, current_user.id)
        
        return event
    except UsageLimitExceededError as e:
        raise http_403_forbidden(str(e))
    except ValidationError as e:
        # Log validation errors with details
        print(f"Event creation validation error for user {current_user.id} ({current_user.email}): {str(e)}")
        raise http_400_bad_request(str(e))
    except Exception as e:
        # Log the full error for debugging
        import traceback
        print(f"Event creation failed for user {current_user.id} ({current_user.email})")
        print(f"Error: {str(e)}")
        print(traceback.format_exc())
        
        if "after start date" in str(e).lower():
            raise http_400_bad_request("End date must be after start date")
        else:
            # Return the actual error message instead of generic one
            raise http_400_bad_request(f"Failed to create event: {str(e)}")

@events_router.post("/{event_id}/cover-image", response_model=EventResponse)
async def upload_event_cover_image(
    event_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload or update event cover image"""
    try:
        event_service = EventService(db)
        event = event_service.get_event_by_id(event_id)
        
        if not event:
            raise http_404_not_found("Event not found")
        
        # Check if user is creator or collaborator
        is_authorized = (
            event.creator_id == current_user.id or
            current_user in event.collaborators
        )
        
        if not is_authorized:
            raise http_403_forbidden("You don't have permission to update this event")
        
        # Validate file type
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
        if file.content_type not in allowed_types:
            raise http_400_bad_request("Invalid file type. Only JPEG, PNG, and WebP images are allowed")
        
        # Validate file size (max 10MB)
        file_content = await file.read()
        if len(file_content) > 10 * 1024 * 1024:
            raise http_400_bad_request("File size too large. Maximum size is 10MB")
        
        # Reset file pointer
        await file.seek(0)
        
        # Upload to GCS
        from app.services.gcp_storage_service import GCPStorageService
        storage_service = GCPStorageService()
        upload_result = await storage_service.upload_file(
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type,
            folder=f"events/{event_id}/cover",
            user_id=current_user.id,
            make_public=True
        )
        
        # Update event cover_image_url
        event.cover_image_url = upload_result["file_url"]
        db.commit()
        db.refresh(event)
        
        return event
        
    except HTTPException:
        raise
    except Exception as e:
        raise http_400_bad_request(f"Failed to upload cover image: {str(e)}")

@events_router.delete("/{event_id}/cover-image", response_model=EventResponse)
async def delete_event_cover_image(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete event cover image"""
    try:
        event_service = EventService(db)
        event = event_service.get_event_by_id(event_id)
        
        if not event:
            raise http_404_not_found("Event not found")
        
        # Check if user is creator or collaborator
        is_authorized = (
            event.creator_id == current_user.id or
            current_user in event.collaborators
        )
        
        if not is_authorized:
            raise http_403_forbidden("You don't have permission to update this event")
        
        if not event.cover_image_url:
            raise http_404_not_found("No cover image to delete")
        
        # Delete from GCS
        from app.services.gcp_storage_service import GCPStorageService
        storage_service = GCPStorageService()
        
        if "storage.googleapis.com" in event.cover_image_url:
            blob_path = event.cover_image_url.split("storage.googleapis.com/")[-1]
            await storage_service.delete_file(blob_path)
        else:
            await storage_service.delete_file(event.cover_image_url)
        
        # Clear cover_image_url
        event.cover_image_url = None
        db.commit()
        db.refresh(event)
        
        return event
        
    except HTTPException:
        raise
    except Exception as e:
        raise http_400_bad_request(f"Failed to delete cover image: {str(e)}")

@events_router.get("/", response_model=EventListResponse)
async def get_events(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    category: Optional[str] = Query(None, description="Filter by category: upcoming, past, drafts, hosting, attending, public"),
    event_type: Optional[EventType] = Query(None),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of events.
    
    Filter options:
    - category: 
        - upcoming: Events happening in the future (requires login)
        - past: Events that have already ended (requires login)
        - drafts: Events with draft status (requires login)
        - hosting: Events created by current user (requires login)
        - attending: Events user is invited to (requires login)
        - public: Public events (no login required)
    """
    try:
        event_repo = EventRepository(db)
        
        # Base query
        query = db.query(Event).filter(Event.is_deleted == False)
        
        # Apply category filters
        if category:
            category = category.lower()
            
            if category == "public":
                # Public events - no authentication required
                query = query.filter(Event.is_public == True, Event.status != EventStatus.DRAFT)
                query = query.order_by(Event.start_datetime.desc())
                
            elif not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required for this category"
                )
                
            elif category == "upcoming":
                # Future events (exclude drafts)
                query = query.filter(
                    Event.start_datetime >= datetime.utcnow(),
                    Event.status != EventStatus.DRAFT
                )
                access_filter = or_(
                    Event.creator_id == current_user.id,
                    Event.collaborators.any(User.id == current_user.id),
                    Event.invitations.any(EventInvitation.user_id == current_user.id)
                )
                query = query.filter(access_filter)
                query = query.order_by(Event.start_datetime.asc())
                
            elif category == "past":
                # Past events (exclude drafts)
                query = query.filter(
                    Event.end_datetime < datetime.utcnow(),
                    Event.status != EventStatus.DRAFT
                )
                access_filter = or_(
                    Event.creator_id == current_user.id,
                    Event.collaborators.any(User.id == current_user.id),
                    Event.invitations.any(EventInvitation.user_id == current_user.id)
                )
                query = query.filter(access_filter)
                query = query.order_by(Event.start_datetime.desc())
                
            elif category == "drafts":
                # Draft events only
                query = query.filter(Event.status == EventStatus.DRAFT)
                access_filter = or_(
                    Event.creator_id == current_user.id,
                    Event.collaborators.any(User.id == current_user.id),
                    Event.invitations.any(EventInvitation.user_id == current_user.id)
                )
                query = query.filter(access_filter)
                query = query.order_by(Event.start_datetime.desc())
                
            elif category == "hosting":
                # Events created by user (all statuses)
                query = query.filter(Event.creator_id == current_user.id)
                query = query.order_by(Event.start_datetime.desc())
                
            elif category == "attending":
                # Events user is invited to (not creator, exclude drafts)
                query = query.filter(
                    Event.creator_id != current_user.id,
                    Event.invitations.any(EventInvitation.user_id == current_user.id),
                    Event.status != EventStatus.DRAFT
                )
                query = query.order_by(Event.start_datetime.desc())
            else:
                raise http_400_bad_request(f"Invalid category: {category}. Use: upcoming, past, drafts, hosting, attending, or public")
        
        else:
            # No category specified
            if current_user:
                # Return all events user has access to (exclude drafts unless they're the creator)
                access_filter = or_(
                    Event.creator_id == current_user.id,
                    and_(
                        Event.status != EventStatus.DRAFT,
                        or_(
                            Event.collaborators.any(User.id == current_user.id),
                            Event.invitations.any(EventInvitation.user_id == current_user.id)
                        )
                    )
                )
                query = query.filter(access_filter)
            else:
                # Return public events only
                query = query.filter(Event.is_public == True, Event.status != EventStatus.DRAFT)
            
            query = query.order_by(Event.start_datetime.desc())
        
        # Apply event_type filter if provided
        if event_type:
            query = query.filter(Event.event_type == event_type)
        
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
    except HTTPException:
        raise
    except Exception as e:
        raise http_400_bad_request(f"Failed to retrieve events: {str(e)}")

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
    category: Optional[str] = Query(None, description="Filter by category: upcoming, past, drafts, hosting, attending"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's events.
    
    Filter options:
    - category: 
        - upcoming: Events happening in the future
        - past: Events that have already ended
        - drafts: Events with draft status
        - hosting: Events created by current user
        - attending: Events user is invited to (not creator)
    """
    try:
        event_repo = EventRepository(db)
        
        # Base query for user's events
        query = db.query(Event).filter(Event.is_deleted == False)
        
        # Apply category filters
        if category:
            category = category.lower()
            
            if category == "upcoming":
                # Future events (exclude drafts)
                query = query.filter(
                    Event.start_datetime >= datetime.utcnow(),
                    Event.status != EventStatus.DRAFT
                )
                # Filter for user's events
                access_filter = or_(
                    Event.creator_id == current_user.id,
                    Event.collaborators.any(User.id == current_user.id),
                    Event.invitations.any(EventInvitation.user_id == current_user.id)
                )
                query = query.filter(access_filter)
                query = query.order_by(Event.start_datetime.asc())
                
            elif category == "past":
                # Past events (exclude drafts)
                query = query.filter(
                    Event.end_datetime < datetime.utcnow(),
                    Event.status != EventStatus.DRAFT
                )
                # Filter for user's events
                access_filter = or_(
                    Event.creator_id == current_user.id,
                    Event.collaborators.any(User.id == current_user.id),
                    Event.invitations.any(EventInvitation.user_id == current_user.id)
                )
                query = query.filter(access_filter)
                query = query.order_by(Event.start_datetime.desc())
                
            elif category == "drafts":
                # Draft events only (that user created or has access to)
                query = query.filter(Event.status == EventStatus.DRAFT)
                access_filter = or_(
                    Event.creator_id == current_user.id,
                    Event.collaborators.any(User.id == current_user.id),
                    Event.invitations.any(EventInvitation.user_id == current_user.id)
                )
                query = query.filter(access_filter)
                query = query.order_by(Event.start_datetime.desc())
                
            elif category == "hosting":
                # Events created by user (all statuses)
                query = query.filter(Event.creator_id == current_user.id)
                query = query.order_by(Event.start_datetime.desc())
                
            elif category == "attending":
                # Events user is invited to (not creator, exclude drafts)
                query = query.filter(
                    Event.creator_id != current_user.id,
                    Event.invitations.any(EventInvitation.user_id == current_user.id),
                    Event.status != EventStatus.DRAFT
                )
                query = query.order_by(Event.start_datetime.desc())
            else:
                raise http_400_bad_request(f"Invalid category: {category}. Use: upcoming, past, drafts, hosting, or attending")
        else:
            # No category - return all events user has access to (exclude drafts unless they're the creator)
            access_filter = or_(
                Event.creator_id == current_user.id,
                and_(
                    Event.status != EventStatus.DRAFT,
                    or_(
                        Event.collaborators.any(User.id == current_user.id),
                        Event.invitations.any(EventInvitation.user_id == current_user.id)
                    )
                )
            )
            query = query.filter(access_filter)
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
    except HTTPException:
        raise
    except Exception as e:
        raise http_400_bad_request(f"Failed to retrieve user events: {str(e)}")


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
        subscription_service = SubscriptionService()
        can_create_event = await subscription_service.check_event_creation_limit(db, current_user.id)
        if not can_create_event:
            raise http_403_forbidden("Event creation limit reached for current plan")
        
        event_service = EventService(db)
        duplicated_event = event_service.duplicate_event(
            event_id, 
            current_user.id, 
            duplicate_data.new_title
        )
        
        # Update usage after successful event duplication
        await subscription_service.increment_event_usage(db, current_user.id)
        
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

@events_router.get("/{event_id}/attendees", response_model=List[EventInvitationResponse])
async def get_event_attendees(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get attendee invitations for an event"""
    try:
        event_service = EventService(db)
        invitations = event_service.get_event_attendees(event_id, current_user.id)
        return invitations
    except NotFoundError:
        raise http_404_not_found("Event not found")
    except AuthorizationError:
        raise http_403_forbidden("Access denied to this event")
    except Exception:
        raise http_400_bad_request("Failed to retrieve attendees")

@events_router.get("/{event_id}/collaborators", response_model=List[UserSummary])
async def get_event_collaborators(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get collaborators for an event"""
    try:
        event_service = EventService(db)
        collaborators = event_service.get_event_collaborators(event_id, current_user.id)
        return [UserSummary.model_validate(collaborator) for collaborator in collaborators]
    except NotFoundError:
        raise http_404_not_found("Event not found")
    except AuthorizationError:
        raise http_403_forbidden("Access denied to this event")
    except Exception:
        raise http_400_bad_request("Failed to retrieve collaborators")

@events_router.post("/{event_id}/collaborators", response_model=List[UserSummary])
async def add_event_collaborators(
    event_id: int,
    collaborator_data: CollaboratorAddRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Add collaborators to an event"""
    try:
        event_service = EventService(db)
        collaborators = event_service.add_event_collaborators(
            event_id=event_id,
            user_id=current_user.id,
            collaborator_ids=collaborator_data.user_ids,
            send_notifications=collaborator_data.send_notifications
        )
        return [UserSummary.model_validate(collaborator) for collaborator in collaborators]
    except ValidationError as exc:
        raise http_400_bad_request(exc.message)
    except NotFoundError as exc:
        raise http_404_not_found(str(exc))
    except AuthorizationError:
        raise http_403_forbidden("Permission denied to manage collaborators")
    except Exception:
        raise http_400_bad_request("Failed to add collaborators")

# Task management endpoints
@events_router.get("/{event_id}/tasks", response_model=TaskCategoriesResponse)
async def get_event_tasks(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all tasks for an event, grouped by categories.
    Tasks are created as part of event creation in task_categories.
    
    Returns tasks organized by categories like:
    - Food & Catering
    - Decorations
    - Entertainment
    - Logistics
    - etc.
    """
    try:
        event_service = EventService(db)
        tasks = event_service.get_event_tasks(event_id, current_user.id)
        
        # Group tasks by category
        from collections import defaultdict
        categories_dict = defaultdict(list)
        
        for task in tasks:
            category_name = task.category or "Uncategorized"
            categories_dict[category_name].append(TaskCategoryItem(
                id=task.id,
                title=task.title,
                description=task.description,
                completed=(task.status == TaskStatus.COMPLETED),
                assignee_id=task.assigned_to_id
            ))
        
        # Convert to list of TaskCategory objects
        task_categories = [
            TaskCategory(name=name, items=items)
            for name, items in sorted(categories_dict.items(), key=lambda entry: entry[0].lower())
        ]
        
        return TaskCategoriesResponse(task_categories=task_categories)
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
    """
    Update a task (title, description, status, assignee, etc.)
    
    Use this to:
    - Mark tasks as completed/pending
    - Assign tasks to users
    - Update task details
    - Change category or priority
    """
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

@events_router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get details of a single task by ID.
    
    Returns full task information including:
    - Title, description, category
    - Status (pending/completed)
    - Assignee information
    - Due date and priority
    - Cost estimates
    """
    try:
        event_service = EventService(db)
        task = event_service.get_task_by_id(task_id, current_user.id)
        return task
    except NotFoundError:
        raise http_404_not_found("Task not found")
    except AuthorizationError:
        raise http_403_forbidden("Access denied to this task")
    except Exception:
        raise http_400_bad_request("Failed to retrieve task")

@events_router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a task"""
    try:
        event_service = EventService(db)
        event_service.delete_task(task_id, current_user.id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except NotFoundError:
        raise http_404_not_found("Task not found")
    except AuthorizationError:
        raise http_403_forbidden("Permission denied to delete this task")
    except Exception:
        raise http_400_bad_request("Failed to delete task")

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

@events_router.get("/expenses/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    expense_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a single expense"""
    try:
        event_service = EventService(db)
        expense = event_service.get_expense_by_id(expense_id, current_user.id)
        return expense
    except NotFoundError:
        raise http_404_not_found("Expense not found")
    except AuthorizationError:
        raise http_403_forbidden("Access denied to this expense")
    except Exception:
        raise http_400_bad_request("Failed to retrieve expense")

@events_router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete an expense"""
    try:
        event_service = EventService(db)
        event_service.delete_expense(expense_id, current_user.id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except NotFoundError:
        raise http_404_not_found("Expense not found")
    except AuthorizationError:
        raise http_403_forbidden("Permission denied to delete this expense")
    except Exception:
        raise http_400_bad_request("Failed to delete expense")

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

@events_router.get("/comments/{comment_id}", response_model=CommentResponse)
async def get_comment(
    comment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a single comment"""
    try:
        event_service = EventService(db)
        comment = event_service.get_comment_by_id(comment_id, current_user.id)
        return comment
    except NotFoundError:
        raise http_404_not_found("Comment not found")
    except AuthorizationError:
        raise http_403_forbidden("Access denied to this comment")
    except Exception:
        raise http_400_bad_request("Failed to retrieve comment")

@events_router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a comment"""
    try:
        event_service = EventService(db)
        event_service.delete_comment(comment_id, current_user.id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except NotFoundError:
        raise http_404_not_found("Comment not found")
    except AuthorizationError:
        raise http_403_forbidden("Permission denied to delete this comment")
    except Exception:
        raise http_400_bad_request("Failed to delete comment")

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

@events_router.get("/polls/{poll_id}", response_model=PollResponse)
async def get_poll(
    poll_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get poll details"""
    try:
        event_service = EventService(db)
        poll = event_service.get_poll(poll_id, current_user.id)
        return poll
    except NotFoundError:
        raise http_404_not_found("Poll not found")
    except AuthorizationError:
        raise http_403_forbidden("Access denied to this poll")
    except Exception:
        raise http_400_bad_request("Failed to retrieve poll")

@events_router.delete("/polls/{poll_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_poll(
    poll_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a poll"""
    try:
        event_service = EventService(db)
        event_service.delete_poll(poll_id, current_user.id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except NotFoundError:
        raise http_404_not_found("Poll not found")
    except AuthorizationError:
        raise http_403_forbidden("Permission denied to delete this poll")
    except Exception:
        raise http_400_bad_request("Failed to delete poll")

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