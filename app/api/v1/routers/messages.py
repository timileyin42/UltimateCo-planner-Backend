from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.deps import get_db, get_current_active_user
from app.core.errors import http_400_bad_request, http_404_not_found, http_403_forbidden
from app.services.message_service import MessageService
from app.schemas.message import (
    MessageCreate, MessageUpdate, MessageResponse, MessageListResponse,
    MessageReactionCreate, MessageReactionResponse, EventChatSettingsResponse,
    EventChatSettingsUpdate, ChatParticipantResponse, ChatParticipantUpdate,
    MessageSearchParams, MessageBulkDelete, MessageBulkMarkRead,
    ChatStatistics, MessageFileUpload
)
from app.models.user_models import User
from pydantic import BaseModel
import json

messages_router = APIRouter()

# Message CRUD endpoints
@messages_router.post("/events/{event_id}/messages", response_model=MessageResponse)
async def create_message(
    event_id: int,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new message in an event chat"""
    try:
        message_service = MessageService(db)
        message = message_service.create_message(event_id, current_user.id, message_data)
        
        return MessageResponse.model_validate(message)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower() or "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        elif "disabled" in str(e).lower():
            raise http_400_bad_request(str(e))
        else:
            raise http_400_bad_request("Failed to create message")

@messages_router.post("/events/{event_id}/messages/file", response_model=MessageResponse)
async def create_file_message(
    event_id: int,
    file: UploadFile = File(...),
    content: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a message with file attachment"""
    try:
        from app.services.gcp_storage_service import gcp_storage_service
        
        # Read file content
        file_content = await file.read()
        
        # Validate file
        validation = gcp_storage_service.validate_file(
            filename=file.filename,
            file_size=len(file_content),
            content_type=file.content_type,
            allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf', 'doc', 'docx', 'txt'],
            max_size_mb=25
        )
        
        if not validation["is_valid"]:
            raise http_400_bad_request(f"File validation failed: {', '.join(validation['errors'])}")
        
        # Upload to GCP Storage
        upload_result = await gcp_storage_service.upload_file(
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type,
            folder=f"messages/event_{event_id}",
            user_id=current_user.id
        )
        
        file_data = MessageFileUpload(
            content=content,
            file_name=upload_result["filename"],
            file_size=upload_result["file_size"],
            file_type=upload_result["content_type"],
            file_url=upload_result["file_url"]
        )
        
        message_service = MessageService(db)
        message = message_service.create_file_message(event_id, current_user.id, file_data)
        
        return MessageResponse.model_validate(message)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower() or "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        elif "disabled" in str(e).lower() or "exceeds limit" in str(e).lower():
            raise http_400_bad_request(str(e))
        elif "validation failed" in str(e).lower():
            raise http_400_bad_request(str(e))
        else:
            raise http_400_bad_request("Failed to upload file")

@messages_router.get("/events/{event_id}/messages", response_model=MessageListResponse)
async def get_messages(
    event_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=100),
    before_message_id: Optional[int] = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get paginated messages for an event"""
    try:
        message_service = MessageService(db)
        messages, total = message_service.get_messages(
            event_id, current_user.id, page, per_page, before_message_id
        )
        
        message_responses = [MessageResponse.model_validate(msg) for msg in messages]
        
        return MessageListResponse(
            messages=message_responses,
            total=total,
            page=page,
            per_page=per_page,
            has_next=(page * per_page) < total,
            has_prev=page > 1
        )
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get messages")

@messages_router.get("/events/{event_id}/messages/search", response_model=MessageListResponse)
async def search_messages(
    event_id: int,
    search_params: MessageSearchParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Search messages in an event"""
    try:
        message_service = MessageService(db)
        messages, total = message_service.search_messages(event_id, current_user.id, search_params)
        
        message_responses = [MessageResponse.model_validate(msg) for msg in messages]
        
        return MessageListResponse(
            messages=message_responses,
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
            raise http_400_bad_request("Failed to search messages")

@messages_router.get("/messages/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific message by ID"""
    try:
        message_service = MessageService(db)
        message = message_service.get_message(message_id, current_user.id)
        
        if not message:
            raise http_404_not_found("Message not found")
        
        return MessageResponse.model_validate(message)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get message")

@messages_router.put("/messages/{message_id}", response_model=MessageResponse)
async def update_message(
    message_id: int,
    update_data: MessageUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a message (only by sender)"""
    try:
        message_service = MessageService(db)
        message = message_service.update_message(message_id, current_user.id, update_data)
        
        return MessageResponse.model_validate(message)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower() or "own messages" in str(e).lower():
            raise http_403_forbidden(str(e))
        elif "too old" in str(e).lower():
            raise http_400_bad_request(str(e))
        else:
            raise http_400_bad_request("Failed to update message")

@messages_router.delete("/messages/{message_id}")
async def delete_message(
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a message (soft delete)"""
    try:
        message_service = MessageService(db)
        success = message_service.delete_message(message_id, current_user.id)
        
        return {"message": "Message deleted successfully", "success": success}
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to delete message")

# Message actions
@messages_router.post("/messages/{message_id}/pin", response_model=MessageResponse)
async def pin_message(
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Pin a message in the chat"""
    try:
        message_service = MessageService(db)
        message = message_service.pin_message(message_id, current_user.id)
        
        return MessageResponse.model_validate(message)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to pin message")

@messages_router.delete("/messages/{message_id}/pin", response_model=MessageResponse)
async def unpin_message(
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Unpin a message in the chat"""
    try:
        message_service = MessageService(db)
        message = message_service.unpin_message(message_id, current_user.id)
        
        return MessageResponse.model_validate(message)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to unpin message")

# Reaction endpoints
@messages_router.post("/messages/{message_id}/reactions", response_model=MessageReactionResponse)
async def add_reaction(
    message_id: int,
    reaction_data: MessageReactionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Add a reaction to a message"""
    try:
        message_service = MessageService(db)
        reaction = message_service.add_reaction(message_id, current_user.id, reaction_data)
        
        return MessageReactionResponse.model_validate(reaction)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to add reaction")

@messages_router.delete("/messages/{message_id}/reactions/{emoji}")
async def remove_reaction(
    message_id: int,
    emoji: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Remove a reaction from a message"""
    try:
        message_service = MessageService(db)
        success = message_service.remove_reaction(message_id, current_user.id, emoji)
        
        return {"message": "Reaction removed successfully", "success": success}
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        else:
            raise http_400_bad_request("Failed to remove reaction")

# Chat settings endpoints
@messages_router.get("/events/{event_id}/chat/settings", response_model=EventChatSettingsResponse)
async def get_chat_settings(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get chat settings for an event"""
    try:
        message_service = MessageService(db)
        settings = message_service.get_chat_settings(event_id)
        
        return EventChatSettingsResponse.model_validate(settings)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get chat settings")

@messages_router.put("/events/{event_id}/chat/settings", response_model=EventChatSettingsResponse)
async def update_chat_settings(
    event_id: int,
    settings_data: EventChatSettingsUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update chat settings for an event (only event creator)"""
    try:
        message_service = MessageService(db)
        settings = message_service.update_chat_settings(event_id, current_user.id, settings_data)
        
        return EventChatSettingsResponse.model_validate(settings)
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower() or "creator" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to update chat settings")

# Bulk operations
@messages_router.post("/events/{event_id}/messages/bulk-delete")
async def bulk_delete_messages(
    event_id: int,
    delete_data: MessageBulkDelete,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Bulk delete messages (event creator only)"""
    try:
        message_service = MessageService(db)
        
        # Verify user is event creator
        event = message_service._get_event_with_access(event_id, current_user.id)
        if event.creator_id != current_user.id:
            raise http_403_forbidden("Only event creator can bulk delete messages")
        
        deleted_count = 0
        for message_id in delete_data.message_ids:
            try:
                message_service.delete_message(message_id, current_user.id)
                deleted_count += 1
            except Exception:
                continue  # Skip messages that can't be deleted
        
        return {
            "message": f"Deleted {deleted_count} messages",
            "deleted_count": deleted_count,
            "total_requested": len(delete_data.message_ids)
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "permission" in str(e).lower() or "creator" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to bulk delete messages")

@messages_router.post("/events/{event_id}/messages/mark-read")
async def mark_messages_read(
    event_id: int,
    read_data: MessageBulkMarkRead,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Mark multiple messages as read"""
    try:
        message_service = MessageService(db)
        
        # Verify access
        message_service._get_event_with_access(event_id, current_user.id)
        
        # Mark messages as read
        message_service._mark_messages_as_read(event_id, current_user.id, read_data.message_ids)
        
        return {
            "message": "Messages marked as read",
            "marked_count": len(read_data.message_ids)
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to mark messages as read")

# Chat statistics
@messages_router.get("/events/{event_id}/chat/stats", response_model=ChatStatistics)
async def get_chat_statistics(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get chat statistics for an event"""
    try:
        message_service = MessageService(db)
        
        # Verify access
        message_service._get_event_with_access(event_id, current_user.id)
        
        # Get basic statistics
        from sqlalchemy import func, distinct
        from app.models.message_models import Message, MessageReaction, ChatParticipant
        from datetime import datetime, timedelta
        
        today = datetime.utcnow().date()
        
        # Total messages
        total_messages = db.query(func.count(Message.id)).filter(
            Message.event_id == event_id
        ).scalar() or 0
        
        # Messages today
        messages_today = db.query(func.count(Message.id)).filter(
            Message.event_id == event_id,
            func.date(Message.created_at) == today
        ).scalar() or 0
        
        # Total participants
        total_participants = db.query(func.count(distinct(ChatParticipant.user_id))).filter(
            ChatParticipant.event_id == event_id
        ).scalar() or 0
        
        # Active participants today
        active_today = db.query(func.count(distinct(ChatParticipant.user_id))).filter(
            ChatParticipant.event_id == event_id,
            func.date(ChatParticipant.last_seen_at) == today
        ).scalar() or 0
        
        # File count
        file_count = db.query(func.count(Message.id)).filter(
            Message.event_id == event_id,
            Message.file_url.isnot(None)
        ).scalar() or 0
        
        # Reaction count
        reaction_count = db.query(func.count(MessageReaction.id)).join(
            Message, MessageReaction.message_id == Message.id
        ).filter(Message.event_id == event_id).scalar() or 0
        
        return ChatStatistics(
            total_messages=total_messages,
            total_participants=total_participants,
            active_participants_today=active_today,
            messages_today=messages_today,
            file_count=file_count,
            reaction_count=reaction_count
        )
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get chat statistics")

# Typing indicator endpoint (for REST API, WebSocket would be better)
@messages_router.post("/events/{event_id}/typing")
async def send_typing_indicator(
    event_id: int,
    is_typing: bool,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Send typing indicator (REST endpoint, WebSocket preferred for real-time)"""
    try:
        message_service = MessageService(db)
        
        # Verify access
        message_service._get_event_with_access(event_id, current_user.id)
        
        # Update participant's last seen
        if is_typing:
            message_service._update_participant_last_seen(event_id, current_user.id)
        
        # In a real implementation, this would broadcast via WebSocket
        return {
            "message": "Typing indicator sent",
            "event_id": event_id,
            "user_id": current_user.id,
            "is_typing": is_typing
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to send typing indicator")

# Get pinned messages
@messages_router.get("/events/{event_id}/messages/pinned", response_model=List[MessageResponse])
async def get_pinned_messages(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all pinned messages for an event"""
    try:
        message_service = MessageService(db)
        
        # Verify access
        message_service._get_event_with_access(event_id, current_user.id)
        
        # Get pinned messages
        from app.models.message_models import Message
        pinned_messages = db.query(Message).filter(
            Message.event_id == event_id,
            Message.is_pinned == True
        ).order_by(Message.pinned_at.desc()).all()
        
        return [MessageResponse.model_validate(msg) for msg in pinned_messages]
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get pinned messages")

# Get unread message count
@messages_router.get("/events/{event_id}/messages/unread-count")
async def get_unread_count(
    event_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get unread message count for current user"""
    try:
        message_service = MessageService(db)
        
        # Verify access
        message_service._get_event_with_access(event_id, current_user.id)
        
        # Get participant's last read message
        from app.models.message_models import ChatParticipant, Message
        participant = db.query(ChatParticipant).filter(
            ChatParticipant.event_id == event_id,
            ChatParticipant.user_id == current_user.id
        ).first()
        
        if not participant or not participant.last_read_message_id:
            # Count all messages if no read history
            unread_count = db.query(func.count(Message.id)).filter(
                Message.event_id == event_id
            ).scalar() or 0
        else:
            # Count messages after last read
            last_read_message = db.query(Message).filter(
                Message.id == participant.last_read_message_id
            ).first()
            
            if last_read_message:
                unread_count = db.query(func.count(Message.id)).filter(
                    Message.event_id == event_id,
                    Message.created_at > last_read_message.created_at
                ).scalar() or 0
            else:
                unread_count = 0
        
        return {
            "event_id": event_id,
            "unread_count": unread_count
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise http_404_not_found(str(e))
        elif "access denied" in str(e).lower():
            raise http_403_forbidden(str(e))
        else:
            raise http_400_bad_request("Failed to get unread count")