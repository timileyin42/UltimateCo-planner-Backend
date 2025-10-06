from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey, Table, Index, Integer
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.shared_models import TimestampMixin, SoftDeleteMixin, ActiveMixin, IDMixin

# Association table for user friendships (many-to-many)
user_friends = Table(
    'user_friends',
    Base.metadata,
    Column('user_id', ForeignKey('users.id'), primary_key=True),
    Column('friend_id', ForeignKey('users.id'), primary_key=True)
)

class User(Base, IDMixin, TimestampMixin, SoftDeleteMixin, ActiveMixin):
    """User model"""
    __tablename__ = "users"
    
    # Basic user information
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=True)
    
    # Registration method tracking
    signup_method = Column(String(10), nullable=False, default="email")  # "email" or "phone"
    
    # Profile information
    bio = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    phone_number = Column(String(20), nullable=True)
    date_of_birth = Column(DateTime, nullable=True)
    
    # Location information
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    timezone = Column(String(50), nullable=True)
    
    # User preferences
    email_notifications = Column(Boolean, default=True, nullable=False)
    push_notifications = Column(Boolean, default=True, nullable=False)
    sms_notifications = Column(Boolean, default=False, nullable=False)
    
    # Account status
    is_verified = Column(Boolean, default=False, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    
    # Email verification OTP
    email_verification_otp = Column(String(6), nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)
    otp_attempts = Column(Integer, default=0, nullable=False)
    
    # Password reset tokens
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)
    
    # Social features
    is_public_profile = Column(Boolean, default=True, nullable=False)
    
    # Stripe integration
    stripe_customer_id = Column(String(100), nullable=True, unique=True)
    
    # Relationships
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    
    # Event relationships
    created_events = relationship("Event", foreign_keys="Event.creator_id", back_populates="creator")
    event_invitations = relationship("EventInvitation", back_populates="user")
    
    # Task relationships
    created_tasks = relationship("Task", foreign_keys="Task.creator_id", back_populates="creator")
    assigned_tasks = relationship("Task", foreign_keys="Task.assigned_to_id", back_populates="assigned_to")
    
    # Expense relationships
    paid_expenses = relationship("Expense", foreign_keys="Expense.paid_by_user_id", back_populates="paid_by_user")
    expense_splits = relationship("ExpenseSplit", back_populates="user")
    
    # Comment relationships
    comments = relationship("Comment", back_populates="author")
    
    # Poll relationships
    created_polls = relationship("Poll", back_populates="creator")
    poll_votes = relationship("PollVote", back_populates="user")
    
    # Media relationships
    uploaded_media = relationship("Media", foreign_keys="Media.uploaded_by_id", back_populates="uploaded_by")
    media_likes = relationship("MediaLike", back_populates="user")
    media_comments = relationship("MediaComment", back_populates="author")
    media_shares = relationship("MediaShare", back_populates="shared_by")
    
    # Message relationships
    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    message_reactions = relationship("MessageReaction", back_populates="user")
    message_read_receipts = relationship("MessageReadReceipt", back_populates="user")
    message_mentions = relationship("MessageMention", back_populates="mentioned_user")
    chat_participations = relationship("ChatParticipant", back_populates="user")
    
    # Creative feature relationships
    created_moodboards = relationship("Moodboard", foreign_keys="Moodboard.creator_id", back_populates="creator")
    moodboard_items = relationship("MoodboardItem", back_populates="added_by")
    moodboard_likes = relationship("MoodboardLike", back_populates="user")
    moodboard_comments = relationship("MoodboardComment", back_populates="author")
    
    created_playlists = relationship("Playlist", foreign_keys="Playlist.creator_id", back_populates="creator")
    playlist_tracks = relationship("PlaylistTrack", back_populates="added_by")
    playlist_votes = relationship("PlaylistVote", back_populates="user")
    
    created_games = relationship("Game", foreign_keys="Game.creator_id", back_populates="creator")
    hosted_game_sessions = relationship("GameSession", foreign_keys="GameSession.host_id", back_populates="host")
    game_participations = relationship("GameParticipant", back_populates="user")
    game_ratings = relationship("GameRating", back_populates="user")
    
    # Timeline relationships
    created_timelines = relationship("EventTimeline", foreign_keys="EventTimeline.creator_id", back_populates="creator")
    assigned_timeline_items = relationship("TimelineItem", foreign_keys="TimelineItem.assigned_to_id", back_populates="assigned_to")
    created_timeline_templates = relationship("TimelineTemplate", foreign_keys="TimelineTemplate.creator_id", back_populates="creator")
    timeline_notifications = relationship("TimelineNotification", back_populates="recipient")
    timeline_updates = relationship("TimelineUpdate", back_populates="updated_by")
    
    # Notification relationships
    created_reminders = relationship("SmartReminder", foreign_keys="SmartReminder.creator_id", back_populates="creator")
    received_notifications = relationship("NotificationLog", back_populates="recipient")
    notification_preferences = relationship("NotificationPreference", back_populates="user")
    created_reminder_templates = relationship("ReminderTemplate", back_populates="creator")
    created_automation_rules = relationship("AutomationRule", back_populates="creator")
    
    # Vendor relationships
    vendor_profile = relationship("Vendor", back_populates="user", uselist=False)
    vendor_bookings = relationship("VendorBooking", back_populates="booked_by")
    vendor_payments = relationship("VendorPayment", back_populates="paid_by")
    vendor_reviews = relationship("VendorReview", back_populates="reviewer")
    
    # AI Chat relationships
    ai_chat_sessions = relationship("AIChatSession", back_populates="user", cascade="all, delete-orphan")
    
    # Subscription relationships
    subscription = relationship("UserSubscription", back_populates="user", uselist=False)
    usage_limits = relationship("UsageLimit", back_populates="user", cascade="all, delete-orphan")
    
    # Friendships (many-to-many self-referential)
    friends = relationship(
        "User",
        secondary=user_friends,
        primaryjoin="User.id == user_friends.c.user_id",
        secondaryjoin="User.id == user_friends.c.friend_id",
        back_populates="friends"
    )
    
    # Invite relationships
    created_invite_codes = relationship("InviteCode", foreign_keys="InviteCode.user_id", back_populates="creator")
    used_invite_codes = relationship("InviteCode", foreign_keys="InviteCode.used_by_user_id", back_populates="used_by")
    created_invite_links = relationship("InviteLink", foreign_keys="InviteLink.user_id", back_populates="creator")
    invite_link_usages = relationship("InviteLinkUsage", foreign_keys="InviteLinkUsage.used_by_user_id", back_populates="used_by")
    
    # Contact relationships
    contacts = relationship("UserContact", foreign_keys="UserContact.user_id", back_populates="user", cascade="all, delete-orphan")
    sent_contact_invitations = relationship("ContactInvitation", foreign_keys="ContactInvitation.sender_id", back_populates="sender", cascade="all, delete-orphan")
    received_contact_invitations = relationship("ContactInvitation", foreign_keys="ContactInvitation.recipient_id", back_populates="recipient")
    contact_groups = relationship("ContactGroup", back_populates="user", cascade="all, delete-orphan")
    
    # Biometric authentication relationships
    devices = relationship("UserDevice", back_populates="user", cascade="all, delete-orphan")
    biometric_auths = relationship("BiometricAuth", back_populates="user", cascade="all, delete-orphan")
    biometric_attempts = relationship("BiometricAuthAttempt", back_populates="user", cascade="all, delete-orphan")
    biometric_tokens = relationship("BiometricToken", back_populates="user", cascade="all, delete-orphan")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_user_email', 'email'),  # Already exists but explicit
        Index('idx_user_username', 'username'),  # Already exists but explicit
        Index('idx_user_city', 'city'),
        Index('idx_user_country', 'country'),
        Index('idx_user_timezone', 'timezone'),
        Index('idx_user_is_verified', 'is_verified'),
        Index('idx_user_is_active', 'is_active'),
        Index('idx_user_is_deleted', 'is_deleted'),
        Index('idx_user_created_at', 'created_at'),
        Index('idx_user_updated_at', 'updated_at'),
        Index('idx_user_stripe_customer_id', 'stripe_customer_id'),
        Index('idx_user_otp_expires_at', 'otp_expires_at'),
        Index('idx_user_signup_method', 'signup_method'),
        # Combined indexes for common queries
        Index('idx_user_city_country', 'city', 'country'),
        Index('idx_user_active_verified', 'is_active', 'is_verified'),
        Index('idx_user_created_active', 'created_at', 'is_active'),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', full_name='{self.full_name}')>"
    
    @property
    def display_name(self):
        """Get display name (username or full name)"""
        return self.username or self.full_name
    
    def is_friend_with(self, user_id: int) -> bool:
        """Check if this user is friends with another user"""
        return any(friend.id == user_id for friend in self.friends)

