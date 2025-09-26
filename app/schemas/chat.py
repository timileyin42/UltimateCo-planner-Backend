from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum

class ChatMessageRole(str, Enum):
    """Chat message roles"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class ChatSessionStatus(str, Enum):
    """Chat session status"""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ChatMessage(BaseModel):
    """Individual chat message"""
    role: ChatMessageRole
    content: str = Field(..., min_length=1, max_length=2000)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(from_attributes=True)

class ChatSessionCreate(BaseModel):
    """Schema for creating a new chat session"""
    initial_message: str = Field(..., min_length=1, max_length=2000, description="Initial user message to start the conversation")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context for the chat session")

class ChatMessageCreate(BaseModel):
    """Schema for creating a new chat message"""
    content: str = Field(..., min_length=1, max_length=2000)
    
class ChatSessionResponse(BaseModel):
    """Chat session response"""
    id: str
    user_id: int
    status: ChatSessionStatus
    messages: List[ChatMessage]
    event_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class ChatMessageResponse(BaseModel):
    """Chat message response"""
    session_id: str
    message: ChatMessage
    suggestions: Optional[List[str]] = None
    event_preview: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(from_attributes=True)

class EventCreationResult(BaseModel):
    """Result of event creation from chat"""
    event_id: int
    session_id: str
    success: bool
    message: str
    
    model_config = ConfigDict(from_attributes=True)