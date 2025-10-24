from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
from app.models.event_models import (
    Event, EventInvitation, Task, Expense, ExpenseSplit, Comment, Poll, PollOption, PollVote
)
from app.models.user_models import User
from app.models.shared_models import EventStatus, RSVPStatus, TaskStatus
from app.schemas.event import (
    EventCreate, EventUpdate, EventInvitationCreate, EventInvitationUpdate,
    TaskCreate, TaskUpdate, ExpenseCreate, ExpenseUpdate, CommentCreate,
    PollCreate, PollVoteCreate
)
from app.schemas.location import Coordinates
from app.core.errors import NotFoundError, ValidationError, ConflictError, AuthorizationError
from app.services.user_service import UserService
from app.services.email_service import email_service
from app.services.google_maps_service import google_maps_service
from app.services.calendar_service import CalendarServiceFactory, CalendarProvider, SyncStatus
from app.models.calendar_models import CalendarConnection, CalendarEvent
import asyncio
import logging

logger = logging.getLogger(__name__)

class EventService:
    """Service for event-related business logic"""
    
    def __init__(self, db: Session):
        self.db = db
        self.user_service = UserService(db)
    
    # Event CRUD operations
    def get_event_by_id(self, event_id: int, user_id: Optional[int] = None) -> Optional[Event]:
        """Get event by ID with access control using read replicas for better performance"""
        # Try to get from cache first
        cache_key = f"event:{event_id}:user:{user_id}"
        try:
            from app.core.cache import cache_service
            cached_event = cache_service.get(cache_key)
            if cached_event:
                return cached_event
        except Exception as e:
            logger.warning(f"Cache retrieval error: {e}")
        
        # Use read replica if available
        try:
            from app.core.db_optimizations import get_read_db
            read_db = get_read_db() or self.db
            event = read_db.query(Event).filter(Event.id == event_id).first()
        except Exception as e:
            logger.warning(f"Read replica error, falling back to primary: {e}")
            event = self.db.query(Event).filter(Event.id == event_id).first()
        
        if not event:
            return None
        
        # Check access permissions
        if user_id and not self._can_access_event(event, user_id):
            raise AuthorizationError("Access denied to this event")
        
        # Cache the result for future requests
        try:
            from app.core.cache import cache_service
            cache_service.set(cache_key, event, ttl=300)  # Cache for 5 minutes
        except Exception as e:
            logger.warning(f"Cache storage error: {e}")
        
        return event
    
    def create_event(self, event_data: EventCreate, creator_id: int) -> Event:
        """Create a new event with location optimization"""
        # Validate creator exists
        creator = self.user_service.get_user_by_id(creator_id)
        if not creator:
            raise NotFoundError("Creator not found")
        
        # Validate event dates
        if event_data.end_datetime and event_data.end_datetime <= event_data.start_datetime:
            raise ValidationError("End date must be after start date")
        
        # Prepare event data
        event_dict = event_data.model_dump()
        
        # Handle location optimization if requested
        if event_data.location_input and event_data.auto_optimize_location:
            try:
                # Convert user_coordinates to Coordinates object if provided
                user_coords = None
                if event_data.user_coordinates:
                    user_coords = Coordinates(
                        latitude=event_data.user_coordinates.get('latitude'),
                        longitude=event_data.user_coordinates.get('longitude')
                    )
                
                # Optimize location using Google Maps
                optimization_result = asyncio.run(
                    google_maps_service.optimize_location_input(
                        user_input=event_data.location_input,
                        user_coordinates=user_coords,
                        include_nearby=False,
                        max_suggestions=1
                    )
                )
                
                if optimization_result.optimized and optimization_result.validation.is_valid:
                    # Update event data with optimized location
                    event_dict['venue_address'] = optimization_result.validation.formatted_address
                    if optimization_result.validation.coordinates:
                        event_dict['latitude'] = optimization_result.validation.coordinates.latitude
                        event_dict['longitude'] = optimization_result.validation.coordinates.longitude
                    
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
        event_dict.pop('user_coordinates', None)
        event_dict.pop('auto_optimize_location', None)
        
        # Create event
        event = Event(
            **event_dict,
            creator_id=creator_id,
            status=EventStatus.DRAFT
        )
        
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        
        # Automatically add creator as collaborator
        event.collaborators.append(creator)
        self.db.commit()
        
        # Sync with connected calendars
        asyncio.create_task(self._sync_event_to_calendars(event, 'create'))
        
        return event
    
    def update_event(self, event_id: int, event_data: EventUpdate, user_id: int) -> Event:
        """Update event information"""
        event = self.get_event_by_id(event_id, user_id)
        if not event:
            raise NotFoundError("Event not found")
        
        # Check if user can edit event
        if not self._can_edit_event(event, user_id):
            raise AuthorizationError("Permission denied to edit this event")
        
        # Validate dates if being updated
        update_data = event_data.model_dump(exclude_unset=True)
        if 'end_datetime' in update_data and 'start_datetime' in update_data:
            if update_data['end_datetime'] and update_data['end_datetime'] <= update_data['start_datetime']:
                raise ValidationError("End date must be after start date")
        
        # Update event fields
        for field, value in update_data.items():
            if hasattr(event, field):
                setattr(event, field, value)
        
        self.db.commit()
        self.db.refresh(event)
        
        # Sync with connected calendars
        asyncio.create_task(self._sync_event_to_calendars(event, 'update'))
        
        return event
    
    def delete_event(self, event_id: int, user_id: int) -> bool:
        """Delete event (soft delete)"""
        event = self.get_event_by_id(event_id, user_id)
        if not event:
            raise NotFoundError("Event not found")
        
        # Only creator can delete event
        if event.creator_id != user_id:
            raise AuthorizationError("Only event creator can delete the event")
        
        event.soft_delete()
        self.db.commit()
        
        # Sync deletion with connected calendars
        asyncio.create_task(self._sync_event_to_calendars(event, 'delete'))
        
        return True
    
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
        creator = self.db.query(User).filter(User.id == user_id).first()
        if creator:
            duplicate_event.collaborators.append(creator)
        
        # Copy tasks from original event
        original_tasks = self.db.query(Task).filter(
            Task.event_id == event_id,
            Task.is_deleted == False
        ).all()
        
        for task in original_tasks:
            new_task = Task(
                event_id=duplicate_event.id,
                title=task.title,
                description=task.description,
                due_date=task.due_date,
                priority=task.priority,
                assigned_to_id=None,  # Don't copy assignments
                creator_id=user_id,
                status=TaskStatus.PENDING
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
        query = self.db.query(Event).filter(
            or_(
                Event.creator_id == user_id,
                Event.collaborators.any(User.id == user_id),
                Event.invitations.any(
                    and_(
                        EventInvitation.user_id == user_id,
                        EventInvitation.rsvp_status == RSVPStatus.ACCEPTED
                    )
                )
            ),
            Event.is_deleted == False
        )
        
        if status:
            query = query.filter(Event.status == status)
        
        return query.offset(skip).limit(limit).all()
    
    def search_events(
        self, 
        query: str, 
        user_id: Optional[int] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[Event]:
        """Search public events or user's events"""
        search_filter = or_(
            Event.title.ilike(f"%{query}%"),
            Event.description.ilike(f"%{query}%"),
            Event.venue_name.ilike(f"%{query}%")
        )
        
        db_query = self.db.query(Event).filter(
            search_filter,
            Event.is_deleted == False
        )
        
        if user_id:
            # Include user's private events and public events
            db_query = db_query.filter(
                or_(
                    Event.is_public == True,
                    Event.creator_id == user_id,
                    Event.collaborators.any(User.id == user_id)
                )
            )
        else:
            # Only public events for anonymous users
            db_query = db_query.filter(Event.is_public == True)
        
        return db_query.offset(skip).limit(limit).all()
    
    # Event invitation methods
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
            existing_invitation = self.db.query(EventInvitation).filter(
                EventInvitation.event_id == event_id,
                EventInvitation.user_id == user_id
            ).first()
            
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
        invitation = self.db.query(EventInvitation).filter(
            EventInvitation.id == invitation_id,
            EventInvitation.user_id == user_id
        ).first()
        
        if not invitation:
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
        
        task = Task(
            **task_data.model_dump(),
            event_id=event_id,
            creator_id=creator_id
        )
        
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task
    
    def update_task(self, task_id: int, task_data: TaskUpdate, user_id: int) -> Task:
        """Update a task"""
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise NotFoundError("Task not found")
        
        # Check permissions
        if not self._can_edit_task(task, user_id):
            raise AuthorizationError("Permission denied to edit this task")
        
        # Update task fields
        update_data = task_data.model_dump(exclude_unset=True)
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
        
        return event.expenses
    
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
        """Get all comments for an event"""
        event = self.get_event_by_id(event_id, user_id)
        if not event:
            raise NotFoundError("Event not found")
        
        return event.comments
    
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
        poll = self.db.query(Poll).filter(Poll.id == poll_id).first()
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
            self.db.query(PollVote).filter(
                PollVote.poll_id == poll_id,
                PollVote.user_id == user_id
            ).delete()
        
        # Create new votes
        votes = []
        for option_id in vote_data.option_ids:
            # Validate option belongs to poll
            option = self.db.query(PollOption).filter(
                PollOption.id == option_id,
                PollOption.poll_id == poll_id
            ).first()
            
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
        
        # Calculate budget info
        total_expenses = sum(exp.amount for exp in event.expenses)
        budget_remaining = (event.total_budget - total_expenses) if event.total_budget else None
        
        return {
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
            connections = self.db.query(CalendarConnection).filter(
                CalendarConnection.user_id == event.creator_id,
                CalendarConnection.sync_enabled == True,
                CalendarConnection.sync_status != SyncStatus.DISABLED
            ).all()
            
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
        connections = self.db.query(CalendarConnection).filter(
            CalendarConnection.user_id == user_id
        ).all()
        
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
            connections = self.db.query(CalendarConnection).filter(
                CalendarConnection.user_id == user_id,
                CalendarConnection.sync_enabled == True
            ).all()
            
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