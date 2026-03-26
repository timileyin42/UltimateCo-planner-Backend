from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Body, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.rate_limiter import create_rate_limit_decorator, RateLimitConfig
from app.services.tool_chat_service import (
    DEFAULT_TOOL_CHAT_SYSTEM_PROMPT,
    ToolChatIntakeAnswers,
    ToolChatPreflightState,
    VenueShortlistResponse,
    VenueShortlistSearchContext,
    tool_chat_runner,
)

tool_chat_dev_router = APIRouter(prefix="/tool-chat-dev", tags=["tool-chat-dev"])

rate_limit_tool_chat_dev = create_rate_limit_decorator(RateLimitConfig.AI_CHAT)


class ToolChatDevRequest(BaseModel):
    user_message: str = Field(..., min_length=1)
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    preflight_answers: Optional[ToolChatIntakeAnswers] = None
    model: Optional[str] = None
    system_prompt: str = Field(default=DEFAULT_TOOL_CHAT_SYSTEM_PROMPT)
    tool_choice: Literal["auto", "none", "required"] = "auto"
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tool_rounds: int = Field(default=8, ge=1, le=20)


class ToolChatDevResponse(BaseModel):
    assistant_message: Optional[Dict[str, Any]] = None
    assistant_messages: List[Dict[str, Any]] = Field(default_factory=list)
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    tool_trace: List[Dict[str, Any]] = Field(default_factory=list)
    max_tool_rounds_reached: bool = False
    warning: Optional[str] = None
    preflight: Optional[ToolChatPreflightState] = None
    venue_shortlist: Optional[VenueShortlistResponse] = None


class VenueMoreRequest(BaseModel):
    search_context: VenueShortlistSearchContext
    page_token: Optional[str] = None


class VenueMoreResponse(BaseModel):
    venue_shortlist: VenueShortlistResponse


@tool_chat_dev_router.post("/message", response_model=ToolChatDevResponse)
@rate_limit_tool_chat_dev
async def send_tool_chat_dev_message(
    request: Request,
    payload: ToolChatDevRequest = Body(...),
):
    """Run one tool-chat turn against the local planning tool registry."""
    try:
        result = await tool_chat_runner.run_turn(
            user_prompt=payload.user_message,
            messages=payload.messages,
            preflight_answers=payload.preflight_answers,
            model=payload.model,
            system_prompt=payload.system_prompt,
            tool_choice=payload.tool_choice,
            temperature=payload.temperature,
            max_tool_rounds=payload.max_tool_rounds,
        )
        return ToolChatDevResponse(**result)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process tool chat request: {exc}",
        ) from exc


@tool_chat_dev_router.post("/venues/more", response_model=VenueMoreResponse)
@rate_limit_tool_chat_dev
async def load_more_tool_chat_dev_venues(
    request: Request,
    payload: VenueMoreRequest = Body(...),
):
    """Load the next venue page directly from Google Places without another LLM round."""
    try:
        shortlist = await tool_chat_runner.load_more_venues(
            search_context=payload.search_context,
            page_token=payload.page_token,
        )
        return VenueMoreResponse(venue_shortlist=VenueShortlistResponse(**shortlist))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load more venue options: {exc}",
        ) from exc


@tool_chat_dev_router.get("/config")
async def get_tool_chat_dev_config():
    return {
        "default_model": tool_chat_runner.default_model,
        "default_system_prompt": DEFAULT_TOOL_CHAT_SYSTEM_PROMPT,
        "tools": tool_chat_runner.build_tools_payload(),
    }