class UserProfile(Base, IDMixin, TimestampMixin):
    """Extended user profile information"""
    __tablename__ = "user_profiles"
    
    user_id = Column(ForeignKey("users.id"), unique=True, nullable=False)
    
    # Extended profile fields
    occupation = Column(String(100), nullable=True)
    company = Column(String(100), nullable=True)
    website = Column(String(255), nullable=True)
    
    # Social media links
    instagram_handle = Column(String(100), nullable=True)
    twitter_handle = Column(String(100), nullable=True)
    linkedin_url = Column(String(255), nullable=True)
    
    # Event planning preferences
    favorite_event_types = Column(Text, nullable=True)  # JSON string
    planning_style = Column(String(50), nullable=True)  # detailed, casual, etc.
    budget_range = Column(String(50), nullable=True)  # low, medium, high
    
    # Relationship
    user = relationship("User", back_populates="profile")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_userprofile_user_id', 'user_id'),
        Index('idx_userprofile_occupation', 'occupation'),
        Index('idx_userprofile_company', 'company'),
        Index('idx_userprofile_planning_style', 'planning_style'),
        Index('idx_userprofile_budget_range', 'budget_range'),
        Index('idx_userprofile_created_at', 'created_at'),
        # Combined indexes for common queries
        Index('idx_userprofile_occupation_company', 'occupation', 'company'),
        Index('idx_userprofile_style_budget', 'planning_style', 'budget_range'),
    )
    
    def __repr__(self):
        return f"<UserProfile(user_id={self.user_id}, occupation='{self.occupation}')>"

class UserSession(Base, IDMixin, TimestampMixin):
    """User session tracking"""
    __tablename__ = "user_sessions"
    
    user_id = Column(ForeignKey("users.id"), nullable=False)
    session_token = Column(String(255), unique=True, nullable=False)
    refresh_token = Column(String(255), unique=True, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Session metadata
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    device_info = Column(Text, nullable=True)
    
    # Relationship
    user = relationship("User", back_populates="sessions")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_usersession_user_id', 'user_id'),
        Index('idx_usersession_session_token', 'session_token'),
        Index('idx_usersession_refresh_token', 'refresh_token'),
        Index('idx_usersession_expires_at', 'expires_at'),
        Index('idx_usersession_is_active', 'is_active'),
        Index('idx_usersession_created_at', 'created_at'),
        Index('idx_usersession_ip_address', 'ip_address'),
        # Combined indexes for common queries
        Index('idx_usersession_user_active', 'user_id', 'is_active'),
        Index('idx_usersession_active_expires', 'is_active', 'expires_at'),
        Index('idx_usersession_user_expires', 'user_id', 'expires_at'),
    )
    
    def __repr__(self):
        return f"<UserSession(user_id={self.user_id}, expires_at='{self.expires_at}')>"