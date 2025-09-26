import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.services.event_service import EventService
from app.services.auth_service import AuthService
from app.schemas.event import (
    EventCreate, EventUpdate, EventInvitationCreate, EventInvitationUpdate,
    TaskCreate, TaskUpdate, ExpenseCreate, CommentCreate, PollCreate, PollVoteCreate
)
from app.models.shared_models import EventStatus, RSVPStatus, TaskStatus
from app.core.errors import NotFoundError, ValidationError, AuthorizationError
from app.tests.conftest import UserFactory, EventFactory

class TestEventService:
    """Test cases for EventService."""
    
    def test_create_event(self, event_service: EventService, test_user):
        """Test creating a new event."""
        event_data = EventCreate(
            title="Test Event",
            description="A test event",
            event_type="party",
            start_datetime=datetime.utcnow() + timedelta(days=7),
            end_datetime=datetime.utcnow() + timedelta(days=7, hours=3),
            venue_name="Test Venue",
            is_public=False
        )
        
        event = event_service.create_event(event_data, test_user.id)
        
        assert event.title == "Test Event"
        assert event.description == "A test event"
        assert event.event_type == "party"
        assert event.creator_id == test_user.id
        assert event.status == EventStatus.DRAFT
        assert len(event.collaborators) == 1  # Creator is auto-added as collaborator
    
    def test_create_event_invalid_dates(self, event_service: EventService, test_user):
        """Test creating event with invalid date range."""
        start_time = datetime.utcnow() + timedelta(days=7)
        end_time = start_time - timedelta(hours=1)  # End before start
        
        event_data = EventCreate(
            title="Invalid Event",
            start_datetime=start_time,
            end_datetime=end_time,
            event_type="party"
        )
        
        with pytest.raises(ValidationError, match="after start date"):
            event_service.create_event(event_data, test_user.id)
    
    def test_create_event_nonexistent_creator(self, event_service: EventService):
        """Test creating event with non-existent creator."""
        event_data = EventCreate(
            title="Test Event",
            start_datetime=datetime.utcnow() + timedelta(days=7),
            event_type="party"
        )
        
        with pytest.raises(NotFoundError, match="Creator not found"):
            event_service.create_event(event_data, 99999)
    
    def test_get_event_by_id(self, event_service: EventService, test_user):
        """Test getting event by ID."""
        # Create event
        event_data = EventCreate(
            title="Test Event",
            start_datetime=datetime.utcnow() + timedelta(days=7),
            event_type="party"
        )
        created_event = event_service.create_event(event_data, test_user.id)
        
        # Get event
        retrieved_event = event_service.get_event_by_id(created_event.id, test_user.id)
        
        assert retrieved_event is not None
        assert retrieved_event.id == created_event.id
        assert retrieved_event.title == "Test Event"
    
    def test_get_event_by_id_not_found(self, event_service: EventService, test_user):
        """Test getting non-existent event."""
        event = event_service.get_event_by_id(99999, test_user.id)
        assert event is None
    
    def test_get_event_access_denied(self, event_service: EventService, auth_service: AuthService, test_user):
        """Test accessing private event without permission."""
        # Create another user
        other_user = UserFactory.create_user(auth_service)
        
        # Create private event
        event_data = EventCreate(
            title="Private Event",
            start_datetime=datetime.utcnow() + timedelta(days=7),
            event_type="party",
            is_public=False
        )
        created_event = event_service.create_event(event_data, test_user.id)
        
        # Try to access with other user
        with pytest.raises(AuthorizationError, match="Access denied"):
            event_service.get_event_by_id(created_event.id, other_user.id)
    
    def test_update_event(self, event_service: EventService, test_user):
        """Test updating an event."""
        # Create event
        event_data = EventCreate(
            title="Original Title",
            start_datetime=datetime.utcnow() + timedelta(days=7),
            event_type="party"
        )
        created_event = event_service.create_event(event_data, test_user.id)
        
        # Update event
        update_data = EventUpdate(
            title="Updated Title",
            description="Updated description",
            status=EventStatus.PLANNING
        )
        
        updated_event = event_service.update_event(created_event.id, update_data, test_user.id)
        
        assert updated_event.title == "Updated Title"
        assert updated_event.description == "Updated description"
        assert updated_event.status == EventStatus.PLANNING
    
    def test_update_event_permission_denied(self, event_service: EventService, auth_service: AuthService, test_user):
        """Test updating event without permission."""
        # Create another user
        other_user = UserFactory.create_user(auth_service)
        
        # Create event
        event_data = EventCreate(
            title="Test Event",
            start_datetime=datetime.utcnow() + timedelta(days=7),
            event_type="party"
        )
        created_event = event_service.create_event(event_data, test_user.id)
        
        # Try to update with other user
        update_data = EventUpdate(title="Unauthorized Update")
        
        with pytest.raises(AuthorizationError, match="Permission denied"):
            event_service.update_event(created_event.id, update_data, other_user.id)
    
    def test_delete_event(self, event_service: EventService, test_user):
        """Test deleting an event."""
        # Create event
        event_data = EventCreate(
            title="Test Event",
            start_datetime=datetime.utcnow() + timedelta(days=7),
            event_type="party"
        )
        created_event = event_service.create_event(event_data, test_user.id)
        
        # Delete event
        success = event_service.delete_event(created_event.id, test_user.id)
        assert success is True
        
        # Verify event is soft deleted
        deleted_event = event_service.get_event_by_id(created_event.id, test_user.id)
        assert deleted_event is None
    
    def test_delete_event_only_creator(self, event_service: EventService, auth_service: AuthService, test_user):
        """Test that only creator can delete event."""
        # Create another user
        other_user = UserFactory.create_user(auth_service)
        
        # Create event
        event_data = EventCreate(
            title="Test Event",
            start_datetime=datetime.utcnow() + timedelta(days=7),
            event_type="party"
        )
        created_event = event_service.create_event(event_data, test_user.id)
        
        # Try to delete with other user
        with pytest.raises(AuthorizationError, match="Only event creator"):
            event_service.delete_event(created_event.id, other_user.id)
    
    def test_get_user_events(self, event_service: EventService, test_user):
        """Test getting user's events."""
        # Create multiple events
        for i in range(3):
            event_data = EventCreate(
                title=f"Event {i}",
                start_datetime=datetime.utcnow() + timedelta(days=7+i),
                event_type="party"
            )
            event_service.create_event(event_data, test_user.id)
        
        # Get user events
        events = event_service.get_user_events(test_user.id, skip=0, limit=10)
        
        assert len(events) == 3
        assert all(event.creator_id == test_user.id for event in events)
    
    def test_search_events(self, event_service: EventService, test_user):
        """Test searching events."""
        # Create searchable event
        event_data = EventCreate(
            title="Searchable Birthday Party",
            description="A fun birthday celebration",
            start_datetime=datetime.utcnow() + timedelta(days=7),
            event_type="birthday",
            venue_name="Party Venue",
            is_public=True
        )
        event_service.create_event(event_data, test_user.id)
        
        # Search by title
        results = event_service.search_events("Birthday", user_id=test_user.id)
        assert len(results) >= 1
        assert any("Birthday" in event.title for event in results)
        
        # Search by venue
        results = event_service.search_events("Party Venue", user_id=test_user.id)
        assert len(results) >= 1
        assert any("Party Venue" in (event.venue_name or "") for event in results)

