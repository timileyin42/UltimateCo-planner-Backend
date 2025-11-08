from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
from app.models.event_models import Event

from app.core.deps import get_db, get_current_active_user
from app.core.rate_limiter import create_rate_limit_decorator, RateLimitConfig
from app.models.user_models import User
from app.services.ai_service import ai_service
from app.models.event_models import Event
from app.models.ai_chat_models import AIChatSession, AIChatMessage

from app.schemas.chat import (
    ChatSessionCreate, 
    ChatSessionResponse, 
    ChatMessageCreate, 
    ChatMessageResponse,
    EventCreationResult
)

ai_chat_router = APIRouter(prefix="/ai-chat", tags=["AI Chat"])

# Rate limiting decorators for AI endpoints
rate_limit_ai_chat = create_rate_limit_decorator(RateLimitConfig.AI_CHAT)
rate_limit_ai_analysis = create_rate_limit_decorator(RateLimitConfig.AI_ANALYSIS)

@ai_chat_router.post("/sessions", response_model=ChatSessionResponse)
@rate_limit_ai_chat
async def create_chat_session(
    request: Request,
    session_data: ChatSessionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new AI chat session for general event planning assistance.
    
    The AI can help with:
    - Event creation and planning
    - Budget management
    - Vendor recommendations
    - Timeline creation
    - General event planning advice
    - And much more!
    """
    try:
        # Get user's events to provide context to AI
        user_events = db.query(Event).filter(
            Event.creator_id == current_user.id,
            Event.is_active == True
        ).limit(10).all()
        
        # Add user events to context if not already provided
        if not session_data.context:
            session_data.context = {}
        
        session_data.context['user_events'] = [
            {
                'id': event.id,
                'title': event.title,
                'type': event.event_type,
                'date': event.start_datetime.isoformat() if event.start_datetime else None,
                'location': event.venue_name
            }
            for event in user_events
        ]
        
        return await ai_service.create_chat_session(db, current_user.id, session_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create chat session: {str(e)}"
        )

@ai_chat_router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a chat session with all messages."""
    try:
        return await ai_service.get_chat_session(db, session_id, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get chat session: {str(e)}"
        )

@ai_chat_router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
@rate_limit_ai_chat
async def send_chat_message(
    request: Request,
    session_id: str,
    message_data: ChatMessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Send a message in an existing chat session."""
    try:
        return await ai_service.send_chat_message(db, session_id, current_user.id, message_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )

@ai_chat_router.post("/sessions/{session_id}/complete", response_model=EventCreationResult)
@rate_limit_ai_analysis
async def complete_chat_session(
    request: Request,
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Complete a chat session and create the event."""
    try:
        result = await ai_service.complete_chat_session(db, session_id, current_user.id)
        return EventCreationResult(
            event_id=result["event_id"],
            session_id=result["session_id"],
            success=result["success"],
            message=result["message"]
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete chat session: {str(e)}"
        )

@ai_chat_router.get("/sessions", response_model=List[ChatSessionResponse])
async def get_user_chat_sessions(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all chat sessions for the current user."""
    try:        
        sessions = db.query(AIChatSession).filter(
            AIChatSession.user_id == current_user.id
        ).order_by(AIChatSession.updated_at.desc()).all()
        
        result = []
        for session in sessions:
            messages = db.query(AIChatMessage).filter(
                AIChatMessage.session_id == session.id
            ).order_by(AIChatMessage.created_at).all()
            
            result.append(ChatSessionResponse(
                id=session.session_id,
                user_id=current_user.id,
                status=session.status,
                messages=[ai_service._message_to_schema(msg) for msg in messages],
                event_data=session.event_data,
                created_at=session.created_at,
                updated_at=session.updated_at,
                completed_at=session.completed_at
            ))
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get chat sessions: {str(e)}"
        )

@ai_chat_router.get("/suggested-prompts")
async def get_suggested_prompts(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get suggested prompts/questions users can ask the AI assistant.
    These help users discover what the AI can do.
    """
    try:
        
        # Check if user has events
        has_events = db.query(Event).filter(
            Event.creator_id == current_user.id
        ).count() > 0
        
        # Category-based suggested prompts
        suggestions = {
            "event_creation": {
                "title": "Create Events",
                "icon": "🎉",
                "prompts": [
                    "Help me plan a birthday party",
                    "I want to create a wedding event",
                    "Set up a corporate meeting for next week",
                    "Plan a surprise anniversary celebration",
                    "Create a baby shower event"
                ]
            },
            "budget_planning": {
                "title": "Budget & Finance",
                "icon": "",
                "prompts": [
                    "How much should I budget for a wedding?",
                    "Help me optimize my event budget",
                    "What are typical costs for a corporate event?",
                    "Create a budget breakdown for my party",
                    "How can I save money on my event?"
                ]
            },
            "vendor_selection": {
                "title": "Vendors & Services",
                "icon": "🎪",
                "prompts": [
                    "Recommend caterers for my event",
                    "What vendors do I need for a wedding?",
                    "Help me find a photographer",
                    "Suggest decoration companies",
                    "What questions should I ask vendors?"
                ]
            },
            "timeline_planning": {
                "title": "Timeline & Schedule",
                "icon": "📅",
                "prompts": [
                    "Create a timeline for my wedding day",
                    "What's a typical event schedule?",
                    "Help me plan my event timeline",
                    "When should I start planning my event?",
                    "Create a preparation checklist"
                ]
            },
            "guest_management": {
                "title": "Guests & Invitations",
                "icon": "👥",
                "prompts": [
                    "How do I manage RSVPs?",
                    "When should I send invitations?",
                    "Help me create a guest list",
                    "What information should be on invitations?",
                    "How to handle plus ones?"
                ]
            },
            "tips_advice": {
                "title": "Tips & Advice",
                "icon": "💡",
                "prompts": [
                    "What are common event planning mistakes?",
                    "Give me tips for a successful party",
                    "How to choose the perfect venue?",
                    "What should I do day-of the event?",
                    "Emergency backup plans for outdoor events"
                ]
            }
        }
        
        # Add context-specific suggestions if user has events
        if has_events:
            suggestions["my_events"] = {
                "title": "My Events",
                "icon": "📋",
                "prompts": [
                    "Show me my upcoming events",
                    "Help me with my next event",
                    "What tasks are pending for my events?",
                    "Suggest improvements for my event",
                    "Help me plan my event budget"
                ]
            }
        
        return {
            "suggestions": suggestions,
            "general_examples": [
                "What can you help me with?",
                "I need event planning advice",
                "How do I get started?",
                "Tell me about event types you can help with"
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get suggested prompts: {str(e)}"
        )