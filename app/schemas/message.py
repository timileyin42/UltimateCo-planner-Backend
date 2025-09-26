from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.message_models import MessageType, MessageStatus

# Base message schemas
class MessageBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000, description="Message content")
    message_type: MessageType = Field(default=MessageType.TEXT, description="Type of message")
    reply_to_id: Optional[int] = Field(None, description="ID of message being replied to")

class MessageCreate(MessageBase):
    """Schema for creating a new message."""
    pass

class MessageUpdate(BaseModel):
    """Schema for updating a message."""
    content: str = Field(..., min_length=1, max_length=5000, description="Updated message content")

class MessageFileUpload(BaseModel):
    """Schema for file upload with message."""
    content: Optional[str] = Field(None, max_length=1000, description="Optional message with file")
    file_name: str = Field(..., description="Name of uploaded file")
    file_size: int = Field(..., gt=0, description="Size of file in bytes")
    file_type: str = Field(..., description="MIME type of file")
    file_url: str = Field(..., description="URL of uploaded file")

# Response schemas
class UserBasic(BaseModel):
    """Basic user info for message responses."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    full_name: str
    username: Optional[str] = None
    avatar_url: Optional[str] = None

class MessageReactionResponse(BaseModel):
    """Schema for message reaction response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    emoji: str
    user: UserBasic
    created_at: datetime

class MessageResponse(BaseModel):
    """Schema for message response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    content: str
    message_type: MessageType
    status: MessageStatus
    event_id: int
    sender: UserBasic
    reply_to_id: Optional[int] = None
    
    # File info
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    
    # Message metadata
    is_edited: bool
    edited_at: Optional[datetime] = None
    is_pinned: bool
    pinned_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    
    # Reactions and replies
    reactions: List[MessageReactionResponse] = []
    reply_count: int = 0
    
    # Read status for current user
    is_read: Optional[bool] = None

class MessageWithReplies(MessageResponse):
    """Message response with replies included."""
    replies: List[MessageResponse] = []

class MessageListResponse(BaseModel):
    """Schema for paginated message list."""
    messages: List[MessageResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool

# Reaction schemas
class MessageReactionCreate(BaseModel):
    """Schema for creating a message reaction."""
    emoji: str = Field(..., min_length=1, max_length=10, description="Emoji reaction")

class MessageReactionUpdate(BaseModel):
    """Schema for updating a message reaction."""
    emoji: str = Field(..., min_length=1, max_length=10, description="Updated emoji reaction")

# Read receipt schemas
class MessageReadReceiptResponse(BaseModel):
    """Schema for message read receipt response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user: UserBasic
    read_at: datetime

class MessageReadStatus(BaseModel):
    """Schema for message read status."""
    message_id: int
    read_receipts: List[MessageReadReceiptResponse]
    total_readers: int
    total_participants: int

# Chat settings schemas
class EventChatSettingsBase(BaseModel):
    """Base schema for event chat settings."""
    is_enabled: bool = Field(default=True, description="Whether chat is enabled")
    allow_file_uploads: bool = Field(default=True, description="Allow file uploads")
    allow_reactions: bool = Field(default=True, description="Allow message reactions")
    max_file_size_mb: int = Field(default=10, ge=1, le=100, description="Max file size in MB")
    allowed_file_types: Optional[List[str]] = Field(None, description="Allowed file types")
    require_approval: bool = Field(default=False, description="Require message approval")
    auto_delete_after_days: Optional[int] = Field(None, ge=1, le=365, description="Auto-delete messages after days")
    notify_on_new_message: bool = Field(default=True, description="Notify on new messages")
    notify_on_mention: bool = Field(default=True, description="Notify on mentions")

class EventChatSettingsCreate(EventChatSettingsBase):
    """Schema for creating event chat settings."""
    pass

class EventChatSettingsUpdate(EventChatSettingsBase):
    """Schema for updating event chat settings."""
    pass