class TestEventInvitations:
    """Test event invitation functionality."""
    
    def test_invite_users(self, event_service: EventService, auth_service: AuthService, test_user):
        """Test inviting users to an event."""
        # Create invitees
        invitee1 = UserFactory.create_user(auth_service)
        invitee2 = UserFactory.create_user(auth_service)
        
        # Create event
        event_data = EventCreate(
            title="Test Event",
            start_datetime=datetime.utcnow() + timedelta(days=7),
            event_type="party"
        )
        created_event = event_service.create_event(event_data, test_user.id)
        
        # Invite users
        invitation_data = EventInvitationCreate(
            user_ids=[invitee1.id, invitee2.id],
            invitation_message="Please join our event!",
            plus_one_allowed=True
        )
        
        invitations = event_service.invite_users(created_event.id, invitation_data, test_user.id)
        
        assert len(invitations) == 2
        assert all(inv.rsvp_status == RSVPStatus.PENDING for inv in invitations)
        assert all(inv.plus_one_allowed is True for inv in invitations)
    
    def test_invite_users_permission_denied(self, event_service: EventService, auth_service: AuthService, test_user):
        """Test inviting users without permission."""
        # Create another user and invitee
        other_user = UserFactory.create_user(auth_service)
        invitee = UserFactory.create_user(auth_service)
        
        # Create event
        event_data = EventCreate(
            title="Test Event",
            start_datetime=datetime.utcnow() + timedelta(days=7),
            event_type="party",
            allow_guest_invites=False  # Only organizers can invite
        )
        created_event = event_service.create_event(event_data, test_user.id)
        
        # Try to invite with other user
        invitation_data = EventInvitationCreate(user_ids=[invitee.id])
        
        with pytest.raises(AuthorizationError, match="Permission denied"):
            event_service.invite_users(created_event.id, invitation_data, other_user.id)
    
    def test_respond_to_invitation(self, event_service: EventService, auth_service: AuthService, test_user):
        """Test responding to an event invitation."""
        # Create invitee
        invitee = UserFactory.create_user(auth_service)
        
        # Create event and invite user
        event_data = EventCreate(
            title="Test Event",
            start_datetime=datetime.utcnow() + timedelta(days=7),
            event_type="party"
        )
        created_event = event_service.create_event(event_data, test_user.id)
        
        invitation_data = EventInvitationCreate(user_ids=[invitee.id])
        invitations = event_service.invite_users(created_event.id, invitation_data, test_user.id)
        invitation_id = invitations[0].id
        
        # Respond to invitation
        response_data = EventInvitationUpdate(
            rsvp_status=RSVPStatus.ACCEPTED,
            response_message="I'll be there!",
            dietary_restrictions="Vegetarian"
        )
        
        updated_invitation = event_service.respond_to_invitation(
            invitation_id, response_data, invitee.id
        )
        
        assert updated_invitation.rsvp_status == RSVPStatus.ACCEPTED
        assert updated_invitation.response_message == "I'll be there!"
        assert updated_invitation.dietary_restrictions == "Vegetarian"
        assert updated_invitation.responded_at is not None

