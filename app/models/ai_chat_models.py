from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLEnum, JSON, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.models.shared_models import BaseModel, TimestampMixin
from app.schemas.chat import ChatSessionStatus, ChatMessageRole
import enum
import uuid

class AIChatSession(BaseModel, TimestampMixin):
    """AI chat sessions for conversational event creation."""
    __tablename__ = "ai_chat_sessions"
    
    # Session identification
    session_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    status: Mapped[ChatSessionStatus] = mapped_column(SQLEnum(ChatSessionStatus), default=ChatSessionStatus.ACTIVE)
    
    # User relationship
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Event creation context
    event_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string for event data being built
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string for additional context
    
    # Session metadata
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="ai_chat_sessions")
    messages = relationship("AIChatMessage", back_populates="session", cascade="all, delete-orphan")
    created_event = relationship("Event")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_ai_chat_session_session_id', 'session_id'),
        Index('idx_ai_chat_session_user_id', 'user_id'),
        Index('idx_ai_chat_session_status', 'status'),
        Index('idx_ai_chat_session_completed_at', 'completed_at'),
        Index('idx_ai_chat_session_created_event_id', 'created_event_id'),
        Index('idx_ai_chat_session_created_at', 'created_at'),
        Index('idx_ai_chat_session_updated_at', 'updated_at'),
        
        # Combined indexes for common queries
        Index('idx_ai_chat_session_user_status', 'user_id', 'status'),
        Index('idx_ai_chat_session_user_created', 'user_id', 'created_at'),
        Index('idx_ai_chat_session_status_created', 'status', 'created_at'),
    )
    
    def __repr__(self):
        return f"<AIChatSession(id={self.id}, session_id={self.session_id}, user_id={self.user_id}, status={self.status})>"

class AIChatMessage(BaseModel, TimestampMixin):
    """Messages in AI chat sessions."""
    __tablename__ = "ai_chat_messages"
    
    # Message content
    role: Mapped[ChatMessageRole] = mapped_column(SQLEnum(ChatMessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Message metadata
    metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string for additional data
    suggestions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of suggestions
    event_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON object for event preview
    
    # Session relationship
    session_id: Mapped[int] = mapped_column(ForeignKey("ai_chat_sessions.id"), nullable=False)
    
    # Relationships
    session = relationship("AIChatSession", back_populates="messages")
    
    # Database indexes
    __table_args__ = (
        # Single field indexes
        Index('idx_ai_chat_message_session_id', 'session_id'),
        Index('idx_ai_chat_message_role', 'role'),
        Index('idx_ai_chat_message_created_at', 'created_at'),
        Index('idx_ai_chat_message_updated_at', 'updated_at'),
        
        # Combined indexes for common queries
        Index('idx_ai_chat_message_session_role', 'session_id', 'role'),
        Index('idx_ai_chat_message_session_created', 'session_id', 'created_at'),
        Index('idx_ai_chat_message_role_created', 'role', 'created_at'),
    )
    
    def __repr__(self):
        return f"<AIChatMessage(id={self.id}, session_id={self.session_id}, role={self.role})>"