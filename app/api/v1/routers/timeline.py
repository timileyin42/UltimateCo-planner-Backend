from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from app.core.deps import get_db, get_current_active_user
from app.core.errors import http_400_bad_request, http_404_not_found, http_403_forbidden
from app.services.timeline_service import TimelineService
from app.schemas.timeline import (
    # Timeline schemas
    EventTimelineCreate, EventTimelineUpdate, EventTimelineResponse, TimelineListResponse,
    
    # Timeline item schemas
    TimelineItemCreate, TimelineItemUpdate, TimelineItemStatusUpdate, TimelineItemResponse,
    
    # Template schemas
    TimelineTemplateCreate, TimelineTemplateUpdate, TimelineTemplateResponse, TimelineTemplateListResponse,
    
    # AI and search schemas
    AITimelineRequest, AITimelineResponse, TimelineSearchParams,
    
    # Statistics and utility schemas
    TimelineStatistics, TimelineReorderRequest, BulkTimelineItemCreate,
    TimelineExportRequest, TimelineExportResponse, TimelineProgress
)
from app.models.user_models import User
from pydantic import BaseModel

timeline_router = APIRouter()

# Timeline CRUD endpoints
@timeline_router.post("/events/{event_id}/timelines", response_model=EventTimelineResponse)
async def create_timeline(
    event_id: int,
    timeline_data: EventTimelineCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new timeline for an event"""
    try:
        timeline_service = TimelineService(db)
        timeline = timeline_service.create_timeline(event_id, current_user.id, timeline_data)
        
        return EventTimelineResponse.model_validate(timeline)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower() or "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to create timeline")

@timeline_router.get("/events/{event_id}/timelines", response_model=TimelineListResponse)
async def get_event_timelines(
    event_id: int,
    search_params: TimelineSearchParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get timelines for an event"""
    try:
        timeline_service = TimelineService(db)
        timelines, total = timeline_service.get_event_timelines(event_id, current_user.id, search_params)
        
        timeline_responses = [EventTimelineResponse.model_validate(tl) for tl in timelines]
        
        return TimelineListResponse(
            timelines=timeline_responses,
            total=total,
            page=search_params.page,
            per_page=search_params.per_page,
            has_next=(search_params.page * search_params.per_page) < total,
            has_prev=search_params.page > 1
        )
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get timelines")

@timeline_router.get("/timelines/{timeline_id}", response_model=EventTimelineResponse)
async def get_timeline(
    timeline_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific timeline by ID"""
    try:
        timeline_service = TimelineService(db)
        timeline = timeline_service.get_timeline(timeline_id, current_user.id)
        
        if not timeline:
            raise http_404_not_found("Timeline not found")
        
        return EventTimelineResponse.model_validate(timeline)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get timeline")

@timeline_router.put("/timelines/{timeline_id}", response_model=EventTimelineResponse)
async def update_timeline(
    timeline_id: int,
    update_data: EventTimelineUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a timeline"""
    try:
        timeline_service = TimelineService(db)
        timeline = timeline_service.update_timeline(timeline_id, current_user.id, update_data)
        
        return EventTimelineResponse.model_validate(timeline)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to update timeline")

@timeline_router.delete("/timelines/{timeline_id}")
async def delete_timeline(
    timeline_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a timeline"""
    try:
        timeline_service = TimelineService(db)
        success = timeline_service.delete_timeline(timeline_id, current_user.id)
        
        return {"message": "Timeline deleted successfully", "success": success}
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to delete timeline")

# Timeline item endpoints
@timeline_router.post("/timelines/{timeline_id}/items", response_model=TimelineItemResponse)
async def add_timeline_item(
    timeline_id: int,
    item_data: TimelineItemCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Add an item to a timeline"""
    try:
        timeline_service = TimelineService(db)
        item = timeline_service.add_timeline_item(timeline_id, current_user.id, item_data)
        
        return TimelineItemResponse.model_validate(item)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to add timeline item")

@timeline_router.put("/timeline-items/{item_id}", response_model=TimelineItemResponse)
async def update_timeline_item(
    item_id: int,
    update_data: TimelineItemUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a timeline item"""
    try:
        timeline_service = TimelineService(db)
        item = timeline_service.update_timeline_item(item_id, current_user.id, update_data)
        
        return TimelineItemResponse.model_validate(item)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to update timeline item")

@timeline_router.patch("/timeline-items/{item_id}/status", response_model=TimelineItemResponse)
async def update_item_status(
    item_id: int,
    status_data: TimelineItemStatusUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update timeline item status and timing"""
    try:
        timeline_service = TimelineService(db)
        item = timeline_service.update_item_status(item_id, current_user.id, status_data)
        
        return TimelineItemResponse.model_validate(item)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to update item status")

@timeline_router.delete("/timeline-items/{item_id}")
async def delete_timeline_item(
    item_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a timeline item"""
    try:
        timeline_service = TimelineService(db)
        success = timeline_service.delete_timeline_item(item_id, current_user.id)
        
        return {"message": "Timeline item deleted successfully", "success": success}
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to delete timeline item")

@timeline_router.post("/timelines/{timeline_id}/reorder")
async def reorder_timeline_items(
    timeline_id: int,
    reorder_data: TimelineReorderRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Reorder timeline items"""
    try:
        timeline_service = TimelineService(db)
        success = timeline_service.reorder_timeline_items(
            timeline_id, current_user.id, reorder_data.item_orders
        )
        
        return {"message": "Timeline items reordered successfully", "success": success}
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to reorder timeline items")

# AI-powered timeline generation
@timeline_router.post("/events/{event_id}/generate-timeline", response_model=EventTimelineResponse)
async def generate_ai_timeline(
    event_id: int,
    ai_request: AITimelineRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Generate a timeline using AI based on event details"""
    try:
        timeline_service = TimelineService(db)
        timeline = await timeline_service.generate_ai_timeline(event_id, current_user.id, ai_request)
        
        return EventTimelineResponse.model_validate(timeline)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to generate AI timeline")

# Template endpoints
@timeline_router.post("/timeline-templates", response_model=TimelineTemplateResponse)
async def create_timeline_template(
    template_data: TimelineTemplateCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a timeline template"""
    try:
        timeline_service = TimelineService(db)
        template = timeline_service.create_template(current_user.id, template_data)
        
        return TimelineTemplateResponse.model_validate(template)
        
    except Exception as e:
        raise http_400_bad_request("Failed to create timeline template")

@timeline_router.post("/events/{event_id}/apply-template/{template_id}", response_model=EventTimelineResponse)
async def apply_timeline_template(
    event_id: int,
    template_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Apply a template to create a new timeline"""
    try:
        timeline_service = TimelineService(db)
        timeline = timeline_service.apply_template(event_id, current_user.id, template_id)
        
        return EventTimelineResponse.model_validate(timeline)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access" in str(e).lower() or "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to apply timeline template")

# Statistics and analytics
@timeline_router.get("/timelines/{timeline_id}/statistics", response_model=TimelineStatistics)
async def get_timeline_statistics(
    timeline_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get statistics for a timeline"""
    try:
        timeline_service = TimelineService(db)
        stats = timeline_service.get_timeline_statistics(timeline_id, current_user.id)
        
        return TimelineStatistics(**stats)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get timeline statistics")

@timeline_router.get("/timelines/{timeline_id}/progress", response_model=TimelineProgress)
async def get_timeline_progress(
    timeline_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get real-time progress of a timeline"""
    try:
        timeline_service = TimelineService(db)
        timeline = timeline_service.get_timeline(timeline_id, current_user.id)
        
        if not timeline:
            raise http_404_not_found("Timeline not found")
        
        # Get current and next items
        from app.models.timeline_models import TimelineStatus
        current_item = None
        next_items = []
        
        for item in timeline.items:
            if item.status == TimelineStatus.IN_PROGRESS:
                current_item = item
            elif item.status == TimelineStatus.PENDING:
                next_items.append(item)
                if len(next_items) >= 3:  # Limit to next 3 items
                    break
        
        # Get statistics
        stats = timeline_service.get_timeline_statistics(timeline_id, current_user.id)
        
        return TimelineProgress(
            timeline_id=timeline_id,
            total_items=stats['total_items'],
            completed_items=stats['completed_items'],
            in_progress_items=stats['in_progress_items'],
            pending_items=stats['pending_items'],
            overdue_items=stats['overdue_items'],
            completion_percentage=stats['completion_percentage'],
            current_item=TimelineItemResponse.model_validate(current_item) if current_item else None,
            next_items=[TimelineItemResponse.model_validate(item) for item in next_items]
        )
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get timeline progress")

# Bulk operations
@timeline_router.post("/timelines/{timeline_id}/bulk-items")
async def bulk_create_timeline_items(
    timeline_id: int,
    bulk_data: BulkTimelineItemCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Bulk create timeline items"""
    try:
        timeline_service = TimelineService(db)
        created_items = []
        
        for item_data in bulk_data.items:
            item = timeline_service.add_timeline_item(timeline_id, current_user.id, item_data)
            created_items.append(TimelineItemResponse.model_validate(item))
        
        return {
            "message": f"Successfully created {len(created_items)} timeline items",
            "items": created_items
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to bulk create timeline items")

# Export functionality
@timeline_router.post("/timelines/{timeline_id}/export", response_model=TimelineExportResponse)
async def export_timeline(
    timeline_id: int,
    export_request: TimelineExportRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Export timeline to various formats"""
    try:
        timeline_service = TimelineService(db)
        timeline = timeline_service.get_timeline(timeline_id, current_user.id)
        
        if not timeline:
            raise http_404_not_found("Timeline not found")
        
        # Generate export (this would typically involve a background task)
        export_url = f"/exports/timeline_{timeline_id}_{export_request.format}"
        
        from datetime import datetime, timedelta
        return TimelineExportResponse(
            export_url=export_url,
            expires_at=datetime.utcnow() + timedelta(hours=24),
            file_size_bytes=1024,  # Mock size
            format=export_request.format
        )
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to export timeline")

# Timeline templates public endpoints
@timeline_router.get("/timeline-templates", response_model=TimelineTemplateListResponse)
async def get_public_timeline_templates(
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get public timeline templates"""
    try:
        from app.models.timeline_models import TimelineTemplate
        
        query = db.query(TimelineTemplate).filter(TimelineTemplate.is_public == True)
        
        if event_type:
            query = query.filter(TimelineTemplate.event_type == event_type)
        
        total = query.count()
        templates = query.order_by(TimelineTemplate.usage_count.desc()).offset(
            (page - 1) * per_page
        ).limit(per_page).all()
        
        template_responses = [TimelineTemplateResponse.model_validate(t) for t in templates]
        
        return TimelineTemplateListResponse(
            templates=template_responses,
            total=total,
            page=page,
            per_page=per_page,
            has_next=(page * per_page) < total,
            has_prev=page > 1
        )
        
    except Exception as e:
        raise http_400_bad_request("Failed to get timeline templates")

# Real-time timeline updates (WebSocket placeholder)
@timeline_router.get("/timelines/{timeline_id}/live-updates")
async def get_live_timeline_updates(
    timeline_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get live timeline updates (WebSocket endpoint placeholder)"""
    try:
        timeline_service = TimelineService(db)
        timeline = timeline_service.get_timeline(timeline_id, current_user.id)
        
        if not timeline:
            raise http_404_not_found("Timeline not found")
        
        # This would typically be a WebSocket endpoint
        return {
            "message": "WebSocket endpoint for live updates",
            "timeline_id": timeline_id,
            "websocket_url": f"/ws/timelines/{timeline_id}"
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get live updates info")

# Timeline validation and conflict detection
@timeline_router.post("/timelines/{timeline_id}/validate")
async def validate_timeline(
    timeline_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Validate timeline for conflicts and issues"""
    try:
        timeline_service = TimelineService(db)
        timeline = timeline_service.get_timeline(timeline_id, current_user.id)
        
        if not timeline:
            raise http_404_not_found("Timeline not found")
        
        # Perform validation checks
        conflicts = []
        warnings = []
        
        # Check for overlapping items
        items = sorted(timeline.items, key=lambda x: x.start_time)
        for i in range(len(items) - 1):
            current_item = items[i]
            next_item = items[i + 1]
            
            if current_item.end_time and current_item.end_time > next_item.start_time:
                conflicts.append({
                    "type": "overlap",
                    "message": f"'{current_item.title}' overlaps with '{next_item.title}'",
                    "items": [current_item.id, next_item.id]
                })
        
        # Check for missing critical items
        critical_types = ['setup', 'arrival', 'cleanup']
        existing_types = [item.item_type.value for item in timeline.items]
        
        for critical_type in critical_types:
            if critical_type not in existing_types:
                warnings.append({
                    "type": "missing_critical",
                    "message": f"Missing critical item type: {critical_type}"
                })
        
        return {
            "is_valid": len(conflicts) == 0,
            "conflicts": conflicts,
            "warnings": warnings,
            "total_items": len(timeline.items),
            "validation_timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to validate timeline")

# Timeline sharing and collaboration
@timeline_router.post("/timelines/{timeline_id}/share")
async def share_timeline(
    timeline_id: int,
    share_with_user_ids: List[int],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Share timeline with other users"""
    try:
        timeline_service = TimelineService(db)
        timeline = timeline_service.get_timeline(timeline_id, current_user.id)
        
        if not timeline:
            raise http_404_not_found("Timeline not found")
        
        # This would typically involve creating sharing records
        # For now, return a success message
        return {
            "message": f"Timeline shared with {len(share_with_user_ids)} users",
            "timeline_id": timeline_id,
            "shared_with": share_with_user_ids
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to share timeline")