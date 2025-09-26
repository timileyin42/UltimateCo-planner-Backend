from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from app.core.deps import get_db, get_current_active_user
from app.core.errors import http_400_bad_request, http_404_not_found
from app.core.rate_limiter import create_rate_limit_decorator, RateLimitConfig
from app.services.ai_service import ai_service
from app.services.event_service import EventService
from app.models.user_models import User
from pydantic import BaseModel, Field

ai_router = APIRouter()

# Rate limiting decorators for AI endpoints
rate_limit_ai_analysis = create_rate_limit_decorator(RateLimitConfig.AI_ANALYSIS)

# Pydantic models for AI requests
class ChecklistRequest(BaseModel):
    event_id: int
    budget: Optional[float] = None

class VendorRequest(BaseModel):
    event_id: int
    category: str = Field(..., description="Vendor category (catering, venue, entertainment, etc.)")
    location: Optional[str] = None

class MenuRequest(BaseModel):
    event_id: int
    dietary_restrictions: List[str] = []
    budget_per_person: Optional[float] = None

class BudgetOptimizationRequest(BaseModel):
    event_id: int
    target_budget: float

class TimelineRequest(BaseModel):
    event_id: int
    include_tasks: bool = True

class GiftSuggestionRequest(BaseModel):
    event_id: int
    recipient_info: Dict[str, Any]
    budget_range: Optional[str] = None

class WeatherCheckRequest(BaseModel):
    event_id: int
    location: str

