from sqlalchemy import Column, String, Text, DateTime, Integer, Float, Boolean, ForeignKey, Table, Index
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.shared_models import (
    TimestampMixin, SoftDeleteMixin, ActiveMixin, IDMixin,
    EventType, EventStatus, RSVPStatus, TaskStatus, TaskPriority
)

# Association table for event collaborators (many-to-many)
event_collaborators = Table(
    'event_collaborators',
    Base.metadata,
    Column('event_id', ForeignKey('events.id'), primary_key=True),
    Column('user_id', ForeignKey('users.id'), primary_key=True)
)

class Event(Base, IDMixin, TimestampMixin, SoftDeleteMixin, ActiveMixin):
    """Main event model"""
    __tablename__ = "events"
    
    # Basic event information
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(String(50), nullable=False, default=EventType.OTHER)
    status = Column(String(50), nullable=False, default=EventStatus.DRAFT)
    
    # Date and time
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=True)
    timezone = Column(String(50), nullable=True)
    
    # Location
    venue_name = Column(String(255), nullable=True)
    venue_address = Column(Text, nullable=True)
    venue_city = Column(String(100), nullable=True)
    venue_country = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Event settings
    is_public = Column(Boolean, default=False, nullable=False)
    max_attendees = Column(Integer, nullable=True)
    requires_approval = Column(Boolean, default=False, nullable=False)
    allow_guest_invites = Column(Boolean, default=True, nullable=False)
    
    # Budget information
    total_budget = Column(Float, nullable=True)
    currency = Column(String(3), default="USD", nullable=False)
    
    # Event theme and styling
    theme_color = Column(String(7), nullable=True)  # Hex color
    cover_image_url = Column(String(500), nullable=True)
    
    # Creator relationship
    creator_id = Column(ForeignKey("users.id"), nullable=False)
    creator = relationship("User", back_populates="created_events", foreign_keys=[creator_id])
    
    # Collaborators (many-to-many)
    collaborators = relationship(
        "User",
        secondary=event_collaborators,
        backref="collaborated_events"
    )
    
    # Related models
    invitations = relationship("EventInvitation", back_populates="event", cascade="all, delete-orphan")
    contact_invitations = relationship("ContactInvitation", back_populates="event", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="event", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="event", cascade="all, delete-orphan")
    media = relationship("Media", back_populates="event")
    comments = relationship("Comment", back_populates="event", cascade="all, delete-orphan")
    polls = relationship("Poll", back_populates="event", cascade="all, delete-orphan")
    
    # Message relationships
    messages = relationship("Message", back_populates="event", cascade="all, delete-orphan")
    chat_settings = relationship("EventChatSettings", back_populates="event", uselist=False, cascade="all, delete-orphan")
    
    # Creative feature relationships
    moodboards = relationship("Moodboard", back_populates="event", cascade="all, delete-orphan")
    playlists = relationship("Playlist", back_populates="event", cascade="all, delete-orphan")
    games = relationship("Game", back_populates="event", cascade="all, delete-orphan")
    game_sessions = relationship("GameSession", back_populates="event", cascade="all, delete-orphan")
    
    # Timeline relationships
    timelines = relationship("EventTimeline", back_populates="event", cascade="all, delete-orphan")
    
    # Notification relationships
    smart_reminders = relationship("SmartReminder", back_populates="event", cascade="all, delete-orphan")
    notification_logs = relationship("NotificationLog", back_populates="event", cascade="all, delete-orphan")
    
    # Vendor relationships
    vendor_bookings = relationship("VendorBooking", back_populates="event", cascade="all, delete-orphan")
    
    # Database indexes for performance
    __table_args__ = (
        Index('idx_event_creator_id', 'creator_id'),
        Index('idx_event_status', 'status'),
        Index('idx_event_type', 'event_type'),
        Index('idx_event_start_datetime', 'start_datetime'),
        Index('idx_event_venue_city', 'venue_city'),
        Index('idx_event_is_public', 'is_public'),
        Index('idx_event_created_at', 'created_at'),
        Index('idx_event_is_deleted', 'is_deleted'),
        Index('idx_event_is_active', 'is_active'),
        # Combined indexes for common queries
        Index('idx_event_creator_status', 'creator_id', 'status'),
        Index('idx_event_type_status', 'event_type', 'status'),
        Index('idx_event_city_type', 'venue_city', 'event_type'),
        Index('idx_event_date_status', 'start_datetime', 'status'),
        Index('idx_event_location', 'latitude', 'longitude'),
    )
    
    def __repr__(self):
        return f"<Event(id={self.id}, title='{self.title}', status='{self.status}')>"
    
    @property
    def attendee_count(self):
        """Get count of confirmed attendees"""
        return len([inv for inv in self.invitations if inv.rsvp_status == RSVPStatus.ACCEPTED])
    
    @property
    def total_expenses(self):
        """Get total expenses for this event"""
        return sum(expense.amount for expense in self.expenses if not expense.is_deleted)
    
    @property
    def task_categories(self):
        """Get tasks grouped by category"""
        from collections import defaultdict
        
        # Group tasks by category
        categories_dict = defaultdict(list)
        for task in self.tasks:
            if not task.is_deleted:
                categories_dict[task.category or 'Other'].append({
                    'id': task.id,
                    'title': task.title,
                    'description': task.description,
                    'completed': task.status == TaskStatus.COMPLETED,
                    'assignee_id': task.assigned_to_id
                })
        
        # Format as list of categories
        categories = []
        for category_name, items in categories_dict.items():
            categories.append({
                'name': category_name,
                'items': items
            })
        
        return categories