class TestEventTasks:
    """Test event task management."""
    
    def test_create_task(self, event_service: EventService, test_user):
        """Test creating a task for an event."""
        # Create event
        event_data = EventCreate(
            title="Test Event",
            start_datetime=datetime.utcnow() + timedelta(days=7),
            event_type="party"
        )
        created_event = event_service.create_event(event_data, test_user.id)
        
        # Create task
        task_data = TaskCreate(
            title="Buy decorations",
            description="Get party decorations",
            priority="high",
            due_date=datetime.utcnow() + timedelta(days=3),
            estimated_cost=50.0,
            category="decorations"
        )
        
        task = event_service.create_task(created_event.id, task_data, test_user.id)
        
        assert task.title == "Buy decorations"
        assert task.event_id == created_event.id
        assert task.creator_id == test_user.id
        assert task.status == TaskStatus.TODO
        assert task.priority == "high"
    
    def test_update_task(self, event_service: EventService, test_user, db_session):
        """Test updating a task."""
        # Create event and task
        event_data = EventCreate(
            title="Test Event",
            start_datetime=datetime.utcnow() + timedelta(days=7),
            event_type="party"
        )
        created_event = event_service.create_event(event_data, test_user.id)
        
        task_data = TaskCreate(
            title="Original Task",
            description="Original description"
        )
        created_task = event_service.create_task(created_event.id, task_data, test_user.id)
        
        # Update task
        update_data = TaskUpdate(
            title="Updated Task",
            status=TaskStatus.COMPLETED,
            actual_cost=75.0
        )
        
        updated_task = event_service.update_task(created_task.id, update_data, test_user.id)
        
        assert updated_task.title == "Updated Task"
        assert updated_task.status == TaskStatus.COMPLETED
        assert updated_task.actual_cost == 75.0
        assert updated_task.completed_at is not None

class TestEventExpenses:
    """Test event expense management."""
    
    def test_create_expense(self, event_service: EventService, test_user):
        """Test creating an expense for an event."""
        # Create event
        event_data = EventCreate(
            title="Test Event",
            start_datetime=datetime.utcnow() + timedelta(days=7),
            event_type="party"
        )
        created_event = event_service.create_event(event_data, test_user.id)
        
        # Create expense
        expense_data = ExpenseCreate(
            title="Venue Rental",
            description="Party venue rental fee",
            amount=200.0,
            currency="USD",
            category="venue",
            vendor_name="Party Palace",
            expense_date=datetime.utcnow(),
            is_shared=True,
            split_equally=True
        )
        
        expense = event_service.create_expense(created_event.id, expense_data, test_user.id)
        
        assert expense.title == "Venue Rental"
        assert expense.amount == 200.0
        assert expense.event_id == created_event.id
        assert expense.paid_by_user_id == test_user.id