@ai_router.post("/checklist")
@rate_limit_ai_analysis
async def generate_event_checklist(
    request: ChecklistRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Generate AI-powered checklist for an event"""
    try:
        event_service = EventService(db)
        event = event_service.get_event_by_id(request.event_id, current_user.id)
        
        if not event:
            raise http_404_not_found("Event not found")
        
        checklist = await ai_service.generate_event_checklist(event, request.budget)
        
        return {
            "event_id": request.event_id,
            "checklist": checklist,
            "generated_at": "2024-01-01T00:00:00Z",
            "budget_considered": request.budget
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request("Failed to generate checklist")

@ai_router.post("/vendors")
@rate_limit_ai_analysis
async def suggest_vendors(
    request: VendorRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get AI-powered vendor suggestions"""
    try:
        event_service = EventService(db)
        event = event_service.get_event_by_id(request.event_id, current_user.id)
        
        if not event:
            raise http_404_not_found("Event not found")
        
        vendors = await ai_service.suggest_vendors(event, request.category, request.location)
        
        return {
            "event_id": request.event_id,
            "category": request.category,
            "location": request.location,
            "vendors": vendors,
            "generated_at": "2024-01-01T00:00:00Z"
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request("Failed to suggest vendors")

@ai_router.post("/menu")
@rate_limit_ai_analysis
async def generate_menu_suggestions(
    request: MenuRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Generate AI-powered menu suggestions"""
    try:
        event_service = EventService(db)
        event = event_service.get_event_by_id(request.event_id, current_user.id)
        
        if not event:
            raise http_404_not_found("Event not found")
        
        menu = await ai_service.generate_menu_suggestions(
            event, 
            request.dietary_restrictions, 
            request.budget_per_person
        )
        
        return {
            "event_id": request.event_id,
            "menu": menu,
            "dietary_restrictions": request.dietary_restrictions,
            "budget_per_person": request.budget_per_person,
            "generated_at": "2024-01-01T00:00:00Z"
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request("Failed to generate menu suggestions")

@ai_router.post("/budget-optimization")
@rate_limit_ai_analysis
async def optimize_budget(
    request: BudgetOptimizationRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get AI-powered budget optimization suggestions"""
    try:
        event_service = EventService(db)
        event = event_service.get_event_by_id(request.event_id, current_user.id)
        
        if not event:
            raise http_404_not_found("Event not found")
        
        # Get current expenses
        expenses = event_service.get_event_expenses(request.event_id, current_user.id)
        expense_data = [
            {
                "title": exp.title,
                "amount": exp.amount,
                "category": exp.category,
                "description": exp.description
            }
            for exp in expenses
        ]
        
        optimization = await ai_service.optimize_budget(event, expense_data, request.target_budget)
        
        return {
            "event_id": request.event_id,
            "optimization": optimization,
            "target_budget": request.target_budget,
            "generated_at": "2024-01-01T00:00:00Z"
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request("Failed to optimize budget")

@ai_router.post("/timeline")
@rate_limit_ai_analysis
async def generate_event_timeline(
    request: TimelineRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Generate AI-powered event timeline"""
    try:
        event_service = EventService(db)
        event = event_service.get_event_by_id(request.event_id, current_user.id)
        
        if not event:
            raise http_404_not_found("Event not found")
        
        tasks = None
        if request.include_tasks:
            event_tasks = event_service.get_event_tasks(request.event_id, current_user.id)
            tasks = [
                {
                    "title": task.title,
                    "description": task.description,
                    "category": task.category,
                    "priority": task.priority,
                    "due_date": task.due_date.isoformat() if task.due_date else None
                }
                for task in event_tasks
            ]
        
        timeline = await ai_service.generate_event_timeline(event, tasks)
        
        return {
            "event_id": request.event_id,
            "timeline": timeline,
            "includes_tasks": request.include_tasks,
            "generated_at": "2024-01-01T00:00:00Z"
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request("Failed to generate timeline")

@ai_router.post("/gift-ideas")
@rate_limit_ai_analysis
async def suggest_gift_ideas(
    request: GiftSuggestionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Generate AI-powered gift suggestions"""
    try:
        event_service = EventService(db)
        event = event_service.get_event_by_id(request.event_id, current_user.id)
        
        if not event:
            raise http_404_not_found("Event not found")
        
        gift_ideas = await ai_service.suggest_gift_ideas(
            event, 
            request.recipient_info, 
            request.budget_range
        )
        
        return {
            "event_id": request.event_id,
            "gift_ideas": gift_ideas,
            "recipient_info": request.recipient_info,
            "budget_range": request.budget_range,
            "generated_at": "2024-01-01T00:00:00Z"
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request("Failed to suggest gift ideas")

@ai_router.post("/weather-check")
@rate_limit_ai_analysis
async def check_weather_and_backup(
    request: WeatherCheckRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Check weather and get AI-powered backup suggestions"""
    try:
        event_service = EventService(db)
        event = event_service.get_event_by_id(request.event_id, current_user.id)
        
        if not event:
            raise http_404_not_found("Event not found")
        
        weather_analysis = await ai_service.check_weather_and_suggest_backup(
            event, 
            request.location
        )
        
        return {
            "event_id": request.event_id,
            "location": request.location,
            "weather_analysis": weather_analysis,
            "generated_at": "2024-01-01T00:00:00Z"
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request("Failed to check weather")

@ai_router.get("/features")
async def get_ai_features(
    current_user: User = Depends(get_current_active_user)
):
    """Get list of available AI features"""
    return {
        "features": [
            {
                "name": "Event Checklist Generator",
                "description": "Generate comprehensive checklists based on event type and budget",
                "endpoint": "/ai/checklist"
            },
            {
                "name": "Vendor Suggestions",
                "description": "Get AI-powered vendor recommendations for your event",
                "endpoint": "/ai/vendors"
            },
            {
                "name": "Menu Planning",
                "description": "Generate menu suggestions considering dietary restrictions and budget",
                "endpoint": "/ai/menu"
            },
            {
                "name": "Budget Optimization",
                "description": "Analyze expenses and get cost-saving suggestions",
                "endpoint": "/ai/budget-optimization"
            },
            {
                "name": "Event Timeline",
                "description": "Generate detailed run-of-show for your event",
                "endpoint": "/ai/timeline"
            },
            {
                "name": "Gift Ideas",
                "description": "Get personalized gift suggestions based on recipient and occasion",
                "endpoint": "/ai/gift-ideas"
            },
            {
                "name": "Weather & Backup Plans",
                "description": "Check weather forecast and get backup plan suggestions",
                "endpoint": "/ai/weather-check"
            }
        ],
        "ai_provider": "OpenAI GPT-4",
        "features_enabled": True
    }