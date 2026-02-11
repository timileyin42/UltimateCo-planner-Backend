from typing import Optional, List, Dict, Any, Union
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
from app.models.event_models import (
    Event, EventInvitation, Task, Expense, ExpenseSplit, Comment, Poll, PollOption, PollVote
)
from app.models.user_models import User
from app.models.shared_models import EventStatus, RSVPStatus, TaskStatus, TaskPriority
from app.schemas.event import (
    EventCreate, EventUpdate, EventInvitationCreate, EventInvitationUpdate,
    TaskCreate, TaskUpdate, TaskUpdateById, TaskCategory, ExpenseCreate, ExpenseUpdate, CommentCreate,
    PollCreate, PollVoteCreate
)
from app.schemas.location import Coordinates
from app.core.errors import NotFoundError, ValidationError, ConflictError, AuthorizationError
from app.services.user_service import UserService
from app.services.email_service import email_service
from app.services.google_maps_service import google_maps_service
from app.services.calendar_service import CalendarServiceFactory, CalendarProvider, SyncStatus
from app.models.calendar_models import CalendarConnection, CalendarEvent
from app.repositories.event_repo import EventRepository
from app.repositories.user_repo import UserRepository
from app.repositories.calendar_repo import CalendarConnectionRepository
import asyncio
from app.core.logger import get_logger

logger = get_logger(__name__)

