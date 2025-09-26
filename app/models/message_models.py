from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List
from app.models.shared_models import BaseModel, TimestampMixin
import enum

class MessageType(str, enum.Enum):
    """Types of messages in the system."""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    SYSTEM = "system"
    POLL_UPDATE = "poll_update"
    TASK_UPDATE = "task_update"
    EXPENSE_UPDATE = "expense_update"
    RSVP_UPDATE = "rsvp_update"

class MessageStatus(str, enum.Enum):
    """Message delivery status."""
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"

class Message(BaseModel, TimestampMixin):
    """Messages in event conversations."""
    __tablename__ = "messages"
    
    # Basic message info
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[MessageType] = mapped_column(SQLEnum(MessageType), default=MessageType.TEXT)
    status: Mapped[MessageStatus] = mapped_column(SQLEnum(MessageStatus), default=MessageStatus.SENT)
    
    # Relationships
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reply_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("messages.id"), nullable=True)
    
    # Optional file/media info
    file_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    file_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Message metadata
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    edited_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    pinned_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    # System message data (JSON for flexibility)
    system_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    
    # Relationships
    event = relationship("Event", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    reply_to = relationship("Message", remote_side="Message.id", back_populates="replies")
    replies = relationship("Message", back_populates="reply_to", cascade="all, delete-orphan")
    pinned_by = relationship("User", foreign_keys=[pinned_by_id])
    
    # Message reactions and read receipts
    reactions = relationship("MessageReaction", back_populates="message", cascade="all, delete-orphan")
    read_receipts = relationship("MessageReadReceipt", back_populates="message", cascade="all, delete-orphan")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_message_event_id', 'event_id'),
        Index('idx_message_sender_id', 'sender_id'),
        Index('idx_message_reply_to_id', 'reply_to_id'),
        Index('idx_message_message_type', 'message_type'),
        Index('idx_message_status', 'status'),
        Index('idx_message_is_edited', 'is_edited'),
        Index('idx_message_is_pinned', 'is_pinned'),
        Index('idx_message_pinned_by_id', 'pinned_by_id'),
        Index('idx_message_created_at', 'created_at'),
        Index('idx_message_edited_at', 'edited_at'),
        Index('idx_message_pinned_at', 'pinned_at'),
        # Combined indexes for common queries
        Index('idx_message_event_created', 'event_id', 'created_at'),
        Index('idx_message_sender_created', 'sender_id', 'created_at'),
        Index('idx_message_event_type', 'event_id', 'message_type'),
        Index('idx_message_event_pinned', 'event_id', 'is_pinned'),
        Index('idx_message_reply_created', 'reply_to_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Message(id={self.id}, event_id={self.event_id}, sender_id={self.sender_id}, type={self.message_type})>"
    
    @property
    def is_system_message(self) -> bool:
        """Check if this is a system-generated message."""
        return self.message_type == MessageType.SYSTEM
    
    @property
    def has_file(self) -> bool:
        """Check if message has an attached file."""
        return self.file_url is not None
    
    @property
    def reply_count(self) -> int:
        """Get number of replies to this message."""
        return len(self.replies) if self.replies else 0

class MessageReaction(BaseModel, TimestampMixin):
    """Reactions to messages (emojis, likes, etc.)."""
    __tablename__ = "message_reactions"
    
    # Reaction info
    emoji: Mapped[str] = mapped_column(String(10), nullable=False)  # Unicode emoji
    
    # Relationships
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    message = relationship("Message", back_populates="reactions")
    user = relationship("User", back_populates="message_reactions")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_messagereaction_message_id', 'message_id'),
        Index('idx_messagereaction_user_id', 'user_id'),
        Index('idx_messagereaction_emoji', 'emoji'),
        Index('idx_messagereaction_created_at', 'created_at'),
        # Combined indexes for common queries
        Index('idx_messagereaction_message_user', 'message_id', 'user_id'),
        Index('idx_messagereaction_message_emoji', 'message_id', 'emoji'),
        Index('idx_messagereaction_user_emoji', 'user_id', 'emoji'),
    )
    
    def __repr__(self):
        return f"<MessageReaction(id={self.id}, message_id={self.message_id}, user_id={self.user_id}, emoji={self.emoji})>"

class MessageReadReceipt(BaseModel, TimestampMixin):
    """Track when users read messages."""
    __tablename__ = "message_read_receipts"
    
    # Read info
    read_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    
    # Relationships
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    message = relationship("Message", back_populates="read_receipts")
    user = relationship("User", back_populates="message_read_receipts")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_messagereadreceipt_message_id', 'message_id'),
        Index('idx_messagereadreceipt_user_id', 'user_id'),
        Index('idx_messagereadreceipt_read_at', 'read_at'),
        Index('idx_messagereadreceipt_created_at', 'created_at'),
        # Combined indexes for common queries
        Index('idx_messagereadreceipt_message_user', 'message_id', 'user_id'),
        Index('idx_messagereadreceipt_user_read', 'user_id', 'read_at'),
        Index('idx_messagereadreceipt_message_read', 'message_id', 'read_at'),
    )
    
    def __repr__(self):
        return f"<MessageReadReceipt(id={self.id}, message_id={self.message_id}, user_id={self.user_id})>"