class TestEventComments:
    """Test event comment functionality."""
    
    def test_create_comment(self, event_service: EventService, test_user):
        """Test creating a comment on an event."""
        # Create event
        event_data = EventCreate(
            title="Test Event",
            start_datetime=datetime.utcnow() + timedelta(days=7),
            event_type="party"
        )
        created_event = event_service.create_event(event_data, test_user.id)
        
        # Create comment
        comment_data = CommentCreate(
            content="This event looks great!",
            parent_id=None
        )
        
        comment = event_service.create_comment(created_event.id, comment_data, test_user.id)
        
        assert comment.content == "This event looks great!"
        assert comment.event_id == created_event.id
        assert comment.author_id == test_user.id
        assert comment.parent_id is None

class TestEventPolls:
    """Test event poll functionality."""
    
    def test_create_poll(self, event_service: EventService, test_user):
        """Test creating a poll for an event."""
        # Create event
        event_data = EventCreate(
            title="Test Event",
            start_datetime=datetime.utcnow() + timedelta(days=7),
            event_type="party"
        )
        created_event = event_service.create_event(event_data, test_user.id)
        
        # Create poll
        from app.schemas.event import PollOptionCreate
        poll_data = PollCreate(
            title="What time should we start?",
            description="Vote for the best start time",
            multiple_choice=False,
            anonymous=False,
            options=[
                PollOptionCreate(text="7:00 PM"),
                PollOptionCreate(text="8:00 PM"),
                PollOptionCreate(text="9:00 PM")
            ]
        )
        
        poll = event_service.create_poll(created_event.id, poll_data, test_user.id)
        
        assert poll.title == "What time should we start?"
        assert poll.event_id == created_event.id
        assert poll.creator_id == test_user.id
        assert len(poll.options) == 3
    
    def test_vote_on_poll(self, event_service: EventService, auth_service: AuthService, test_user):
        """Test voting on a poll."""
        # Create event and poll
        event_data = EventCreate(
            title="Test Event",
            start_datetime=datetime.utcnow() + timedelta(days=7),
            event_type="party"
        )
        created_event = event_service.create_event(event_data, test_user.id)
        
        from app.schemas.event import PollOptionCreate
        poll_data = PollCreate(
            title="Test Poll",
            multiple_choice=False,
            options=[
                PollOptionCreate(text="Option 1"),
                PollOptionCreate(text="Option 2")
            ]
        )
        created_poll = event_service.create_poll(created_event.id, poll_data, test_user.id)
        
        # Vote on poll
        vote_data = PollVoteCreate(option_ids=[created_poll.options[0].id])
        votes = event_service.vote_on_poll(created_poll.id, vote_data, test_user.id)
        
        assert len(votes) == 1
        assert votes[0].option_id == created_poll.options[0].id
        assert votes[0].user_id == test_user.id

class TestEventStats:
    """Test event statistics functionality."""
    
    def test_get_event_stats(self, event_service: EventService, auth_service: AuthService, test_user):
        """Test getting comprehensive event statistics."""
        # Create event
        event_data = EventCreate(
            title="Test Event",
            start_datetime=datetime.utcnow() + timedelta(days=7),
            event_type="party",
            total_budget=1000.0
        )
        created_event = event_service.create_event(event_data, test_user.id)
        
        # Add some data
        invitee = UserFactory.create_user(auth_service)
        invitation_data = EventInvitationCreate(user_ids=[invitee.id])
        event_service.invite_users(created_event.id, invitation_data, test_user.id)
        
        task_data = TaskCreate(title="Test Task")
        event_service.create_task(created_event.id, task_data, test_user.id)
        
        expense_data = ExpenseCreate(
            title="Test Expense",
            amount=100.0,
            expense_date=datetime.utcnow()
        )
        event_service.create_expense(created_event.id, expense_data, test_user.id)
        
        # Get stats
        stats = event_service.get_event_stats(created_event.id, test_user.id)
        
        assert "rsvp_counts" in stats
        assert "task_counts" in stats
        assert "total_expenses" in stats
        assert "budget_remaining" in stats
        assert stats["total_expenses"] == 100.0
        assert stats["budget_remaining"] == 900.0