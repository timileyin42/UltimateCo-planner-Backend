from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, func, text
from datetime import datetime, timedelta
from app.models.message_models import (
    Message, MessageReaction, MessageReadReceipt, EventChatSettings,
    ChatParticipant, MessageMention, MessageType, MessageStatus
)
from app.models.user_models import User
from app.models.event_models import Event
from app.schemas.message import (
    MessageCreate, MessageUpdate, MessageFileUpload, MessageReactionCreate,
    ChatParticipantUpdate, EventChatSettingsCreate, EventChatSettingsUpdate,
    SystemMessageData, MessageSearchParams
)
from app.core.errors import NotFoundError, ValidationError, AuthorizationError
from app.services.email_service import email_service
import json
import asyncio

class MessageService:
    """Service for managing event messages and chat functionality."""
    
    def __init__(self, db: Session):
        self.db = db
    
    # Message CRUD operations
    def create_message(
        self, 
        event_id: int, 
        sender_id: int, 
        message_data: MessageCreate
    ) -> Message:
        """Create a new message in an event chat."""
        # Verify event exists and user has access
        event = self._get_event_with_access(event_id, sender_id)
        
        # Check if chat is enabled
        chat_settings = self.get_chat_settings(event_id)
        if not chat_settings.is_enabled:
            raise ValidationError("Chat is disabled for this event")
        
        # Verify reply_to message exists if specified
        if message_data.reply_to_id:
            reply_to = self.db.query(Message).filter(
                Message.id == message_data.reply_to_id,
                Message.event_id == event_id
            ).first()
            if not reply_to:
                raise NotFoundError("Reply-to message not found")
        
        # Create message
        message = Message(
            content=message_data.content,
            message_type=message_data.message_type,
            event_id=event_id,
            sender_id=sender_id,
            reply_to_id=message_data.reply_to_id,
            status=MessageStatus.SENT
        )
        
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        
        # Update participant's last seen
        self._update_participant_last_seen(event_id, sender_id)
        
        # Process mentions if any
        self._process_mentions(message)
        
        # Send notifications
        self._send_message_notifications(message)
        
        return message
    
    def create_file_message(
        self, 
        event_id: int, 
        sender_id: int, 
        file_data: MessageFileUpload
    ) -> Message:
        """Create a message with file attachment."""
        # Verify event exists and user has access
        event = self._get_event_with_access(event_id, sender_id)
        
        # Check if file uploads are allowed
        chat_settings = self.get_chat_settings(event_id)
        if not chat_settings.allow_file_uploads:
            raise ValidationError("File uploads are disabled for this event")
        
        # Check file size
        max_size_bytes = chat_settings.max_file_size_mb * 1024 * 1024
        if file_data.file_size > max_size_bytes:
            raise ValidationError(f"File size exceeds limit of {chat_settings.max_file_size_mb}MB")
        
        # Create message with file
        message = Message(
            content=file_data.content or f"Shared a file: {file_data.file_name}",
            message_type=MessageType.FILE,
            event_id=event_id,
            sender_id=sender_id,
            file_url=file_data.file_url,
            file_name=file_data.file_name,
            file_size=file_data.file_size,
            file_type=file_data.file_type,
            status=MessageStatus.SENT
        )
        
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        
        # Update participant's last seen
        self._update_participant_last_seen(event_id, sender_id)
        
        # Send notifications
        self._send_message_notifications(message)
        
        return message
    
    def create_system_message(
        self, 
        event_id: int, 
        system_data: SystemMessageData
    ) -> Message:
        """Create a system message for event updates."""
        # Create system message content
        content = self._format_system_message(system_data)
        
        message = Message(
            content=content,
            message_type=MessageType.SYSTEM,
            event_id=event_id,
            sender_id=None,  # System messages have no sender
            system_data=json.dumps(system_data.model_dump()),
            status=MessageStatus.SENT
        )
        
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        
        return message
    
    def get_message(self, message_id: int, user_id: int) -> Optional[Message]:
        """Get a specific message by ID."""
        message = self.db.query(Message).options(
            joinedload(Message.sender),
            joinedload(Message.reactions).joinedload(MessageReaction.user),
            joinedload(Message.reply_to)
        ).filter(Message.id == message_id).first()
        
        if not message:
            return None
        
        # Check if user has access to the event
        self._get_event_with_access(message.event_id, user_id)
        
        return message
    
    def get_messages(
        self, 
        event_id: int, 
        user_id: int, 
        page: int = 1, 
        per_page: int = 50,
        before_message_id: Optional[int] = None
    ) -> Tuple[List[Message], int]:
        """Get paginated messages for an event."""
        # Verify access
        self._get_event_with_access(event_id, user_id)
        
        # Build query
        query = self.db.query(Message).options(
            joinedload(Message.sender),
            joinedload(Message.reactions).joinedload(MessageReaction.user)
        ).filter(Message.event_id == event_id)
        
        # Add before_message_id filter for pagination
        if before_message_id:
            before_message = self.db.query(Message).filter(
                Message.id == before_message_id
            ).first()
            if before_message:
                query = query.filter(Message.created_at < before_message.created_at)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        messages = query.order_by(desc(Message.created_at)).offset(
            (page - 1) * per_page
        ).limit(per_page).all()
        
        # Reverse to show oldest first
        messages.reverse()
        
        # Mark messages as read for this user
        self._mark_messages_as_read(event_id, user_id, [msg.id for msg in messages])
        
        return messages, total
    
    def search_messages(
        self, 
        event_id: int, 
        user_id: int, 
        search_params: MessageSearchParams
    ) -> Tuple[List[Message], int]:
        """Search messages in an event."""
        # Verify access
        self._get_event_with_access(event_id, user_id)
        
        # Build query
        query = self.db.query(Message).options(
            joinedload(Message.sender),
            joinedload(Message.reactions).joinedload(MessageReaction.user)
        ).filter(Message.event_id == event_id)
        
        # Apply filters
        if search_params.query:
            query = query.filter(Message.content.ilike(f"%{search_params.query}%"))
        
        if search_params.message_type:
            query = query.filter(Message.message_type == search_params.message_type)
        
        if search_params.sender_id:
            query = query.filter(Message.sender_id == search_params.sender_id)
        
        if search_params.date_from:
            query = query.filter(Message.created_at >= search_params.date_from)
        
        if search_params.date_to:
            query = query.filter(Message.created_at <= search_params.date_to)
        
        if search_params.has_files is not None:
            if search_params.has_files:
                query = query.filter(Message.file_url.isnot(None))
            else:
                query = query.filter(Message.file_url.is_(None))
        
        if search_params.is_pinned is not None:
            query = query.filter(Message.is_pinned == search_params.is_pinned)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        messages = query.order_by(desc(Message.created_at)).offset(
            (search_params.page - 1) * search_params.per_page
        ).limit(search_params.per_page).all()
        
        return messages, total
    
    def update_message(
        self, 
        message_id: int, 
        user_id: int, 
        update_data: MessageUpdate
    ) -> Message:
        """Update a message (only by sender)."""
        message = self.db.query(Message).filter(Message.id == message_id).first()
        
        if not message:
            raise NotFoundError("Message not found")
        
        # Check if user is the sender
        if message.sender_id != user_id:
            raise AuthorizationError("You can only edit your own messages")
        
        # Check if message is too old to edit (24 hours)
        if datetime.utcnow() - message.created_at > timedelta(hours=24):
            raise ValidationError("Message is too old to edit")
        
        # Update message
        message.content = update_data.content
        message.is_edited = True
        message.edited_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(message)
        
        return message
    
    def delete_message(self, message_id: int, user_id: int) -> bool:
        """Delete a message (soft delete)."""
        message = self.db.query(Message).filter(Message.id == message_id).first()
        
        if not message:
            raise NotFoundError("Message not found")
        
        # Check permissions (sender or event creator)
        event = self.db.query(Event).filter(Event.id == message.event_id).first()
        if message.sender_id != user_id and event.creator_id != user_id:
            raise AuthorizationError("You don't have permission to delete this message")
        
        # Soft delete
        message.content = "[Message deleted]"
        message.is_edited = True
        message.edited_at = datetime.utcnow()
        
        self.db.commit()
        
        return True
    
    def pin_message(self, message_id: int, user_id: int) -> Message:
        """Pin a message in the chat."""
        message = self.db.query(Message).filter(Message.id == message_id).first()
        
        if not message:
            raise NotFoundError("Message not found")
        
        # Check if user is event creator or collaborator
        event = self._get_event_with_access(message.event_id, user_id)
        if event.creator_id != user_id and user_id not in [c.id for c in event.collaborators]:
            raise AuthorizationError("You don't have permission to pin messages")
        
        # Pin message
        message.is_pinned = True
        message.pinned_at = datetime.utcnow()
        message.pinned_by_id = user_id
        
        self.db.commit()
        self.db.refresh(message)
        
        return message
    
    def unpin_message(self, message_id: int, user_id: int) -> Message:
        """Unpin a message in the chat."""
        message = self.db.query(Message).filter(Message.id == message_id).first()
        
        if not message:
            raise NotFoundError("Message not found")
        
        # Check permissions
        event = self._get_event_with_access(message.event_id, user_id)
        if event.creator_id != user_id and user_id not in [c.id for c in event.collaborators]:
            raise AuthorizationError("You don't have permission to unpin messages")
        
        # Unpin message
        message.is_pinned = False
        message.pinned_at = None
        message.pinned_by_id = None
        
        self.db.commit()
        self.db.refresh(message)
        
        return message
    
    # Reaction operations
    def add_reaction(
        self, 
        message_id: int, 
        user_id: int, 
        reaction_data: MessageReactionCreate
    ) -> MessageReaction:
        """Add a reaction to a message."""
        message = self.db.query(Message).filter(Message.id == message_id).first()
        
        if not message:
            raise NotFoundError("Message not found")
        
        # Verify access
        self._get_event_with_access(message.event_id, user_id)
        
        # Check if reaction already exists
        existing_reaction = self.db.query(MessageReaction).filter(
            MessageReaction.message_id == message_id,
            MessageReaction.user_id == user_id,
            MessageReaction.emoji == reaction_data.emoji
        ).first()
        
        if existing_reaction:
            return existing_reaction
        
        # Create reaction
        reaction = MessageReaction(
            message_id=message_id,
            user_id=user_id,
            emoji=reaction_data.emoji
        )
        
        self.db.add(reaction)
        self.db.commit()
        self.db.refresh(reaction)
        
        return reaction
    
    def remove_reaction(self, message_id: int, user_id: int, emoji: str) -> bool:
        """Remove a reaction from a message."""
        reaction = self.db.query(MessageReaction).filter(
            MessageReaction.message_id == message_id,
            MessageReaction.user_id == user_id,
            MessageReaction.emoji == emoji
        ).first()
        
        if not reaction:
            raise NotFoundError("Reaction not found")
        
        self.db.delete(reaction)
        self.db.commit()
        
        return True
    
    # Chat settings operations
    def get_chat_settings(self, event_id: int) -> EventChatSettings:
        """Get chat settings for an event."""
        settings = self.db.query(EventChatSettings).filter(
            EventChatSettings.event_id == event_id
        ).first()
        
        if not settings:
            # Create default settings
            settings = EventChatSettings(event_id=event_id)
            self.db.add(settings)
            self.db.commit()
            self.db.refresh(settings)
        
        return settings
    
    def update_chat_settings(
        self, 
        event_id: int, 
        user_id: int, 
        settings_data: EventChatSettingsUpdate
    ) -> EventChatSettings:
        """Update chat settings for an event."""
        # Check permissions (only event creator)
        event = self._get_event_with_access(event_id, user_id)
        if event.creator_id != user_id:
            raise AuthorizationError("Only event creator can modify chat settings")
        
        settings = self.get_chat_settings(event_id)
        
        # Update settings
        for field, value in settings_data.model_dump(exclude_unset=True).items():
            if hasattr(settings, field):
                setattr(settings, field, value)
        
        self.db.commit()
        self.db.refresh(settings)
        
        return settings
    
    # Helper methods
    def _get_event_with_access(self, event_id: int, user_id: int) -> Event:
        """Get event and verify user has access."""
        event = self.db.query(Event).options(
            joinedload(Event.collaborators)
        ).filter(Event.id == event_id).first()
        
        if not event:
            raise NotFoundError("Event not found")
        
        # Check access (creator, collaborator, or invited)
        if (event.creator_id != user_id and 
            user_id not in [c.id for c in event.collaborators]):
            # Check if user is invited
            from app.models.event_models import EventInvitation
            invitation = self.db.query(EventInvitation).filter(
                EventInvitation.event_id == event_id,
                EventInvitation.user_id == user_id
            ).first()
            
            if not invitation:
                raise AuthorizationError("You don't have access to this event")
        
        return event
    
    def _update_participant_last_seen(self, event_id: int, user_id: int):
        """Update participant's last seen timestamp."""
        participant = self.db.query(ChatParticipant).filter(
            ChatParticipant.event_id == event_id,
            ChatParticipant.user_id == user_id
        ).first()
        
        if not participant:
            participant = ChatParticipant(
                event_id=event_id,
                user_id=user_id,
                last_seen_at=datetime.utcnow()
            )
            self.db.add(participant)
        else:
            participant.last_seen_at = datetime.utcnow()
        
        self.db.commit()
    
    def _mark_messages_as_read(self, event_id: int, user_id: int, message_ids: List[int]):
        """Mark messages as read for a user."""
        for message_id in message_ids:
            existing_receipt = self.db.query(MessageReadReceipt).filter(
                MessageReadReceipt.message_id == message_id,
                MessageReadReceipt.user_id == user_id
            ).first()
            
            if not existing_receipt:
                receipt = MessageReadReceipt(
                    message_id=message_id,
                    user_id=user_id,
                    read_at=datetime.utcnow()
                )
                self.db.add(receipt)
        
        self.db.commit()
    
    def _process_mentions(self, message: Message):
        """Process @mentions in message content."""
        # Simple mention processing - look for @username patterns
        import re
        mention_pattern = r'@(\w+)'
        mentions = re.finditer(mention_pattern, message.content)
        
        for match in mentions:
            username = match.group(1)
            start_index = match.start()
            end_index = match.end()
            
            # Find user by username
            user = self.db.query(User).filter(User.username == username).first()
            if user:
                mention = MessageMention(
                    message_id=message.id,
                    mentioned_user_id=user.id,
                    start_index=start_index,
                    end_index=end_index
                )
                self.db.add(mention)
        
        self.db.commit()
    
    def _send_message_notifications(self, message: Message):
        """Send notifications for new messages."""
        # Get event participants who should be notified
        participants = self.db.query(ChatParticipant).filter(
            ChatParticipant.event_id == message.event_id,
            ChatParticipant.user_id != message.sender_id,  # Don't notify sender
            ChatParticipant.is_muted == False,
            ChatParticipant.email_notifications == True
        ).all()
        
        # Send email notifications asynchronously
        for participant in participants:
            try:
                asyncio.create_task(
                    email_service.send_new_message_notification(
                        message, participant.user
                    )
                )
            except Exception as e:
                print(f"Failed to send message notification: {str(e)}")
    
    def _format_system_message(self, system_data: SystemMessageData) -> str:
        """Format system message content."""
        action = system_data.action
        actor = system_data.actor_name
        target = system_data.target_name
        
        if action == "user_joined":
            return f"{actor} joined the event"
        elif action == "user_left":
            return f"{actor} left the event"
        elif action == "task_created":
            return f"{actor} created a new task: {target}"
        elif action == "task_completed":
            return f"{actor} completed task: {target}"
        elif action == "expense_added":
            return f"{actor} added an expense: {target}"
        elif action == "poll_created":
            return f"{actor} created a poll: {target}"
        elif action == "rsvp_updated":
            return f"{actor} updated their RSVP"
        else:
            return f"{actor} performed an action"

# Global message service instance
def get_message_service(db: Session) -> MessageService:
    return MessageService(db)