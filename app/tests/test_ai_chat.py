import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch, AsyncMock
import json
from datetime import datetime

from app.main import app
from app.models.user_models import User
from app.models.ai_chat_models import AIChatSession, AIChatMessage
from app.schemas.chat import ChatSessionCreate, ChatMessageCreate, ChatMessageRole, ChatSessionStatus
from app.services.ai_service import ai_service


class TestAIChatAPI:
    """Test AI Chat API endpoints"""

    def test_create_chat_session(self, client: TestClient, test_user: User, db: Session):
        """Test creating a new AI chat session"""
        session_data = {
            "title": "Birthday Party Planning",
            "description": "Help me plan a birthday party for my friend"
        }
        
        response = client.post(
            "/api/v1/ai-chat/sessions",
            json=session_data,
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == session_data["title"]
        assert data["status"] == ChatSessionStatus.ACTIVE
        assert data["user_id"] == test_user.id
        assert len(data["messages"]) == 1  # Initial AI greeting

    def test_get_chat_session(self, client: TestClient, test_user: User, db: Session):
        """Test retrieving a chat session"""
        # Create a session first
        session_data = ChatSessionCreate(
            title="Test Session",
            description="Test description"
        )
        
        with patch.object(ai_service, 'create_chat_session') as mock_create:
            mock_session = {
                "id": "test-session-id",
                "user_id": test_user.id,
                "status": ChatSessionStatus.ACTIVE,
                "title": "Test Session",
                "messages": [],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            mock_create.return_value = mock_session
            
            # Create session
            create_response = client.post(
                "/api/v1/ai-chat/sessions",
                json=session_data.model_dump(),
                headers={"Authorization": f"Bearer {test_user.access_token}"}
            )
            
            session_id = create_response.json()["id"]
            
            # Get session
            with patch.object(ai_service, 'get_chat_session') as mock_get:
                mock_get.return_value = mock_session
                
                response = client.get(
                    f"/api/v1/ai-chat/sessions/{session_id}",
                    headers={"Authorization": f"Bearer {test_user.access_token}"}
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["id"] == session_id

    def test_send_chat_message(self, client: TestClient, test_user: User, db: Session):
        """Test sending a message in a chat session"""
        session_id = "test-session-id"
        message_data = {
            "content": "I want to plan a birthday party for 20 people",
            "role": "user"
        }
        
        with patch.object(ai_service, 'send_chat_message') as mock_send:
            mock_response = {
                "id": 1,
                "session_id": session_id,
                "role": ChatMessageRole.ASSISTANT,
                "content": "Great! I'd love to help you plan a birthday party for 20 people.",
                "created_at": datetime.utcnow()
            }
            mock_send.return_value = mock_response
            
            response = client.post(
                f"/api/v1/ai-chat/sessions/{session_id}/messages",
                json=message_data,
                headers={"Authorization": f"Bearer {test_user.access_token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["role"] == ChatMessageRole.ASSISTANT
            assert "birthday party" in data["content"].lower()

    def test_complete_chat_session(self, client: TestClient, test_user: User, db: Session):
        """Test completing a chat session and creating an event"""
        session_id = "test-session-id"
        
        with patch.object(ai_service, 'complete_chat_session') as mock_complete:
            mock_result = {
                "event_id": 123,
                "session_id": session_id,
                "success": True,
                "message": "Event created successfully!"
            }
            mock_complete.return_value = mock_result
            
            response = client.post(
                f"/api/v1/ai-chat/sessions/{session_id}/complete",
                headers={"Authorization": f"Bearer {test_user.access_token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["event_id"] == 123

    def test_get_user_chat_sessions(self, client: TestClient, test_user: User, db: Session):
        """Test getting all chat sessions for a user"""
        # Create test sessions in database
        session1 = AIChatSession(
            session_id="session-1",
            user_id=test_user.id,
            title="Birthday Party",
            status=ChatSessionStatus.ACTIVE
        )
        session2 = AIChatSession(
            session_id="session-2",
            user_id=test_user.id,
            title="Wedding Planning",
            status=ChatSessionStatus.COMPLETED
        )
        
        db.add_all([session1, session2])
        db.commit()
        
        response = client.get(
            "/api/v1/ai-chat/sessions",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert any(session["title"] == "Birthday Party" for session in data)
        assert any(session["title"] == "Wedding Planning" for session in data)

    def test_unauthorized_access(self, client: TestClient):
        """Test that unauthorized requests are rejected"""
        response = client.get("/api/v1/ai-chat/sessions")
        assert response.status_code == 401

    def test_session_not_found(self, client: TestClient, test_user: User):
        """Test handling of non-existent session"""
        with patch.object(ai_service, 'get_chat_session') as mock_get:
            mock_get.side_effect = ValueError("Session not found")
            
            response = client.get(
                "/api/v1/ai-chat/sessions/non-existent-id",
                headers={"Authorization": f"Bearer {test_user.access_token}"}
            )
            
            assert response.status_code == 404


class TestAIChatService:
    """Test AI Chat Service functionality"""

    @pytest.mark.asyncio
    async def test_create_chat_session_service(self, db: Session, test_user: User):
        """Test creating a chat session through the service"""
        session_data = ChatSessionCreate(
            title="Test Party",
            description="Planning a test party"
        )
        
        with patch('openai.ChatCompletion.acreate') as mock_openai:
            mock_openai.return_value = AsyncMock()
            mock_openai.return_value.choices = [
                AsyncMock(message=AsyncMock(content="Hello! I'd love to help you plan your test party."))
            ]
            
            result = await ai_service.create_chat_session(db, test_user.id, session_data)
            
            assert result.title == "Test Party"
            assert result.status == ChatSessionStatus.ACTIVE
            assert len(result.messages) == 1
            assert result.messages[0].role == ChatMessageRole.ASSISTANT

    @pytest.mark.asyncio
    async def test_send_chat_message_service(self, db: Session, test_user: User):
        """Test sending a message through the service"""
        # Create a session first
        session = AIChatSession(
            session_id="test-session",
            user_id=test_user.id,
            title="Test Session",
            status=ChatSessionStatus.ACTIVE
        )
        db.add(session)
        db.commit()
        
        message_data = ChatMessageCreate(
            content="I need help with decorations",
            role=ChatMessageRole.USER
        )
        
        with patch('openai.ChatCompletion.acreate') as mock_openai:
            mock_openai.return_value = AsyncMock()
            mock_openai.return_value.choices = [
                AsyncMock(message=AsyncMock(content="I can help you with decoration ideas!"))
            ]
            
            result = await ai_service.send_chat_message(
                db, "test-session", test_user.id, message_data
            )
            
            assert result.role == ChatMessageRole.ASSISTANT
            assert "decoration" in result.content.lower()

    @pytest.mark.asyncio
    async def test_complete_chat_session_service(self, db: Session, test_user: User):
        """Test completing a chat session through the service"""
        # Create a session with messages
        session = AIChatSession(
            session_id="test-session",
            user_id=test_user.id,
            title="Birthday Party",
            status=ChatSessionStatus.ACTIVE,
            event_data={
                "title": "John's Birthday",
                "event_type": "birthday",
                "guest_count": 20
            }
        )
        db.add(session)
        db.commit()
        
        # Add some messages
        message1 = AIChatMessage(
            session_id=session.id,
            role=ChatMessageRole.USER,
            content="I want to plan a birthday party"
        )
        message2 = AIChatMessage(
            session_id=session.id,
            role=ChatMessageRole.ASSISTANT,
            content="Great! Let me help you plan that birthday party."
        )
        db.add_all([message1, message2])
        db.commit()
        
        with patch.object(ai_service, '_create_event_from_chat') as mock_create_event:
            mock_create_event.return_value = {"id": 123, "title": "John's Birthday"}
            
            result = await ai_service.complete_chat_session(
                db, "test-session", test_user.id
            )
            
            assert result["success"] is True
            assert result["event_id"] == 123
            
            # Check that session is marked as completed
            updated_session = db.query(AIChatSession).filter(
                AIChatSession.session_id == "test-session"
            ).first()
            assert updated_session.status == ChatSessionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_parse_ai_response(self, db: Session):
        """Test parsing AI response for event data extraction"""
        ai_response = """
        Based on our conversation, here's what I understand about your event:
        
        **Event Details:**
        - Title: Sarah's 25th Birthday Bash
        - Type: Birthday Party
        - Date: March 15, 2024
        - Time: 7:00 PM
        - Location: Downtown Community Center
        - Guest Count: 30 people
        - Budget: $500
        
        **Additional Notes:**
        - Theme: Retro 90s
        - Decorations: Neon colors, disco ball
        - Food: Pizza and cake
        """
        
        result = ai_service._parse_ai_response(ai_response)
        
        assert result["title"] == "Sarah's 25th Birthday Bash"
        assert result["event_type"] == "birthday"
        assert result["guest_count"] == 30
        assert result["budget"] == 500
        assert "retro 90s" in result["description"].lower()

    def test_generate_chat_response_prompt(self):
        """Test generating appropriate prompts for chat responses"""
        messages = [
            {"role": "user", "content": "I want to plan a wedding"},
            {"role": "assistant", "content": "I'd love to help with your wedding planning!"},
            {"role": "user", "content": "We're thinking of having it outdoors"}
        ]
        
        prompt = ai_service._generate_chat_response_prompt(messages)
        
        assert "wedding" in prompt.lower()
        assert "outdoors" in prompt.lower()
        assert "event planning" in prompt.lower()