class EventChatSettingsResponse(EventChatSettingsBase):
    """Schema for event chat settings response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    event_id: int
    created_at: datetime
    updated_at: datetime

# Chat participant schemas
class ChatParticipantBase(BaseModel):
    """Base schema for chat participant."""
    is_muted: bool = Field(default=False, description="Whether chat is muted")
    muted_until: Optional[datetime] = Field(None, description="Mute until timestamp")
    email_notifications: bool = Field(default=True, description="Email notifications enabled")
    push_notifications: bool = Field(default=True, description="Push notifications enabled")

class ChatParticipantUpdate(ChatParticipantBase):
    """Schema for updating chat participant settings."""
    pass

class ChatParticipantResponse(ChatParticipantBase):
    """Schema for chat participant response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    event_id: int
    user: UserBasic
    last_seen_at: Optional[datetime] = None
    unread_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime

# Message mention schemas
class MessageMentionCreate(BaseModel):
    """Schema for creating a message mention."""
    user_id: int = Field(..., description="ID of user being mentioned")
    start_index: int = Field(..., ge=0, description="Start position in message")
    end_index: int = Field(..., ge=0, description="End position in message")

class MessageMentionResponse(BaseModel):
    """Schema for message mention response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    mentioned_user: UserBasic
    start_index: int
    end_index: int

# System message schemas
class SystemMessageData(BaseModel):
    """Schema for system message data."""
    action: str = Field(..., description="System action type")
    actor_name: str = Field(..., description="Name of user who performed action")
    target_name: Optional[str] = Field(None, description="Name of target (if applicable)")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")

class SystemMessageCreate(BaseModel):
    """Schema for creating system messages."""
    event_id: int = Field(..., description="Event ID")
    system_data: SystemMessageData = Field(..., description="System message data")

# Search and filter schemas
class MessageSearchParams(BaseModel):
    """Schema for message search parameters."""
    query: Optional[str] = Field(None, min_length=1, description="Search query")
    message_type: Optional[MessageType] = Field(None, description="Filter by message type")
    sender_id: Optional[int] = Field(None, description="Filter by sender")
    date_from: Optional[datetime] = Field(None, description="Filter messages from date")
    date_to: Optional[datetime] = Field(None, description="Filter messages to date")
    has_files: Optional[bool] = Field(None, description="Filter messages with files")
    is_pinned: Optional[bool] = Field(None, description="Filter pinned messages")
    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=50, ge=1, le=100, description="Messages per page")

# Bulk operations
class MessageBulkDelete(BaseModel):
    """Schema for bulk deleting messages."""
    message_ids: List[int] = Field(..., min_items=1, max_items=100, description="List of message IDs to delete")

class MessageBulkMarkRead(BaseModel):
    """Schema for bulk marking messages as read."""
    message_ids: List[int] = Field(..., min_items=1, max_items=100, description="List of message IDs to mark as read")

# Chat statistics
class ChatStatistics(BaseModel):
    """Schema for chat statistics."""
    total_messages: int
    total_participants: int
    active_participants_today: int
    messages_today: int
    most_active_user: Optional[UserBasic] = None
    file_count: int
    reaction_count: int
    average_response_time_minutes: Optional[float] = None

# WebSocket message schemas
class WebSocketMessage(BaseModel):
    """Schema for WebSocket messages."""
    type: str = Field(..., description="Message type")
    event_id: int = Field(..., description="Event ID")
    data: Dict[str, Any] = Field(..., description="Message data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")

class TypingIndicator(BaseModel):
    """Schema for typing indicator."""
    event_id: int = Field(..., description="Event ID")
    user: UserBasic = Field(..., description="User who is typing")
    is_typing: bool = Field(..., description="Whether user is typing")

# Export schemas
class ChatExportRequest(BaseModel):
    """Schema for chat export request."""
    format: str = Field(default="json", description="Export format (json, csv, txt)")
    date_from: Optional[datetime] = Field(None, description="Export from date")
    date_to: Optional[datetime] = Field(None, description="Export to date")
    include_files: bool = Field(default=False, description="Include file attachments")
    include_system_messages: bool = Field(default=True, description="Include system messages")

class ChatExportResponse(BaseModel):
    """Schema for chat export response."""
    export_url: str = Field(..., description="URL to download export")
    expires_at: datetime = Field(..., description="Export expiration time")
    file_size_bytes: int = Field(..., description="Export file size")
    message_count: int = Field(..., description="Number of messages exported")