class EventService:
    """Service for event-related business logic"""
    
    def __init__(self, db: Session):
        self.db = db
        self.user_service = UserService(db)
        self.event_repo = EventRepository(db)
        self.user_repo = UserRepository(db)
        self.calendar_repo = CalendarConnectionRepository(db)
    
    # Event CRUD operations
    def get_event_by_id(self, event_id: int, user_id: Optional[int] = None) -> Optional[Event]:
        """Get event by ID with access control"""
        # Query event from repository
        event = self.event_repo.get_by_id(event_id)
        
        if not event:
            return None
        
        # Check access permissions
        if user_id and not self._can_access_event(event, user_id):
            raise AuthorizationError("Access denied to this event")
        
        return event
    
    async def create_event(self, event_data: EventCreate, creator_id: int) -> Event:
        """Create a new event with location optimization"""
        # Validate creator exists
        creator = self.user_service.get_user_by_id(creator_id)
        if not creator:
            raise NotFoundError("Creator not found")
        
        # Validate event dates
        if event_data.end_datetime and event_data.end_datetime <= event_data.start_datetime:
            raise ValidationError("End date must be after start date")
        
        # Prepare event data
        task_categories_input = event_data.task_categories
        event_dict = event_data.model_dump(exclude={"task_categories", "event_type_custom"})
        
        # Handle location optimization if requested
        if event_data.location_input and event_data.auto_optimize_location:
            try:
                # Optimize location using Google Maps
                optimization_result = await google_maps_service.optimize_location_input(
                    user_input=event_data.location_input,
                    user_coordinates=None,
                    include_nearby=False,
                    max_suggestions=1
                )
                
                if optimization_result.optimized and optimization_result.validation.is_valid:
                    # Update event data with optimized location
                    event_dict['venue_address'] = optimization_result.validation.formatted_address
                    if optimization_result.validation.coordinates:
                        event_dict['latitude'] = optimization_result.validation.coordinates.latitude
                        event_dict['longitude'] = optimization_result.validation.coordinates.longitude
                    
                    # Extract venue name from the first autocomplete suggestion if available
                    # This handles cases where user provides just an address or "Venue - Address"
                    if not event_dict.get('venue_name') and optimization_result.autocomplete_suggestions:
                        first_suggestion = optimization_result.autocomplete_suggestions[0]
                        event_dict['venue_name'] = first_suggestion.name
                    
                    # Store additional location metadata (if Event model supports it)
                    # This would require updating the Event model to include these fields
                    # event_dict['place_id'] = optimization_result.validation.place_id
                    # event_dict['formatted_address'] = optimization_result.validation.formatted_address
                    # event_dict['location_verified'] = True
                    # event_dict['location_verification_timestamp'] = datetime.utcnow()
                
            except Exception as e:
                # Log the error but don't fail event creation
                print(f"Location optimization failed: {str(e)}")
                # Fall back to using the raw location input
                if event_data.location_input:
                    event_dict['venue_address'] = event_data.location_input
        
        # Remove location optimization fields from event data
        event_dict.pop('location_input', None)
        event_dict.pop('auto_optimize_location', None)
        
        # Add creator_id and status
        event_dict['creator_id'] = creator_id
        if 'status' not in event_dict:
            event_dict['status'] = EventStatus.CONFIRMED
        
        # Create event using repository
        event = self.event_repo.create(event_dict)
        
        # Automatically add creator as collaborator
        event.collaborators.append(creator)
        self.db.commit()
        
        # Seed tasks based on provided categories or defaults
        if task_categories_input is not None:
            self._create_tasks_from_category_payload(event, task_categories_input, creator_id)
        else:
            self._generate_default_task_categories(event)
        
        # Sync with connected calendars
        asyncio.create_task(self._sync_event_to_calendars(event, 'create'))
        
        return event
    
    async def update_event(self, event_id: int, event_data: EventUpdate, user_id: int) -> Event:
        """Update event information"""
        event = self.get_event_by_id(event_id, user_id)
        if not event:
            raise NotFoundError("Event not found")
        
        # Check if user can edit event
        if not self._can_edit_event(event, user_id):
            raise AuthorizationError("Permission denied to edit this event")
        
        # Validate dates if being updated
        update_data = event_data.model_dump(exclude_unset=True, exclude={"event_type_custom"})
        if event_data.event_type_custom:
            update_data["event_type"] = event_data.event_type_custom.strip()
        if 'end_datetime' in update_data and 'start_datetime' in update_data:
            if update_data['end_datetime'] and update_data['end_datetime'] <= update_data['start_datetime']:
                raise ValidationError("End date must be after start date")
        
        # Handle location optimization if requested
        if event_data.location_input and event_data.auto_optimize_location:
            try:
                # Optimize location using Google Maps
                optimization_result = await google_maps_service.optimize_location_input(
                    user_input=event_data.location_input,
                    user_coordinates=None,
                    include_nearby=False,
                    max_suggestions=1
                )
                
                if optimization_result.optimized and optimization_result.validation.is_valid:
                    # Update event data with optimized location
                    update_data['venue_address'] = optimization_result.validation.formatted_address
                    if optimization_result.validation.coordinates:
                        update_data['latitude'] = optimization_result.validation.coordinates.latitude
                        update_data['longitude'] = optimization_result.validation.coordinates.longitude
                
                    # Extract venue name from the first autocomplete suggestion if available
                    if not update_data.get('venue_name') and optimization_result.autocomplete_suggestions:
                        first_suggestion = optimization_result.autocomplete_suggestions[0]
                        update_data['venue_name'] = first_suggestion.name
            
            except Exception as e:
                # Log the error but don't fail event update
                print(f"Location optimization failed during update: {str(e)}")
                # Fall back to using the raw location input if provided and venue_address not set
                if event_data.location_input and 'venue_address' not in update_data:
                    update_data['venue_address'] = event_data.location_input

        # Remove helper fields from update_data
        update_data.pop('location_input', None)
        update_data.pop('user_coordinates', None)
        update_data.pop('auto_optimize_location', None)
        
        # Extract task categories if present
        task_categories_input = update_data.pop('task_categories', None)
        
        # Update event using repository
        updated_event = self.event_repo.update(event_id, update_data)
        
        # Sync task categories if provided
        if task_categories_input is not None:
            self.sync_tasks_from_category_payload(updated_event, task_categories_input, user_id)
        
        # Pre-load tasks and other relationships to avoid lazy loading issues
        # during response serialization if the session gets closed or busy
        try:
            _ = updated_event.tasks
            _ = updated_event.attendee_count
            _ = updated_event.total_expenses
        except Exception as e:
            print(f"Error pre-loading event relationships: {e}")
            # Continue anyway, let response serialization fail if it must
        
        # Sync with connected calendars
        asyncio.create_task(self._sync_event_to_calendars(updated_event, 'update'))
        
        return updated_event
    
    def delete_event(self, event_id: int, user_id: int) -> bool:
        """Delete event (soft delete)"""
        event = self.get_event_by_id(event_id, user_id)
        if not event:
            raise NotFoundError("Event not found")
        
        # Only creator can delete event
        if event.creator_id != user_id:
            raise AuthorizationError("Only event creator can delete the event")
        
        # Delete using repository
        success = self.event_repo.delete(event_id)
        
        if success:
            # Sync deletion with connected calendars
            asyncio.create_task(self._sync_event_to_calendars(event, 'delete'))
        
        return success
    
    def duplicate_event(self, event_id: int, user_id: int, new_title: Optional[str] = None) -> Event:
        """Duplicate an existing event"""
        original_event = self.get_event_by_id(event_id, user_id)
        if not original_event:
            raise NotFoundError("Event not found")
        
        # Check if user can access the original event
        if not self._can_access_event(original_event, user_id):
            raise AuthorizationError("Permission denied to access this event")
        
        # Create new event with copied data
        duplicate_title = new_title or f"Copy of {original_event.title}"
        
        # Create event data for duplication
        event_data = {
            'title': duplicate_title,
            'description': original_event.description,
            'event_type': original_event.event_type,
            'start_datetime': original_event.start_datetime,
            'end_datetime': original_event.end_datetime,
            'venue_name': original_event.venue_name,
            'venue_address': original_event.venue_address,
            'latitude': original_event.latitude,
            'longitude': original_event.longitude,
            'max_attendees': original_event.max_attendees,
            'is_public': original_event.is_public,
            'creator_id': user_id,
            'status': EventStatus.DRAFT
        }
        
        # Create the duplicate event
        duplicate_event = Event(**event_data)
        self.db.add(duplicate_event)
        self.db.commit()
        self.db.refresh(duplicate_event)
        
        # Add creator as collaborator
        creator = self.user_repo.get_by_id(user_id)
        if creator:
            duplicate_event.collaborators.append(creator)
        
        # Copy tasks from original event
        original_tasks = self.event_repo.get_event_tasks(event_id)
        
        for task in original_tasks:
            new_task = Task(
                event_id=duplicate_event.id,
                title=task.title,
                description=task.description,
                due_date=task.due_date,
                priority=task.priority,
                assigned_to_id=None,  # Don't copy assignments
                creator_id=user_id,
                status=task.status or TaskStatus.TODO
            )
            self.db.add(new_task)
        
        self.db.commit()
        self.db.refresh(duplicate_event)
        
        return duplicate_event
    
    def get_user_events(
        self, 
        user_id: int, 
        status: Optional[EventStatus] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[Event]:
        """Get events for a user (created or invited to)"""
        from app.schemas.pagination import PaginationParams
        
        pagination = PaginationParams(offset=skip, limit=limit)
        filters = {'status': status} if status else None
        
        events, _ = self.event_repo.get_user_events(
            user_id=user_id,
            pagination=pagination,
            filters=filters
        )
        
        return events
    
    def search_events(
        self, 
        query: str, 
        user_id: Optional[int] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[Event]:
        """Search public events or user's events"""
        from app.schemas.pagination import PaginationParams
        
        pagination = PaginationParams(offset=skip, limit=limit)
        
        events, _ = self.event_repo.search(
            search_term=query,
            pagination=pagination,
            user_id=user_id
        )
        
        return events
    
    # Event invitation methods
    def rsvp_to_event(self, event_id: int, user_id: int, rsvp_data: EventInvitationUpdate) -> EventInvitation:
        """RSVP to an event (create or update invitation)"""
        event = self.get_event_by_id(event_id)
        if not event:
            raise NotFoundError("Event not found")
            
        # Check if user is already invited/participating
        invitation = self.event_repo.get_invitation_by_event_and_user(event_id, user_id)
        
        if invitation:
            # Update existing invitation
            invitation.rsvp_status = rsvp_data.rsvp_status
            invitation.response_message = rsvp_data.response_message
            invitation.plus_one_name = rsvp_data.plus_one_name
            invitation.dietary_restrictions = rsvp_data.dietary_restrictions
            invitation.special_requests = rsvp_data.special_requests
            invitation.responded_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(invitation)
        else:
            # Check if event is public or allows self-invites
            # For now, we'll allow RSVP if the event is public OR if we treat this as a "self-invite" mechanism
            # The user mentioned "bulk phone invite", implying they have a link. 
            # If they have a link, they should be able to RSVP.
            
            # Create new invitation with RSVP status
            invitation = EventInvitation(
                event_id=event_id,
                user_id=user_id,
                rsvp_status=rsvp_data.rsvp_status,
                response_message=rsvp_data.response_message,
                plus_one_name=rsvp_data.plus_one_name,
                dietary_restrictions=rsvp_data.dietary_restrictions,
                special_requests=rsvp_data.special_requests,
                responded_at=datetime.utcnow(),
                invited_at=datetime.utcnow() # Self-invited now
            )
            self.db.add(invitation)
            self.db.commit()
            self.db.refresh(invitation)
            
        return invitation

    def invite_users(self, event_id: int, invitation_data: EventInvitationCreate, inviter_id: int) -> List[EventInvitation]:
        """Invite users to an event"""
        event = self.get_event_by_id(event_id, inviter_id)
        if not event:
            raise NotFoundError("Event not found")
        
        # Check if user can invite
        if not self._can_invite_to_event(event, inviter_id):
            raise AuthorizationError("Permission denied to invite users")
        
        invitations = []
        for user_id in invitation_data.user_ids:
            # Check if user exists
            user = self.user_service.get_user_by_id(user_id)
            if not user:
                continue
            
            # Check if already invited
            existing_invitation = self.event_repo.get_invitation_by_event_and_user(event_id, user_id)
            
            if existing_invitation:
                continue
            
            # Create invitation
            invitation = EventInvitation(
                event_id=event_id,
                user_id=user_id,
                invitation_message=invitation_data.invitation_message,
                plus_one_allowed=invitation_data.plus_one_allowed,
                invited_at=datetime.utcnow()
            )
            
            self.db.add(invitation)
            invitations.append(invitation)
            
            # Send invitation email asynchronously
            try:
                inviter = self.user_service.get_user_by_id(inviter_id)
                asyncio.create_task(
                    email_service.send_event_invitation(event, invitation, user, inviter)
                )
            except Exception as e:
                print(f"Failed to send invitation email to {user.email}: {str(e)}")
        
        self.db.commit()
        return invitations
    
    def respond_to_invitation(self, invitation_id: int, response_data: EventInvitationUpdate, user_id: int) -> EventInvitation:
        """Respond to event invitation"""
        invitation = self.event_repo.get_invitation_by_id(invitation_id)
        
        if not invitation or invitation.user_id != user_id:
            raise NotFoundError("Invitation not found")
        
        # Update invitation
        invitation.rsvp_status = response_data.rsvp_status
        invitation.response_message = response_data.response_message
        invitation.plus_one_name = response_data.plus_one_name
        invitation.dietary_restrictions = response_data.dietary_restrictions
        invitation.special_requests = response_data.special_requests
        invitation.responded_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(invitation)
        
        # Send RSVP confirmation email asynchronously
        try:
            user = self.user_service.get_user_by_id(user_id)
            asyncio.create_task(
                email_service.send_rsvp_confirmation(invitation.event, invitation, user)
            )
        except Exception as e:
            print(f"Failed to send RSVP confirmation email: {str(e)}")
        
        return invitation
    
    def get_event_invitations(self, event_id: int, user_id: int) -> List[EventInvitation]:
        """Get all invitations for an event"""
        event = self.get_event_by_id(event_id, user_id)
        if not event:
            raise NotFoundError("Event not found")
        
        if not self._can_view_invitations(event, user_id):
            raise AuthorizationError("Permission denied to view invitations")
        
        return event.invitations

    def get_event_attendees(self, event_id: int, user_id: int) -> List[EventInvitation]:
        """Get attendee invitations for an event"""
        event = self.get_event_by_id(event_id, user_id)
        if not event:
            raise NotFoundError("Event not found")

        invitations = self.event_repo.get_event_invitations(event_id, include_relations=True)

        return invitations

    def get_accepted_event_attendees(self, event_id: int, user_id: int) -> List[EventInvitation]:
        """Get accepted attendee invitations for an event"""
        event = self.get_event_by_id(event_id, user_id)
        if not event:
            raise NotFoundError("Event not found")

        invitations = self.event_repo.get_event_invitations(event_id, include_relations=True)
        return [inv for inv in invitations if inv.rsvp_status == RSVPStatus.ACCEPTED]

    def get_event_collaborators(self, event_id: int, user_id: int) -> List[User]:
        """List event collaborators"""
        event = self.get_event_by_id(event_id, user_id)
        if not event:
            raise NotFoundError("Event not found")

        return list(event.collaborators)

    def add_event_collaborators(
        self,
        event_id: int,
        user_id: int,
        collaborator_ids: List[int],
        send_notifications: bool = False
    ) -> List[User]:
        """Add collaborators to an event"""
        if not collaborator_ids:
            raise ValidationError("No collaborator IDs provided")

        event = self.get_event_by_id(event_id, user_id)
        if not event:
            raise NotFoundError("Event not found")

        if not self._can_edit_event(event, user_id):
            raise AuthorizationError("Permission denied to manage collaborators")

        unique_ids = list({collab_id for collab_id in collaborator_ids if collab_id})
        existing_ids = {collaborator.id for collaborator in event.collaborators}

        ids_to_add = [collab_id for collab_id in unique_ids if collab_id not in existing_ids]
        if not ids_to_add:
            return list(event.collaborators)

        users = self.user_repo.get_by_ids(ids_to_add)
        found_ids = {user.id for user in users}
        missing_ids = set(ids_to_add) - found_ids
        if missing_ids:
            missing_str = ", ".join(str(identifier) for identifier in sorted(missing_ids))
            raise NotFoundError(f"Users not found: {missing_str}")

        for collaborator in users:
            if collaborator not in event.collaborators:
                event.collaborators.append(collaborator)

        self.db.commit()
        self.db.refresh(event)

        # Placeholder for future notification handling
        _ = send_notifications

        return list(event.collaborators)
    
    # Task management methods
    def create_task(self, event_id: int, task_data: TaskCreate, creator_id: int) -> Task:
        """Create a new task for an event"""
        event = self.get_event_by_id(event_id, creator_id)
        if not event:
            raise NotFoundError("Event not found")
        
        if not self._can_edit_event(event, creator_id):
            raise AuthorizationError("Permission denied to create tasks")
        
        # Validate assignee if provided
        if task_data.assignee_id:
            assignee = self.user_service.get_user_by_id(task_data.assignee_id)
            if not assignee:
                raise NotFoundError("Assignee not found")
        
        task_payload = task_data.model_dump(exclude_unset=True)
        assignee_id = task_payload.pop("assignee_id", None)

        # Remove optional fields explicitly set to None so SQLAlchemy ignores them
        task_payload = {key: value for key, value in task_payload.items() if value is not None}

        task = Task(
            **task_payload,
            assigned_to_id=assignee_id,
            event_id=event_id,
            creator_id=creator_id
        )
        
        try:
            self.db.add(task)
            self.db.commit()
            self.db.refresh(task)
        except Exception as exc:
            self.db.rollback()
            logger.exception("Failed to create task", exc_info=exc)
            raise

        return task
    
    def update_task(self, task_id: int, task_data: Union[TaskUpdate, TaskUpdateById], user_id: int) -> Task:
        """Update a task"""
        task = self.event_repo.get_task_by_id(task_id)
        if not task:
            raise NotFoundError("Task not found")
        
        # Check permissions
        if not self._can_edit_task(task, user_id):
            raise AuthorizationError("Permission denied to edit this task")
        
        # Update task fields
        update_data = task_data.model_dump(exclude_unset=True)

        if "assignee_id" in update_data:
            new_assignee_id = update_data.pop("assignee_id")
            if new_assignee_id:
                assignee = self.user_service.get_user_by_id(new_assignee_id)
                if not assignee:
                    raise NotFoundError("Assignee not found")
            task.assigned_to_id = new_assignee_id

        for field, value in update_data.items():
            if hasattr(task, field):
                setattr(task, field, value)
        
        # Set completion time if status changed to completed
        if task_data.status == TaskStatus.COMPLETED and task.status != TaskStatus.COMPLETED:
            task.completed_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(task)
        return task
    
    def get_event_tasks(self, event_id: int, user_id: int) -> List[Task]:
        """Get all tasks for an event"""
        event = self.get_event_by_id(event_id, user_id)
        if not event:
            raise NotFoundError("Event not found")
        
        return event.tasks

    def get_task_by_id(self, task_id: int, user_id: int) -> Task:
        """Get a single task by ID"""
        task = self.event_repo.get_task_by_id(task_id, include_relations=True)

        if not task:
            raise NotFoundError("Task not found")

        if not self._can_access_event(task.event, user_id):
            raise AuthorizationError("Access denied to this task")

        return task

    def delete_task(self, task_id: int, user_id: int) -> bool:
        """Delete (soft delete) a task"""
        task = self.get_task_by_id(task_id, user_id)

        if not self._can_edit_task(task, user_id):
            raise AuthorizationError("Permission denied to delete this task")

        task.soft_delete()
        self.db.commit()
        return True
    
    # Expense management methods
    def create_expense(self, event_id: int, expense_data: ExpenseCreate, user_id: int) -> Expense:
        """Create a new expense for an event"""
        event = self.get_event_by_id(event_id, user_id)
        if not event:
            raise NotFoundError("Event not found")
        
        if not self._can_edit_event(event, user_id):
            raise AuthorizationError("Permission denied to add expenses")
        
        expense = Expense(
            **expense_data.model_dump(exclude={'split_with_user_ids'}),
            event_id=event_id,
            paid_by_user_id=user_id
        )
        
        self.db.add(expense)
        self.db.commit()
        self.db.refresh(expense)
        
        # Create expense splits if shared
        if expense_data.is_shared and expense_data.split_with_user_ids:
            self._create_expense_splits(expense, expense_data.split_with_user_ids)
        
        return expense
    
    def _create_expense_splits(self, expense: Expense, user_ids: List[int]):
        """Create expense splits for shared expenses"""
        if expense.split_equally:
            amount_per_person = expense.amount / len(user_ids)
        else:
            # For now, split equally. In future, allow custom amounts
            amount_per_person = expense.amount / len(user_ids)
        
        for user_id in user_ids:
            split = ExpenseSplit(
                expense_id=expense.id,
                user_id=user_id,
                amount_owed=amount_per_person
            )
            self.db.add(split)
        
        self.db.commit()
    
    def get_event_expenses(self, event_id: int, user_id: int) -> List[Expense]:
        """Get all expenses for an event"""
        event = self.get_event_by_id(event_id, user_id)
        if not event:
            raise NotFoundError("Event not found")
        
        return self.event_repo.get_event_expenses(event_id, include_relations=True)

    def get_expense_by_id(self, expense_id: int, user_id: int) -> Expense:
        """Get a single expense by ID"""
        expense = self.event_repo.get_expense_by_id(expense_id, include_relations=True)

        if not expense:
            raise NotFoundError("Expense not found")

        if not self._can_access_event(expense.event, user_id):
            raise AuthorizationError("Access denied to this expense")

        return expense

    def delete_expense(self, expense_id: int, user_id: int) -> bool:
        """Delete (soft delete) an expense"""
        expense = self.get_expense_by_id(expense_id, user_id)

        if not self._can_edit_event(expense.event, user_id):
            raise AuthorizationError("Permission denied to delete this expense")

        expense.soft_delete()
        self.db.commit()
        return True
    
    # Comment methods
    def create_comment(self, event_id: int, comment_data: CommentCreate, author_id: int) -> Comment:
        """Create a comment on an event"""
        event = self.get_event_by_id(event_id, author_id)
        if not event:
            raise NotFoundError("Event not found")
        
        comment = Comment(
            **comment_data.model_dump(),
            event_id=event_id,
            author_id=author_id
        )
        
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        return comment
    
    def get_event_comments(self, event_id: int, user_id: int) -> List[Comment]:
        """Get all top-level comments for an event"""
        event = self.get_event_by_id(event_id, user_id)
        if not event:
            raise NotFoundError("Event not found")

        return self.event_repo.get_event_comments(event_id, include_relations=True)

    def get_comment_by_id(self, comment_id: int, user_id: int) -> Comment:
        """Get a single comment by ID"""
        comment = self.event_repo.get_comment_by_id(comment_id, include_relations=True)

        if not comment:
            raise NotFoundError("Comment not found")

        if not self._can_access_event(comment.event, user_id):
            raise AuthorizationError("Access denied to this comment")

        return comment

    def delete_comment(self, comment_id: int, user_id: int) -> bool:
        """Delete (soft delete) a comment"""
        comment = self.get_comment_by_id(comment_id, user_id)

        can_delete = (
            comment.author_id == user_id or
            self._can_edit_event(comment.event, user_id)
        )

        if not can_delete:
            raise AuthorizationError("Permission denied to delete this comment")

        comment.soft_delete()

        # Soft delete any nested replies while guarding against None values or
        # already-deleted entries so we do not trigger unexpected errors during
        # traversal.
        stack = [reply for reply in (comment.replies or []) if reply and not reply.is_deleted]
        while stack:
            reply = stack.pop()
            if not reply or reply.is_deleted:
                continue

            reply.soft_delete()

            children = getattr(reply, "replies", None) or []
            stack.extend(child for child in children if child and not child.is_deleted)

        self.db.commit()
        return True
    
    # Poll methods
    def create_poll(self, event_id: int, poll_data: PollCreate, creator_id: int) -> Poll:
        """Create a poll for an event"""
        event = self.get_event_by_id(event_id, creator_id)
        if not event:
            raise NotFoundError("Event not found")
        
        if not self._can_edit_event(event, creator_id):
            raise AuthorizationError("Permission denied to create polls")
        
        poll = Poll(
            **poll_data.model_dump(exclude={'options'}),
            event_id=event_id,
            creator_id=creator_id
        )
        
        self.db.add(poll)
        self.db.commit()
        self.db.refresh(poll)
        
        # Create poll options
        for i, option_data in enumerate(poll_data.options):
            option = PollOption(
                poll_id=poll.id,
                text=option_data.text,
                order_index=i
            )
            self.db.add(option)
        
        self.db.commit()
        return poll
    
    def vote_on_poll(self, poll_id: int, vote_data: PollVoteCreate, user_id: int) -> List[PollVote]:
        """Vote on a poll"""
        poll = self.event_repo.get_poll_by_id(poll_id, include_relations=True)
        if not poll:
            raise NotFoundError("Poll not found")
        
        # Check if user has access to the event
        if not self._can_access_event(poll.event, user_id):
            raise AuthorizationError("Access denied to this poll")
        
        # Check if poll is still open
        if poll.closes_at and poll.closes_at < datetime.utcnow():
            raise ValidationError("Poll is closed")
        
        # Remove existing votes if not multiple choice
        if not poll.multiple_choice:
            self.event_repo.delete_poll_votes(poll_id, user_id)
        
        # Create new votes
        votes = []
        for option_id in vote_data.option_ids:
            # Validate option belongs to poll
            option = self.event_repo.get_poll_option_by_id(option_id)
            
            if not option:
                continue
            
            vote = PollVote(
                poll_id=poll_id,
                option_id=option_id,
                user_id=user_id
            )
            
            self.db.add(vote)
            votes.append(vote)
        
        self.db.commit()
        return votes

    def get_poll(self, poll_id: int, user_id: int) -> Poll:
        """Get poll details"""
        poll = self.event_repo.get_poll_by_id(poll_id, include_relations=True)

        if not poll:
            raise NotFoundError("Poll not found")

        if not self._can_access_event(poll.event, user_id):
            raise AuthorizationError("Access denied to this poll")

        return poll

    def delete_poll(self, poll_id: int, user_id: int) -> bool:
        """Delete a poll"""
        poll = self.get_poll(poll_id, user_id)

        if not self._can_edit_event(poll.event, user_id):
            raise AuthorizationError("Permission denied to delete this poll")

        poll.soft_delete()
        self.db.commit()
        return True
    
    # Permission helper methods
    def _can_access_event(self, event: Event, user_id: int) -> bool:
        """Check if user can access event"""
        if event.is_public:
            return True
        
        # Check if user is creator, collaborator, or invited
        if event.creator_id == user_id:
            return True
        
        if any(collab.id == user_id for collab in event.collaborators):
            return True
        
        if any(inv.user_id == user_id for inv in event.invitations):
            return True
        
        return False
    
    def _can_edit_event(self, event: Event, user_id: int) -> bool:
        """Check if user can edit event"""
        return (event.creator_id == user_id or 
                any(collab.id == user_id for collab in event.collaborators))
    
    def _can_invite_to_event(self, event: Event, user_id: int) -> bool:
        """Check if user can invite others to event"""
        if not event.allow_guest_invites:
            return self._can_edit_event(event, user_id)
        
        return self._can_access_event(event, user_id)
    
    def _can_view_invitations(self, event: Event, user_id: int) -> bool:
        """Check if user can view event invitations"""
        return self._can_edit_event(event, user_id)
    
    def _can_edit_task(self, task: Task, user_id: int) -> bool:
        """Check if user can edit task"""
        return (task.creator_id == user_id or 
                task.assignee_id == user_id or
                self._can_edit_event(task.event, user_id))
    
    def get_event_stats(self, event_id: int, user_id: int) -> Dict[str, Any]:
        """Get comprehensive event statistics"""
        event = self.get_event_by_id(event_id, user_id)
        if not event:
            raise NotFoundError("Event not found")
        
        # Count attendees by RSVP status
        rsvp_counts = {}
        for status in RSVPStatus:
            rsvp_counts[status.value] = len([
                inv for inv in event.invitations 
                if inv.rsvp_status == status
            ])
        
        # Count tasks by status
        task_counts = {}
        for status in TaskStatus:
            task_counts[status.value] = len([
                task for task in event.tasks 
                if task.status == status
            ])
        
        # Calculate aggregate attendee stats
        total_attendees = sum(rsvp_counts.values())
        confirmed_attendees = rsvp_counts.get(RSVPStatus.ACCEPTED.value, 0)
        pending_responses = rsvp_counts.get(RSVPStatus.PENDING.value, 0)

        # Calculate budget info
        total_expenses = sum(exp.amount for exp in event.expenses)
        budget_remaining = (event.total_budget - total_expenses) if event.total_budget else None
        
        return {
            "total_attendees": total_attendees,
            "confirmed_attendees": confirmed_attendees,
            "pending_responses": pending_responses,
            "rsvp_counts": rsvp_counts,
            "task_counts": task_counts,
            "total_expenses": total_expenses,
            "budget_remaining": budget_remaining,
            "total_invitations": len(event.invitations),
            "total_tasks": len(event.tasks),
            "total_comments": len(event.comments),
            "total_polls": len(event.polls)
        }
    
    # Calendar sync methods
    async def _sync_event_to_calendars(self, event: Event, operation: str) -> None:
        """Sync event to all connected calendars for the user"""
        try:
            # Get user's calendar connections
            connections = self.calendar_repo.get_by_user_id(
                user_id=event.creator_id,
                active_only=True
            )
            
            for connection in connections:
                try:
                    await self._sync_event_to_calendar(event, connection, operation)
                except Exception as e:
                    logger.error(f"Failed to sync event {event.id} to calendar {connection.id}: {str(e)}")
                    # Update connection sync status on error
                    connection.sync_error_count += 1
                    connection.sync_error_message = str(e)
                    if connection.sync_error_count >= 5:
                        connection.sync_status = SyncStatus.FAILED
                    self.db.commit()
                    
        except Exception as e:
            logger.error(f"Failed to sync event {event.id} to calendars: {str(e)}")
    
    async def _sync_event_to_calendar(self, event: Event, connection: CalendarConnection, operation: str) -> None:
        """Sync a single event to a specific calendar connection"""
        try:
            # Get calendar service for the provider
            calendar_service = CalendarServiceFactory.get_service(connection.provider)
            
            # Check if calendar event already exists
            calendar_event = self.db.query(CalendarEvent).filter(
                CalendarEvent.user_id == event.creator_id,
                CalendarEvent.calendar_connection_id == connection.id,
                CalendarEvent.external_event_id.isnot(None)
            ).first()
            
            if operation == 'create':
                if not calendar_event:
                    # Create new calendar event
                    external_event = await calendar_service.create_event(
                        calendar_id=connection.calendar_id,
                        event_data={
                            'title': event.title,
                            'description': event.description,
                            'start_time': event.start_datetime,
                            'end_time': event.end_datetime,
                            'location': event.venue_address,
                            'all_day': False,
                            'timezone': 'UTC'
                        },
                        access_token=connection.access_token
                    )
                    
                    # Create calendar event record
                    calendar_event = CalendarEvent(
                        user_id=event.creator_id,
                        calendar_connection_id=connection.id,
                        title=event.title,
                        description=event.description,
                        location=event.venue_address,
                        start_time=event.start_datetime,
                        end_time=event.end_datetime,
                        external_event_id=external_event.get('id'),
                        sync_status=SyncStatus.SYNCED,
                        last_synced_at=datetime.utcnow()
                    )
                    self.db.add(calendar_event)
                    
            elif operation == 'update' and calendar_event:
                # Update existing calendar event
                await calendar_service.update_event(
                    calendar_id=connection.calendar_id,
                    event_id=calendar_event.external_event_id,
                    event_data={
                        'title': event.title,
                        'description': event.description,
                        'start_time': event.start_datetime,
                        'end_time': event.end_datetime,
                        'location': event.venue_address,
                        'all_day': False,
                        'timezone': 'UTC'
                    },
                    access_token=connection.access_token
                )
                
                # Update calendar event record
                calendar_event.title = event.title
                calendar_event.description = event.description
                calendar_event.location = event.venue_address
                calendar_event.start_time = event.start_datetime
                calendar_event.end_time = event.end_datetime
                calendar_event.sync_status = SyncStatus.SYNCED
                calendar_event.last_synced_at = datetime.utcnow()
                
            elif operation == 'delete' and calendar_event:
                # Delete calendar event
                await calendar_service.delete_event(
                    calendar_id=connection.calendar_id,
                    event_id=calendar_event.external_event_id,
                    access_token=connection.access_token
                )
                
                # Remove calendar event record
                self.db.delete(calendar_event)
            
            # Update connection sync status
            connection.sync_status = SyncStatus.SYNCED
            connection.last_sync_at = datetime.utcnow()
            connection.sync_error_count = 0
            connection.sync_error_message = None
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to sync event {event.id} to calendar {connection.id}: {str(e)}")
            raise
    
    def get_calendar_sync_status(self, user_id: int) -> Dict[str, Any]:
        """Get calendar sync status for a user"""
        connections = self.calendar_repo.get_by_user_id(user_id)
        
        sync_status = {
            'total_connections': len(connections),
            'active_connections': len([c for c in connections if c.sync_enabled]),
            'synced_connections': len([c for c in connections if c.sync_status == SyncStatus.SYNCED]),
            'failed_connections': len([c for c in connections if c.sync_status == SyncStatus.FAILED]),
            'connections': []
        }
        
        for connection in connections:
            sync_status['connections'].append({
                'id': connection.id,
                'provider': connection.provider.value,
                'calendar_name': connection.calendar_name,
                'sync_enabled': connection.sync_enabled,
                'sync_status': connection.sync_status.value,
                'last_sync_at': connection.last_sync_at,
                'sync_error_message': connection.sync_error_message
            })
        
        return sync_status
    
    async def manual_sync_calendars(self, user_id: int) -> Dict[str, Any]:
        """Manually trigger calendar sync for all user events"""
        try:
            # Get user's events
            events = self.get_user_events(user_id)
            
            # Get user's calendar connections
            connections = self.calendar_repo.get_by_user_id(
                user_id=user_id,
                active_only=True
            )
            
            sync_results = {
                'total_events': len(events),
                'total_connections': len(connections),
                'synced_events': 0,
                'failed_events': 0,
                'errors': []
            }
            
            for event in events:
                try:
                    await self._sync_event_to_calendars(event, 'update')
                    sync_results['synced_events'] += 1
                except Exception as e:
                    sync_results['failed_events'] += 1
                    sync_results['errors'].append({
                        'event_id': event.id,
                        'event_title': event.title,
                        'error': str(e)
                    })
            
            return sync_results
            
        except Exception as e:
            logger.error(f"Manual calendar sync failed for user {user_id}: {str(e)}")
            raise
    
    def _create_tasks_from_category_payload(
        self,
        event: Event,
        categories: List[TaskCategory],
        creator_id: int
    ) -> None:
        """Create event tasks from provided category payload."""
        if not categories:
            return

        if not self._can_edit_event(event, creator_id):
            raise AuthorizationError("Permission denied to create tasks")

        tasks_created = False

        for category in categories:
            category_name = (category.name or "").strip() or "Uncategorized"

            for item in category.items:
                title = (item.title or "").strip()
                if not title:
                    continue

                assignee_id = item.assignee_id
                if assignee_id:
                    assignee = self.user_service.get_user_by_id(assignee_id)
                    if not assignee:
                        logger.warning(
                            "Skipping task '%s' for event %s: assignee %s not found",
                            title,
                            event.id,
                            assignee_id
                        )
                        assignee_id = None

                task = Task(
                    title=title,
                    description=item.description,
                    category=category_name,
                    event_id=event.id,
                    creator_id=creator_id,
                    assigned_to_id=assignee_id,
                    status=TaskStatus.COMPLETED if item.completed else TaskStatus.TODO
                )

                if item.completed:
                    task.completed_at = datetime.utcnow()

                self.db.add(task)
                tasks_created = True

        if tasks_created:
            self.db.commit()
            self.db.refresh(event)

    def sync_tasks_from_category_payload(
        self,
        event: Event,
        categories: Union[List[TaskCategory], List[Dict[str, Any]]],
        user_id: int
    ) -> None:
        """Sync event tasks from provided category payload during update."""
        if not categories:
            return

        # We need to map existing tasks to update them
        existing_tasks = {task.id: task for task in event.tasks}
        tasks_updated = False
        
        for category in categories:
            if isinstance(category, dict):
                category_name = (category.get("name") or "").strip() or "Uncategorized"
                items = category.get("items") or []
            else:
                category_name = (category.name or "").strip() or "Uncategorized"
                items = category.items
            
            for item in items:
                if isinstance(item, dict):
                    title = (item.get("title") or "").strip()
                    item_id = item.get("id")
                    description = item.get("description")
                    completed = item.get("completed", False)
                    assignee_id = item.get("assignee_id")
                    priority = item.get("priority")
                    due_date = item.get("due_date")
                    estimated_cost = item.get("estimated_cost")
                    actual_cost = item.get("actual_cost")
                else:
                    title = (item.title or "").strip()
                    item_id = item.id
                    description = item.description
                    completed = item.completed
                    assignee_id = item.assignee_id
                    priority = getattr(item, "priority", None)
                    due_date = getattr(item, "due_date", None)
                    estimated_cost = getattr(item, "estimated_cost", None)
                    actual_cost = getattr(item, "actual_cost", None)

                if not title:
                    continue
                
                # Check if task exists (by ID)
                if item_id and item_id in existing_tasks:
                    task = existing_tasks[item_id]
                    # Update task fields
                    task.title = title
                    task.description = description
                    task.category = category_name
                    
                    if priority:
                        task.priority = priority
                    if due_date:
                        task.due_date = due_date
                    if estimated_cost is not None:
                        task.estimated_cost = estimated_cost
                    if actual_cost is not None:
                        task.actual_cost = actual_cost
                    
                    # Update status
                    if completed and task.status != TaskStatus.COMPLETED:
                        task.status = TaskStatus.COMPLETED
                        task.completed_at = datetime.utcnow()
                    elif not completed and task.status == TaskStatus.COMPLETED:
                        task.status = TaskStatus.TODO
                        task.completed_at = None
                        
                    # Update assignee if provided
                    if assignee_id is not None:
                         task.assigned_to_id = assignee_id
                    
                    tasks_updated = True
                    
                else:
                    # Create new task
                    # Validate assignee if provided
                    current_assignee_id = assignee_id
                    if current_assignee_id:
                        assignee = self.user_service.get_user_by_id(current_assignee_id)
                        if not assignee:
                            current_assignee_id = None
                    
                    new_task = Task(
                        title=title,
                        description=description,
                        category=category_name,
                        event_id=event.id,
                        creator_id=user_id,
                        assigned_to_id=current_assignee_id,
                        status=TaskStatus.COMPLETED if completed else TaskStatus.TODO,
                        priority=priority or TaskPriority.MEDIUM,
                        due_date=due_date,
                        estimated_cost=estimated_cost,
                        actual_cost=actual_cost
                    )
                    if completed:
                        new_task.completed_at = datetime.utcnow()
                        
                    self.db.add(new_task)
                    tasks_updated = True
        
        if tasks_updated:
            self.db.commit()
            self.db.refresh(event)

    def _generate_default_task_categories(self, event: Event) -> None:
        """Generate default task category templates based on event type"""
        from app.models.event_models import Task
        from app.models.shared_models import TaskStatus, TaskPriority
        
        # Define default templates by event type
        task_templates = {
            'BIRTHDAY': {
                'Food': [
                    'Confirm brunch menu with cafe',
                    'Order cake (chocolate or strawberry)',
                    'Arrange drinks (mimosas + juice options)',
                ],
                'Guests': [
                    'Send invites to 12 guests',
                    'Track RSVPs',
                    'Confirm seating arrangements with venue',
                ],
                'Logistics': [
                    'Book cafe private room by Wednesday',
                    'Arrange decorations (balloons, banners)',
                    'Confirm photographer or set up photo corner',
                ],
                'Extras': [
                    'Create playlist for background music',
                    'Buy party favors (mini candles or gift bags)',
                    'Prepare a short toast/speech',
                ],
            },
            'WEDDING': {
                'Venue': [
                    'Book ceremony location',
                    'Book reception venue',
                    'Arrange seating plan',
                ],
                'Food': [
                    'Choose catering menu',
                    'Arrange wedding cake',
                    'Plan cocktail hour menu',
                ],
                'Entertainment': [
                    'Book DJ or live band',
                    'Arrange first dance song',
                    'Plan reception timeline',
                ],
                'Decor': [
                    'Choose floral arrangements',
                    'Select table decorations',
                    'Plan ceremony backdrop',
                ],
                'Guests': [
                    'Send save-the-dates',
                    'Send formal invitations',
                    'Track RSVPs',
                ],
                'Logistics': [
                    'Book photographer',
                    'Book videographer',
                    'Arrange transportation',
                ],
            },
            'PARTY': {
                'Food': [
                    'Plan menu',
                    'Order catering or groceries',
                    'Prepare drinks',
                ],
                'Guests': [
                    'Send invitations',
                    'Track RSVPs',
                ],
                'Entertainment': [
                    'Create playlist',
                    'Plan activities or games',
                ],
                'Decor': [
                    'Buy decorations',
                    'Set up venue',
                ],
            },
            'CONFERENCE': {
                'Venue': [
                    'Book conference hall',
                    'Arrange breakout rooms',
                    'Set up registration desk',
                ],
                'Logistics': [
                    'Arrange AV equipment',
                    'Print name badges',
                    'Prepare welcome packs',
                ],
                'Food': [
                    'Arrange coffee breaks',
                    'Book lunch catering',
                ],
                'Guests': [
                    'Send invitations to speakers',
                    'Track attendee registrations',
                ],
            },
            'MEETING': {
                'Logistics': [
                    'Book meeting room',
                    'Prepare agenda',
                    'Set up presentation',
                ],
                'Food': [
                    'Order refreshments',
                ],
            },
        }
        
        # Get templates for this event type, or use generic template
        # Normalize event type to uppercase for matching
        event_type_key = event.event_type.upper() if hasattr(event.event_type, 'upper') else str(event.event_type).upper()
        templates = task_templates.get(event_type_key, {
            'Food': ['Plan food and drinks'],
            'Guests': ['Send invitations', 'Track RSVPs'],
            'Logistics': ['Book venue', 'Arrange setup'],
        })
        
        # Create tasks for each category
        for category_name, task_titles in templates.items():
            for title in task_titles:
                task = Task(
                    event_id=event.id,
                    creator_id=event.creator_id,
                    title=title,
                    category=category_name,
                    status=TaskStatus.TODO,
                    priority=TaskPriority.MEDIUM
                )
                self.db.add(task)
        
        self.db.commit()