class EventInvitation(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    """Event invitation model"""
    __tablename__ = "event_invitations"
    
    event_id = Column(ForeignKey("events.id"), nullable=False)
    user_id = Column(ForeignKey("users.id"), nullable=False)
    
    # Invitation details
    rsvp_status = Column(String(20), default=RSVPStatus.PENDING, nullable=False)
    invitation_message = Column(Text, nullable=True)
    response_message = Column(Text, nullable=True)
    
    # Guest information
    plus_one_allowed = Column(Boolean, default=False, nullable=False)
    plus_one_name = Column(String(255), nullable=True)
    dietary_restrictions = Column(Text, nullable=True)
    special_requests = Column(Text, nullable=True)
    
    # Timestamps
    invited_at = Column(DateTime, nullable=True)
    responded_at = Column(DateTime, nullable=True)
    
    # Relationships
    event = relationship("Event", back_populates="invitations")
    user = relationship("User", back_populates="event_invitations")
    
    # Database indexes for performance
    __table_args__ = (
        Index('idx_invitation_event_id', 'event_id'),
        Index('idx_invitation_user_id', 'user_id'),
        Index('idx_invitation_rsvp_status', 'rsvp_status'),
        Index('idx_invitation_invited_at', 'invited_at'),
        Index('idx_invitation_responded_at', 'responded_at'),
        Index('idx_invitation_is_deleted', 'is_deleted'),
        # Combined indexes for common queries
        Index('idx_invitation_event_status', 'event_id', 'rsvp_status'),
        Index('idx_invitation_user_status', 'user_id', 'rsvp_status'),
    )
    
    def __repr__(self):
        return f"<EventInvitation(event_id={self.event_id}, user_id={self.user_id}, status='{self.rsvp_status}')>"

class Task(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    """Task/checklist item model"""
    __tablename__ = "tasks"
    
    event_id = Column(ForeignKey("events.id"), nullable=False)
    creator_id = Column(ForeignKey("users.id"), nullable=False)
    assigned_to_id = Column(ForeignKey("users.id"), nullable=True)
    
    # Task details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default=TaskStatus.TODO, nullable=False)
    priority = Column(String(20), default=TaskPriority.MEDIUM, nullable=False)
    
    # Timing
    due_date = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Budget related
    estimated_cost = Column(Float, nullable=True)
    actual_cost = Column(Float, nullable=True)
    
    # Task categorization
    category = Column(String(100), nullable=True)  # food, decorations, venue, etc.
    
    # Relationships
    event = relationship("Event", back_populates="tasks")
    creator = relationship("User", back_populates="created_tasks", foreign_keys=[creator_id])
    assigned_to = relationship("User", back_populates="assigned_tasks", foreign_keys=[assigned_to_id])
    timeline_items = relationship("TimelineItem", back_populates="task")
    
    # Database indexes for performance
    __table_args__ = (
        Index('idx_task_event_id', 'event_id'),
        Index('idx_task_creator_id', 'creator_id'),
        Index('idx_task_assignee_id', 'assigned_to_id'),
        Index('idx_task_status', 'status'),
        Index('idx_task_priority', 'priority'),
        Index('idx_task_due_date', 'due_date'),
        Index('idx_task_completed_at', 'completed_at'),
        Index('idx_task_category', 'category'),
        Index('idx_task_is_deleted', 'is_deleted'),
        # Combined indexes for common queries
        Index('idx_task_event_status', 'event_id', 'status'),
        Index('idx_task_assignee_status', 'assigned_to_id', 'status'),
        Index('idx_task_due_status', 'due_date', 'status'),
        Index('idx_task_priority_status', 'priority', 'status'),
    )
    
    def __repr__(self):
        return f"<Task(id={self.id}, title='{self.title}', status='{self.status}')>"

class Expense(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    """Event expense tracking model"""
    __tablename__ = "expenses"
    
    event_id = Column(ForeignKey("events.id"), nullable=False)
    paid_by_user_id = Column(ForeignKey("users.id"), nullable=False)
    
    # Expense details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    
    # Expense metadata
    category = Column(String(100), nullable=True)
    receipt_url = Column(String(500), nullable=True)
    vendor_name = Column(String(255), nullable=True)
    expense_date = Column(DateTime, nullable=False)
    
    # Split information
    is_shared = Column(Boolean, default=False, nullable=False)
    split_equally = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    event = relationship("Event", back_populates="expenses")
    paid_by_user = relationship("User", foreign_keys=[paid_by_user_id], back_populates="paid_expenses")
    splits = relationship("ExpenseSplit", back_populates="expense", cascade="all, delete-orphan")
    
    # Database indexes for performance
    __table_args__ = (
        Index('idx_expense_event_id', 'event_id'),
        Index('idx_expense_paid_by_user_id', 'paid_by_user_id'),
        Index('idx_expense_amount', 'amount'),
        Index('idx_expense_category', 'category'),
        Index('idx_expense_date', 'expense_date'),
        Index('idx_expense_is_shared', 'is_shared'),
        Index('idx_expense_is_deleted', 'is_deleted'),
        # Combined indexes for common queries
        Index('idx_expense_event_category', 'event_id', 'category'),
        Index('idx_expense_event_date', 'event_id', 'expense_date'),
        Index('idx_expense_user_date', 'paid_by_user_id', 'expense_date'),
    )
    
    def __repr__(self):
        return f"<Expense(id={self.id}, title='{self.title}', amount={self.amount})>"

class ExpenseSplit(Base, IDMixin, TimestampMixin):
    """Expense split details"""
    __tablename__ = "expense_splits"
    
    expense_id = Column(ForeignKey("expenses.id"), nullable=False)
    user_id = Column(ForeignKey("users.id"), nullable=False)
    
    # Split details
    amount_owed = Column(Float, nullable=False)
    is_paid = Column(Boolean, default=False, nullable=False)
    paid_at = Column(DateTime, nullable=True)
    
    # Relationships
    expense = relationship("Expense", back_populates="splits")
    user = relationship("User", foreign_keys=[user_id], back_populates="expense_splits")
    
    def __repr__(self):
        return f"<ExpenseSplit(expense_id={self.expense_id}, user_id={self.user_id}, amount={self.amount_owed})>"

class Comment(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    """Comments on events"""
    __tablename__ = "comments"
    
    event_id = Column(ForeignKey("events.id"), nullable=False)
    author_id = Column(ForeignKey("users.id"), nullable=False)
    parent_id = Column(ForeignKey("comments.id"), nullable=True)  # For replies
    
    # Comment content
    content = Column(Text, nullable=False)
    
    # Relationships
    event = relationship("Event", back_populates="comments")
    author = relationship("User", back_populates="comments")
    replies = relationship("Comment", backref="parent", remote_side="Comment.id")
    
    # Database indexes for performance
    __table_args__ = (
        Index('idx_comment_event_id', 'event_id'),
        Index('idx_comment_author_id', 'author_id'),
        Index('idx_comment_parent_id', 'parent_id'),
        Index('idx_comment_created_at', 'created_at'),
        Index('idx_comment_is_deleted', 'is_deleted'),
        # Combined indexes for common queries
        Index('idx_comment_event_created', 'event_id', 'created_at'),
        Index('idx_comment_author_created', 'author_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Comment(id={self.id}, event_id={self.event_id}, author_id={self.author_id})>"

class Poll(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    """Polls for event decisions"""
    __tablename__ = "polls"
    
    event_id = Column(ForeignKey("events.id"), nullable=False)
    creator_id = Column(ForeignKey("users.id"), nullable=False)
    
    # Poll details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Poll settings
    multiple_choice = Column(Boolean, default=False, nullable=False)
    anonymous = Column(Boolean, default=False, nullable=False)
    closes_at = Column(DateTime, nullable=True)
    
    # Relationships
    event = relationship("Event", back_populates="polls")
    creator = relationship("User", foreign_keys=[creator_id], back_populates="created_polls")
    options = relationship("PollOption", back_populates="poll", cascade="all, delete-orphan")
    
    # Database indexes for performance
    __table_args__ = (
        Index('idx_poll_event_id', 'event_id'),
        Index('idx_poll_creator_id', 'creator_id'),
        Index('idx_poll_closes_at', 'closes_at'),
        Index('idx_poll_created_at', 'created_at'),
        Index('idx_poll_is_deleted', 'is_deleted'),
        # Combined indexes for common queries
        Index('idx_poll_event_created', 'event_id', 'created_at'),
        Index('idx_poll_creator_created', 'creator_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Poll(id={self.id}, title='{self.title}', event_id={self.event_id})>"

class PollOption(Base, IDMixin, TimestampMixin):
    """Poll option choices"""
    __tablename__ = "poll_options"
    
    poll_id = Column(ForeignKey("polls.id"), nullable=False)
    
    # Option details
    text = Column(String(255), nullable=False)
    order_index = Column(Integer, default=0, nullable=False)
    
    # Relationships
    poll = relationship("Poll", back_populates="options")
    votes = relationship("PollVote", back_populates="option", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<PollOption(id={self.id}, text='{self.text}', poll_id={self.poll_id})>"
    
    @property
    def vote_count(self):
        """Get vote count for this option"""
        return len(self.votes)

class PollVote(Base, IDMixin, TimestampMixin):
    """Poll votes"""
    __tablename__ = "poll_votes"
    
    poll_id = Column(ForeignKey("polls.id"), nullable=False)
    option_id = Column(ForeignKey("poll_options.id"), nullable=False)
    user_id = Column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    poll = relationship("Poll", backref="votes")
    option = relationship("PollOption", back_populates="votes")
    user = relationship("User", foreign_keys=[user_id], back_populates="poll_votes")
    
    def __repr__(self):
        return f"<PollVote(poll_id={self.poll_id}, option_id={self.option_id}, user_id={self.user_id})>"