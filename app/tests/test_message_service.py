import pytest
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session
from app.services.message_service import MessageService
from app.models.message_models import (
    Message, MessageReaction, MessageReadReceipt, EventChatSettings,
    ChatParticipant, MessageMention, MessageType, MessageStatus
)
from app.models.user_models import User
from app.models.event_models import Event, EventInvitation
from app.schemas.message import (
    MessageCreate, MessageUpdate, MessageFileUpload, MessageReactionCreate,
    EventChatSettingsUpdate, SystemMessageData, MessageSearchParams
)
from app.core.errors import NotFoundError, ValidationError, AuthorizationError
from app.tests.conftest import UserFactory, EventFactory
from datetime import datetime, timedelta

class TestMessageService:
    """Test cases for MessageService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = Mock(spec=Session)
        self.message_service = MessageService(self.mock_db)
        
        # Mock user
        self.mock_user = Mock(spec=User)
        self.mock_user.id = 1
        self.mock_user.email = "test@example.com"
        self.mock_user.full_name = "Test User"
        
        # Mock event
        self.mock_event = Mock(spec=Event)
        self.mock_event.id = 1
        self.mock_event.title = "Test Event"
        self.mock_event.creator_id = 1
        self.mock_event.collaborators = []
        
        # Mock message
        self.mock_message = Mock(spec=Message)
        self.mock_message.id = 1
        self.mock_message.content = "Test message"
        self.mock_message.event_id = 1
        self.mock_message.sender_id = 1
        self.mock_message.message_type = MessageType.TEXT
        self.mock_message.created_at = datetime.utcnow()
    
    def test_create_message_success(self):
        """Test successful message creation."""
        message_data = MessageCreate(
            content="Hello everyone!",
            message_type=MessageType.TEXT
        )
        
        # Mock database operations
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_event
        self.mock_db.query.return_value.filter.return_value.options.return_value.filter.return_value.first.return_value = self.mock_event
        
        # Mock chat settings
        mock_settings = Mock(spec=EventChatSettings)
        mock_settings.is_enabled = True
        
        with patch.object(self.message_service, 'get_chat_settings', return_value=mock_settings), \
             patch.object(self.message_service, '_get_event_with_access', return_value=self.mock_event), \
             patch.object(self.message_service, '_update_participant_last_seen'), \
             patch.object(self.message_service, '_process_mentions'), \
             patch.object(self.message_service, '_send_message_notifications'), \
             patch('app.services.message_service.Message', return_value=self.mock_message):
            
            result = self.message_service.create_message(1, 1, message_data)
            
            assert result == self.mock_message
            self.mock_db.add.assert_called_once()
            self.mock_db.commit.assert_called_once()
            self.mock_db.refresh.assert_called_once()
    
    def test_create_message_chat_disabled(self):
        """Test message creation when chat is disabled."""
        message_data = MessageCreate(content="Hello!")
        
        # Mock chat settings with chat disabled
        mock_settings = Mock(spec=EventChatSettings)
        mock_settings.is_enabled = False
        
        with patch.object(self.message_service, 'get_chat_settings', return_value=mock_settings), \
             patch.object(self.message_service, '_get_event_with_access', return_value=self.mock_event):
            
            with pytest.raises(ValidationError, match="Chat is disabled for this event"):
                self.message_service.create_message(1, 1, message_data)
    
    def test_create_message_with_reply(self):
        """Test message creation with reply to another message."""
        message_data = MessageCreate(
            content="Reply message",
            reply_to_id=2
        )
        
        # Mock reply-to message
        mock_reply_message = Mock(spec=Message)
        mock_reply_message.id = 2
        
        self.mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_reply_message,  # For reply-to check
        ]
        
        mock_settings = Mock(spec=EventChatSettings)
        mock_settings.is_enabled = True
        
        with patch.object(self.message_service, 'get_chat_settings', return_value=mock_settings), \
             patch.object(self.message_service, '_get_event_with_access', return_value=self.mock_event), \
             patch.object(self.message_service, '_update_participant_last_seen'), \
             patch.object(self.message_service, '_process_mentions'), \
             patch.object(self.message_service, '_send_message_notifications'), \
             patch('app.services.message_service.Message', return_value=self.mock_message):
            
            result = self.message_service.create_message(1, 1, message_data)
            
            assert result == self.mock_message
    
    def test_create_message_invalid_reply(self):
        """Test message creation with invalid reply-to ID."""
        message_data = MessageCreate(
            content="Reply message",
            reply_to_id=999  # Non-existent message
        )
        
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        mock_settings = Mock(spec=EventChatSettings)
        mock_settings.is_enabled = True
        
        with patch.object(self.message_service, 'get_chat_settings', return_value=mock_settings), \
             patch.object(self.message_service, '_get_event_with_access', return_value=self.mock_event):
            
            with pytest.raises(NotFoundError, match="Reply-to message not found"):
                self.message_service.create_message(1, 1, message_data)
    
    def test_create_file_message_success(self):
        """Test successful file message creation."""
        file_data = MessageFileUpload(
            content="Check out this file!",
            file_name="document.pdf",
            file_size=1024000,  # 1MB
            file_type="application/pdf",
            file_url="/uploads/document.pdf"
        )
        
        mock_settings = Mock(spec=EventChatSettings)
        mock_settings.is_enabled = True
        mock_settings.allow_file_uploads = True
        mock_settings.max_file_size_mb = 10
        
        with patch.object(self.message_service, 'get_chat_settings', return_value=mock_settings), \
             patch.object(self.message_service, '_get_event_with_access', return_value=self.mock_event), \
             patch.object(self.message_service, '_update_participant_last_seen'), \
             patch.object(self.message_service, '_send_message_notifications'), \
             patch('app.services.message_service.Message', return_value=self.mock_message):
            
            result = self.message_service.create_file_message(1, 1, file_data)
            
            assert result == self.mock_message
            self.mock_db.add.assert_called_once()
            self.mock_db.commit.assert_called_once()
    
    def test_create_file_message_uploads_disabled(self):
        """Test file message creation when uploads are disabled."""
        file_data = MessageFileUpload(
            file_name="document.pdf",
            file_size=1024,
            file_type="application/pdf",
            file_url="/uploads/document.pdf"
        )
        
        mock_settings = Mock(spec=EventChatSettings)
        mock_settings.allow_file_uploads = False
        
        with patch.object(self.message_service, 'get_chat_settings', return_value=mock_settings), \
             patch.object(self.message_service, '_get_event_with_access', return_value=self.mock_event):
            
            with pytest.raises(ValidationError, match="File uploads are disabled"):
                self.message_service.create_file_message(1, 1, file_data)
    
    def test_create_file_message_size_exceeded(self):
        """Test file message creation when file size exceeds limit."""
        file_data = MessageFileUpload(
            file_name="large_file.pdf",
            file_size=20 * 1024 * 1024,  # 20MB
            file_type="application/pdf",
            file_url="/uploads/large_file.pdf"
        )
        
        mock_settings = Mock(spec=EventChatSettings)
        mock_settings.allow_file_uploads = True
        mock_settings.max_file_size_mb = 10  # 10MB limit
        
        with patch.object(self.message_service, 'get_chat_settings', return_value=mock_settings), \
             patch.object(self.message_service, '_get_event_with_access', return_value=self.mock_event):
            
            with pytest.raises(ValidationError, match="File size exceeds limit"):
                self.message_service.create_file_message(1, 1, file_data)
    
    def test_create_system_message(self):
        """Test system message creation."""
        system_data = SystemMessageData(
            action="user_joined",
            actor_name="John Doe"
        )
        
        with patch('app.services.message_service.Message', return_value=self.mock_message), \
             patch.object(self.message_service, '_format_system_message', return_value="John Doe joined the event"):
            
            result = self.message_service.create_system_message(1, system_data)
            
            assert result == self.mock_message
            self.mock_db.add.assert_called_once()
            self.mock_db.commit.assert_called_once()
    
    def test_get_message_success(self):
        """Test successful message retrieval."""
        self.mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = self.mock_message
        
        with patch.object(self.message_service, '_get_event_with_access', return_value=self.mock_event):
            result = self.message_service.get_message(1, 1)
            
            assert result == self.mock_message
    
    def test_get_message_not_found(self):
        """Test message retrieval when message doesn't exist."""
        self.mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = None
        
        result = self.message_service.get_message(999, 1)
        
        assert result is None
    
    def test_get_messages_success(self):
        """Test successful messages retrieval with pagination."""
        mock_messages = [self.mock_message]
        
        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_messages
        
        self.mock_db.query.return_value = mock_query
        
        with patch.object(self.message_service, '_get_event_with_access', return_value=self.mock_event), \
             patch.object(self.message_service, '_mark_messages_as_read'):
            
            messages, total = self.message_service.get_messages(1, 1, page=1, per_page=50)
            
            assert len(messages) == 1
            assert total == 1
            assert messages[0] == self.mock_message
    
    def test_update_message_success(self):
        """Test successful message update."""
        update_data = MessageUpdate(content="Updated message content")
        
        self.mock_message.sender_id = 1  # Same as user_id
        self.mock_message.created_at = datetime.utcnow() - timedelta(hours=1)  # Recent message
        
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_message
        
        result = self.message_service.update_message(1, 1, update_data)
        
        assert result == self.mock_message
        assert self.mock_message.content == "Updated message content"
        assert self.mock_message.is_edited is True
        self.mock_db.commit.assert_called_once()
    
    def test_update_message_not_sender(self):
        """Test message update by non-sender."""
        update_data = MessageUpdate(content="Updated content")
        
        self.mock_message.sender_id = 2  # Different from user_id (1)
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_message
        
        with pytest.raises(AuthorizationError, match="You can only edit your own messages"):
            self.message_service.update_message(1, 1, update_data)
    
    def test_update_message_too_old(self):
        """Test message update when message is too old."""
        update_data = MessageUpdate(content="Updated content")
        
        self.mock_message.sender_id = 1
        self.mock_message.created_at = datetime.utcnow() - timedelta(hours=25)  # Too old
        
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_message
        
        with pytest.raises(ValidationError, match="Message is too old to edit"):
            self.message_service.update_message(1, 1, update_data)
    
    def test_delete_message_by_sender(self):
        """Test message deletion by sender."""
        self.mock_message.sender_id = 1
        self.mock_event.creator_id = 2  # Different from sender
        
        self.mock_db.query.return_value.filter.return_value.first.side_effect = [
            self.mock_message,  # For message query
            self.mock_event      # For event query
        ]
        
        result = self.message_service.delete_message(1, 1)
        
        assert result is True
        assert self.mock_message.content == "[Message deleted]"
        assert self.mock_message.is_edited is True
        self.mock_db.commit.assert_called_once()
    
    def test_delete_message_by_event_creator(self):
        """Test message deletion by event creator."""
        self.mock_message.sender_id = 2  # Different from user
        self.mock_event.creator_id = 1   # Same as user
        
        self.mock_db.query.return_value.filter.return_value.first.side_effect = [
            self.mock_message,
            self.mock_event
        ]
        
        result = self.message_service.delete_message(1, 1)
        
        assert result is True
        self.mock_db.commit.assert_called_once()
    
    def test_delete_message_unauthorized(self):
        """Test message deletion by unauthorized user."""
        self.mock_message.sender_id = 2  # Different from user
        self.mock_event.creator_id = 3   # Different from user
        
        self.mock_db.query.return_value.filter.return_value.first.side_effect = [
            self.mock_message,
            self.mock_event
        ]
        
        with pytest.raises(AuthorizationError, match="You don't have permission to delete this message"):
            self.message_service.delete_message(1, 1)
    
    def test_pin_message_success(self):
        """Test successful message pinning."""
        self.mock_event.creator_id = 1  # User is creator
        
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_message
        
        with patch.object(self.message_service, '_get_event_with_access', return_value=self.mock_event):
            result = self.message_service.pin_message(1, 1)
            
            assert result == self.mock_message
            assert self.mock_message.is_pinned is True
            assert self.mock_message.pinned_by_id == 1
            self.mock_db.commit.assert_called_once()
    
    def test_pin_message_unauthorized(self):
        """Test message pinning by unauthorized user."""
        self.mock_event.creator_id = 2  # User is not creator
        self.mock_event.collaborators = []  # User is not collaborator
        
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.mock_message
        
        with patch.object(self.message_service, '_get_event_with_access', return_value=self.mock_event):
            with pytest.raises(AuthorizationError, match="You don't have permission to pin messages"):
                self.message_service.pin_message(1, 1)
    
    def test_add_reaction_success(self):
        """Test successful reaction addition."""
        reaction_data = MessageReactionCreate(emoji="👍")
        
        self.mock_db.query.return_value.filter.return_value.first.side_effect = [
            self.mock_message,  # Message exists
            None               # No existing reaction
        ]
        
        mock_reaction = Mock(spec=MessageReaction)
        
        with patch.object(self.message_service, '_get_event_with_access', return_value=self.mock_event), \
             patch('app.services.message_service.MessageReaction', return_value=mock_reaction):
            
            result = self.message_service.add_reaction(1, 1, reaction_data)
            
            assert result == mock_reaction
            self.mock_db.add.assert_called_once()
            self.mock_db.commit.assert_called_once()
    
    def test_add_reaction_already_exists(self):
        """Test adding reaction when it already exists."""
        reaction_data = MessageReactionCreate(emoji="👍")
        
        mock_existing_reaction = Mock(spec=MessageReaction)
        
        self.mock_db.query.return_value.filter.return_value.first.side_effect = [
            self.mock_message,        # Message exists
            mock_existing_reaction    # Reaction already exists
        ]
        
        with patch.object(self.message_service, '_get_event_with_access', return_value=self.mock_event):
            result = self.message_service.add_reaction(1, 1, reaction_data)
            
            assert result == mock_existing_reaction
            self.mock_db.add.assert_not_called()
    
    def test_remove_reaction_success(self):
        """Test successful reaction removal."""
        mock_reaction = Mock(spec=MessageReaction)
        
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_reaction
        
        result = self.message_service.remove_reaction(1, 1, "👍")
        
        assert result is True
        self.mock_db.delete.assert_called_once_with(mock_reaction)
        self.mock_db.commit.assert_called_once()
    
    def test_remove_reaction_not_found(self):
        """Test reaction removal when reaction doesn't exist."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(NotFoundError, match="Reaction not found"):
            self.message_service.remove_reaction(1, 1, "👍")
    
    def test_get_chat_settings_existing(self):
        """Test getting existing chat settings."""
        mock_settings = Mock(spec=EventChatSettings)
        
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_settings
        
        result = self.message_service.get_chat_settings(1)
        
        assert result == mock_settings
    
    def test_get_chat_settings_create_default(self):
        """Test getting chat settings when none exist (creates default)."""
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        mock_settings = Mock(spec=EventChatSettings)
        
        with patch('app.services.message_service.EventChatSettings', return_value=mock_settings):
            result = self.message_service.get_chat_settings(1)
            
            assert result == mock_settings
            self.mock_db.add.assert_called_once()
            self.mock_db.commit.assert_called_once()
    
    def test_update_chat_settings_success(self):
        """Test successful chat settings update."""
        settings_data = EventChatSettingsUpdate(
            is_enabled=False,
            allow_file_uploads=False
        )
        
        mock_settings = Mock(spec=EventChatSettings)
        self.mock_event.creator_id = 1  # User is creator
        
        with patch.object(self.message_service, '_get_event_with_access', return_value=self.mock_event), \
             patch.object(self.message_service, 'get_chat_settings', return_value=mock_settings):
            
            result = self.message_service.update_chat_settings(1, 1, settings_data)
            
            assert result == mock_settings
            self.mock_db.commit.assert_called_once()
    
    def test_update_chat_settings_unauthorized(self):
        """Test chat settings update by non-creator."""
        settings_data = EventChatSettingsUpdate(is_enabled=False)
        
        self.mock_event.creator_id = 2  # User is not creator
        
        with patch.object(self.message_service, '_get_event_with_access', return_value=self.mock_event):
            with pytest.raises(AuthorizationError, match="Only event creator can modify chat settings"):
                self.message_service.update_chat_settings(1, 1, settings_data)
    
    def test_get_event_with_access_creator(self):
        """Test event access check for creator."""
        self.mock_event.creator_id = 1
        
        self.mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = self.mock_event
        
        result = self.message_service._get_event_with_access(1, 1)
        
        assert result == self.mock_event
    
    def test_get_event_with_access_collaborator(self):
        """Test event access check for collaborator."""
        mock_collaborator = Mock()
        mock_collaborator.id = 1
        
        self.mock_event.creator_id = 2
        self.mock_event.collaborators = [mock_collaborator]
        
        self.mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = self.mock_event
        
        result = self.message_service._get_event_with_access(1, 1)
        
        assert result == self.mock_event
    
    def test_get_event_with_access_invited_user(self):
        """Test event access check for invited user."""
        self.mock_event.creator_id = 2
        self.mock_event.collaborators = []
        
        mock_invitation = Mock(spec=EventInvitation)
        
        self.mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = self.mock_event
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_invitation
        
        result = self.message_service._get_event_with_access(1, 1)
        
        assert result == self.mock_event
    
    def test_get_event_with_access_denied(self):
        """Test event access check when access is denied."""
        self.mock_event.creator_id = 2
        self.mock_event.collaborators = []
        
        self.mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = self.mock_event
        self.mock_db.query.return_value.filter.return_value.first.return_value = None  # No invitation
        
        with pytest.raises(AuthorizationError, match="You don't have access to this event"):
            self.message_service._get_event_with_access(1, 1)
    
    def test_get_event_with_access_not_found(self):
        """Test event access check when event doesn't exist."""
        self.mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(NotFoundError, match="Event not found"):
            self.message_service._get_event_with_access(999, 1)
    
    def test_process_mentions(self):
        """Test mention processing in messages."""
        self.mock_message.content = "Hello @testuser, how are you?"
        self.mock_message.id = 1
        
        mock_mentioned_user = Mock(spec=User)
        mock_mentioned_user.id = 2
        mock_mentioned_user.username = "testuser"
        
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_mentioned_user
        
        with patch('app.services.message_service.MessageMention') as mock_mention_class:
            self.message_service._process_mentions(self.mock_message)
            
            mock_mention_class.assert_called_once()
            self.mock_db.add.assert_called_once()
            self.mock_db.commit.assert_called_once()
    
    def test_format_system_message_user_joined(self):
        """Test system message formatting for user joined."""
        system_data = SystemMessageData(
            action="user_joined",
            actor_name="John Doe"
        )
        
        result = self.message_service._format_system_message(system_data)
        
        assert result == "John Doe joined the event"
    
    def test_format_system_message_task_created(self):
        """Test system message formatting for task creation."""
        system_data = SystemMessageData(
            action="task_created",
            actor_name="Jane Smith",
            target_name="Buy decorations"
        )
        
        result = self.message_service._format_system_message(system_data)
        
        assert result == "Jane Smith created a new task: Buy decorations"
    
    def test_format_system_message_unknown_action(self):
        """Test system message formatting for unknown action."""
        system_data = SystemMessageData(
            action="unknown_action",
            actor_name="User"
        )
        
        result = self.message_service._format_system_message(system_data)
        
        assert result == "User performed an action"
    
    @patch('app.services.message_service.asyncio.create_task')
    def test_send_message_notifications(self, mock_create_task):
        """Test sending message notifications."""
        mock_participant = Mock(spec=ChatParticipant)
        mock_participant.user = self.mock_user
        mock_participant.is_muted = False
        mock_participant.email_notifications = True
        
        self.mock_db.query.return_value.filter.return_value.all.return_value = [mock_participant]
        
        self.message_service._send_message_notifications(self.mock_message)
        
        mock_create_task.assert_called_once()
    
    def test_search_messages_with_query(self):
        """Test message search with text query."""
        search_params = MessageSearchParams(
            query="hello",
            page=1,
            per_page=20
        )
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [self.mock_message]
        
        self.mock_db.query.return_value = mock_query
        
        with patch.object(self.message_service, '_get_event_with_access', return_value=self.mock_event):
            messages, total = self.message_service.search_messages(1, 1, search_params)
            
            assert len(messages) == 1
            assert total == 1
    
    def test_search_messages_with_filters(self):
        """Test message search with multiple filters."""
        search_params = MessageSearchParams(
            message_type=MessageType.FILE,
            sender_id=1,
            has_files=True,
            is_pinned=True
        )
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        
        self.mock_db.query.return_value = mock_query
        
        with patch.object(self.message_service, '_get_event_with_access', return_value=self.mock_event):
            messages, total = self.message_service.search_messages(1, 1, search_params)
            
            assert len(messages) == 0
            assert total == 0