class EventChatSettings(BaseModel, TimestampMixin):
    """Chat settings for events."""
    __tablename__ = "event_chat_settings"
    
    # Chat settings
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_file_uploads: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_reactions: Mapped[bool] = mapped_column(Boolean, default=True)
    max_file_size_mb: Mapped[int] = mapped_column(Integer, default=10)
    allowed_file_types: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    
    # Moderation settings
    require_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_delete_after_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Notification settings
    notify_on_new_message: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_mention: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False, unique=True)
    
    # Relationships
    event = relationship("Event", back_populates="chat_settings")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_eventchatsettings_event_id', 'event_id'),
        Index('idx_eventchatsettings_is_enabled', 'is_enabled'),
        Index('idx_eventchatsettings_allow_file_uploads', 'allow_file_uploads'),
        Index('idx_eventchatsettings_allow_reactions', 'allow_reactions'),
        Index('idx_eventchatsettings_require_approval', 'require_approval'),
        Index('idx_eventchatsettings_notify_new_message', 'notify_on_new_message'),
        Index('idx_eventchatsettings_notify_mention', 'notify_on_mention'),
        Index('idx_eventchatsettings_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<EventChatSettings(id={self.id}, event_id={self.event_id}, enabled={self.is_enabled})>"

class MessageMention(BaseModel, TimestampMixin):
    """User mentions in messages."""
    __tablename__ = "message_mentions"
    
    # Mention info
    start_index: Mapped[int] = mapped_column(Integer, nullable=False)  # Start position in message
    end_index: Mapped[int] = mapped_column(Integer, nullable=False)    # End position in message
    
    # Relationships
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), nullable=False)
    mentioned_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    message = relationship("Message")
    mentioned_user = relationship("User", back_populates="message_mentions")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_messagemention_message_id', 'message_id'),
        Index('idx_messagemention_mentioned_user_id', 'mentioned_user_id'),
        Index('idx_messagemention_start_index', 'start_index'),
        Index('idx_messagemention_end_index', 'end_index'),
        Index('idx_messagemention_created_at', 'created_at'),
        # Combined indexes for common queries
        Index('idx_messagemention_message_user', 'message_id', 'mentioned_user_id'),
        Index('idx_messagemention_user_created', 'mentioned_user_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<MessageMention(id={self.id}, message_id={self.message_id}, user_id={self.mentioned_user_id})>"

class ChatParticipant(BaseModel, TimestampMixin):
    """Track chat participants and their settings."""
    __tablename__ = "chat_participants"
    
    # Participant settings
    is_muted: Mapped[bool] = mapped_column(Boolean, default=False)
    muted_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_read_message_id: Mapped[Optional[int]] = mapped_column(ForeignKey("messages.id"), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Notification preferences
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    push_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    event = relationship("Event")
    user = relationship("User", back_populates="chat_participations")
    last_read_message = relationship("Message")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_chatparticipant_event_id', 'event_id'),
        Index('idx_chatparticipant_user_id', 'user_id'),
        Index('idx_chatparticipant_is_muted', 'is_muted'),
        Index('idx_chatparticipant_muted_until', 'muted_until'),
        Index('idx_chatparticipant_last_read_message_id', 'last_read_message_id'),
        Index('idx_chatparticipant_last_seen_at', 'last_seen_at'),
        Index('idx_chatparticipant_email_notifications', 'email_notifications'),
        Index('idx_chatparticipant_push_notifications', 'push_notifications'),
        Index('idx_chatparticipant_created_at', 'created_at'),
        # Combined indexes for common queries
        Index('idx_chatparticipant_event_user', 'event_id', 'user_id'),
        Index('idx_chatparticipant_user_last_seen', 'user_id', 'last_seen_at'),
        Index('idx_chatparticipant_event_muted', 'event_id', 'is_muted'),
    )
    
    def __repr__(self):
        return f"<ChatParticipant(id={self.id}, event_id={self.event_id}, user_id={self.user_id})>"