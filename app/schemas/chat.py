import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.event import TaskCategory

SUPPORTED_CHAT_CURRENCIES = {"USD", "GBP", "NGN"}
SUPPORTED_CHAT_CURRENCY_PATTERN = r"^(USD|GBP|NGN)$"


def _parse_json_like(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value

class ChatMessageRole(str, Enum):
    """Chat message roles"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessageType(str, Enum):
    """Logical message types for UI rendering and trace storage."""
    MESSAGE = "message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    PLAN_UPDATE = "plan_update"


class ChatSessionStatus(str, Enum):
    """Chat session status"""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ChatBudgetItem(BaseModel):
    """Planned budget allocation for a category."""
    category: str = Field(..., min_length=1, max_length=100)
    amount: float = Field(..., ge=0)
    percentage: Optional[float] = Field(None, ge=0, le=100)
    notes: Optional[str] = None
    source: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ChatPlanData(BaseModel):
    """Structured plan snapshot built during the AI workflow."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    event_type: Optional[str] = Field(None, max_length=50)
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    timezone: Optional[str] = None
    venue_name: Optional[str] = None
    venue_address: Optional[str] = None
    venue_city: Optional[str] = None
    venue_country: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    location_input: Optional[str] = None
    is_public: Optional[bool] = None
    max_attendees: Optional[int] = Field(None, ge=1)
    total_budget: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = Field(None, pattern=SUPPORTED_CHAT_CURRENCY_PATTERN)
    budget_breakdown: List[ChatBudgetItem] = Field(default_factory=list)
    task_categories: Optional[List[TaskCategory]] = None
    notes: Optional[str] = None
    source_context: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True, extra="allow")

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)

        if not normalized.get("start_datetime"):
            start_value = normalized.get("start_date") or normalized.get("date")
            if start_value is not None:
                normalized["start_datetime"] = start_value

        if not normalized.get("end_datetime") and normalized.get("end_date") is not None:
            normalized["end_datetime"] = normalized["end_date"]

        if normalized.get("total_budget") is None and normalized.get("budget") is not None:
            normalized["total_budget"] = normalized["budget"]

        if normalized.get("max_attendees") is None and normalized.get("guest_count") is not None:
            normalized["max_attendees"] = normalized["guest_count"]

        if not normalized.get("location_input") and normalized.get("location"):
            normalized["location_input"] = normalized["location"]

        if not normalized.get("venue_address") and normalized.get("location"):
            normalized["venue_address"] = normalized["location"]

        return normalized

    @field_validator("currency", mode="before")
    @classmethod
    def validate_currency(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.upper()
        if normalized not in SUPPORTED_CHAT_CURRENCIES:
            raise ValueError("Currency must be one of USD, GBP, or NGN")
        return normalized


class ChatMessage(BaseModel):
    """Individual chat message"""
    role: ChatMessageRole
    content: str = Field(default="", max_length=20000)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None
    message_type: ChatMessageType = ChatMessageType.MESSAGE
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_arguments: Optional[Dict[str, Any]] = None
    tool_result: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None
    event_preview: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class ChatPersistedMessageCreate(BaseModel):
    """Schema for appending trace or assistant messages to a session."""
    role: ChatMessageRole
    content: str = Field(default="", max_length=20000)
    metadata: Optional[Dict[str, Any]] = None
    message_type: ChatMessageType = ChatMessageType.MESSAGE
    suggestions: Optional[List[str]] = None
    event_preview: Optional[Dict[str, Any]] = None
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_arguments: Optional[Dict[str, Any]] = None
    tool_result: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def validate_content_for_message(self):
        if self.message_type == ChatMessageType.MESSAGE and not self.content.strip():
            raise ValueError("Message content is required for standard chat messages")
        return self


class ChatSessionCreate(BaseModel):
    """Schema for creating a new chat session"""
    initial_message: str = Field(..., min_length=1, max_length=2000, description="Initial user message to start the conversation")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context for the chat session")
    plan_data: Optional[ChatPlanData] = Field(None, description="Optional initial structured plan snapshot")

class ChatMessageCreate(BaseModel):
    """Schema for creating a new chat message"""
    content: str = Field(..., min_length=1, max_length=2000)


class ChatSessionPlanUpdate(BaseModel):
    """Persist an updated structured plan and optional message trace."""
    plan_data: Optional[ChatPlanData] = None
    event_data: Optional[Dict[str, Any]] = None
    llm_metadata: Optional[Dict[str, Any]] = None
    messages: List[ChatPersistedMessageCreate] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ChatSessionResponse(BaseModel):
    """Chat session response"""
    id: str
    user_id: int
    status: ChatSessionStatus
    messages: List[ChatMessage]
    event_data: Optional[Dict[str, Any]] = None
    plan_data: Optional[ChatPlanData] = None
    llm_metadata: Optional[Dict[str, Any]] = None
    created_event_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    @field_validator("event_data", "llm_metadata", mode="before")
    @classmethod
    def parse_json_dict_fields(cls, value: Any) -> Any:
        return _parse_json_like(value)

    @field_validator("plan_data", mode="before")
    @classmethod
    def parse_plan_data(cls, value: Any) -> Any:
        parsed = _parse_json_like(value)
        if parsed is None:
            return None
        return ChatPlanData.model_validate(parsed)

    model_config = ConfigDict(from_attributes=True)

class ChatMessageResponse(BaseModel):
    """Chat message response"""
    session_id: str
    message: ChatMessage
    suggestions: Optional[List[str]] = None
    event_preview: Optional[Dict[str, Any]] = None
    event_data: Optional[Dict[str, Any]] = None
    plan_data: Optional[ChatPlanData] = None

    model_config = ConfigDict(from_attributes=True)

class EventCreationResult(BaseModel):
    """Result of event creation from chat"""
    event_id: int
    session_id: str
    success: bool
    message: str
    
    model_config = ConfigDict(from_attributes=True)
