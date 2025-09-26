import pytest
from fastapi.testclient import TestClient
from app.tests.conftest import EventFactory

class TestEventEndpoints:
    """Test cases for event API endpoints."""
    
    def test_create_event(self, authenticated_client: TestClient, test_event_data):
        """Test creating a new event."""
        response = authenticated_client.post("/api/v1/events/", json=test_event_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == test_event_data["title"]
        assert data["description"] == test_event_data["description"]
        assert data["event_type"] == test_event_data["event_type"]
        assert data["status"] == "draft"
        assert "id" in data
        assert "creator" in data
    
    def test_create_event_unauthorized(self, client: TestClient, test_event_data):
        """Test creating event without authentication."""
        response = client.post("/api/v1/events/", json=test_event_data)
        assert response.status_code == 401
    
    def test_create_event_invalid_dates(self, authenticated_client: TestClient, test_event_data):
        """Test creating event with invalid date range."""
        # Set end date before start date
        test_event_data["end_datetime"] = test_event_data["start_datetime"]
        
        response = authenticated_client.post("/api/v1/events/", json=test_event_data)
        assert response.status_code == 400
    
    def test_get_events(self, authenticated_client: TestClient):
        """Test getting list of events."""
        # Create a test event first
        event_data = {
            "title": "Test Event",
            "description": "Test Description",
            "event_type": "party",
            "start_datetime": "2024-12-31T20:00:00",
            "end_datetime": "2024-12-31T23:00:00"
        }
        authenticated_client.post("/api/v1/events/", json=event_data)
        
        response = authenticated_client.get("/api/v1/events/")
        
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "total" in data
        assert len(data["events"]) >= 1
    
    def test_get_my_events(self, authenticated_client: TestClient, test_event_data):
        """Test getting current user's events."""
        # Create an event
        create_response = authenticated_client.post("/api/v1/events/", json=test_event_data)
        assert create_response.status_code == 201
        
        # Get user's events
        response = authenticated_client.get("/api/v1/events/my")
        
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert len(data["events"]) >= 1
    
    def test_get_event_by_id(self, authenticated_client: TestClient, test_event_data):
        """Test getting specific event by ID."""
        # Create an event
        create_response = authenticated_client.post("/api/v1/events/", json=test_event_data)
        event_id = create_response.json()["id"]
        
        # Get the event
        response = authenticated_client.get(f"/api/v1/events/{event_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == event_id
        assert data["title"] == test_event_data["title"]
    
    def test_get_event_not_found(self, authenticated_client: TestClient):
        """Test getting non-existent event."""
        response = authenticated_client.get("/api/v1/events/99999")
        assert response.status_code == 404
    
    def test_update_event(self, authenticated_client: TestClient, test_event_data):
        """Test updating an event."""
        # Create an event
        create_response = authenticated_client.post("/api/v1/events/", json=test_event_data)
        event_id = create_response.json()["id"]
        
        # Update the event
        update_data = {
            "title": "Updated Event Title",
            "description": "Updated description"
        }
        
        response = authenticated_client.put(f"/api/v1/events/{event_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Event Title"
        assert data["description"] == "Updated description"
    
    def test_delete_event(self, authenticated_client: TestClient, test_event_data):
        """Test deleting an event."""
        # Create an event
        create_response = authenticated_client.post("/api/v1/events/", json=test_event_data)
        event_id = create_response.json()["id"]
        
        # Delete the event
        response = authenticated_client.delete(f"/api/v1/events/{event_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify event is deleted
        get_response = authenticated_client.get(f"/api/v1/events/{event_id}")
        assert get_response.status_code == 404
    
    def test_search_events(self, authenticated_client: TestClient):
        """Test searching events."""
        # Create a test event
        event_data = {
            "title": "Searchable Event",
            "description": "This event should be found in search",
            "event_type": "party",
            "start_datetime": "2024-12-31T20:00:00",
            "venue_name": "Search Venue"
        }
        authenticated_client.post("/api/v1/events/", json=event_data)
        
        # Search for the event
        response = authenticated_client.get("/api/v1/events/search?q=Searchable")
        
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        # Should find at least one event
        assert len(data["events"]) >= 1
    
    def test_get_event_stats(self, authenticated_client: TestClient, test_event_data):
        """Test getting event statistics."""
        # Create an event
        create_response = authenticated_client.post("/api/v1/events/", json=test_event_data)
        event_id = create_response.json()["id"]
        
        # Get event stats
        response = authenticated_client.get(f"/api/v1/events/{event_id}/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "rsvp_counts" in data
        assert "task_counts" in data
        assert "total_expenses" in data
    
    def test_invite_users_to_event(self, authenticated_client: TestClient, test_event_data, client):
        """Test inviting users to an event."""
        # Create another user to invite
        user_data = {
            "email": "invitee@example.com",
            "password": "password123",
            "confirm_password": "password123",
            "full_name": "Invitee User"
        }
        register_response = client.post("/api/v1/auth/register", json=user_data)
        invitee_id = register_response.json()["id"]
        
        # Create an event
        create_response = authenticated_client.post("/api/v1/events/", json=test_event_data)
        event_id = create_response.json()["id"]
        
        # Invite the user
        invitation_data = {
            "user_ids": [invitee_id],
            "invitation_message": "Please join our event!",
            "plus_one_allowed": True
        }
        
        response = authenticated_client.post(
            f"/api/v1/events/{event_id}/invitations",
            json=invitation_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert len(data) == 1
        assert data[0]["user_id"] == invitee_id
        assert data[0]["rsvp_status"] == "pending"
    
    def test_create_task_for_event(self, authenticated_client: TestClient, test_event_data, test_task_data):
        """Test creating a task for an event."""
        # Create an event
        create_response = authenticated_client.post("/api/v1/events/", json=test_event_data)
        event_id = create_response.json()["id"]
        
        # Create a task
        response = authenticated_client.post(
            f"/api/v1/events/{event_id}/tasks",
            json=test_task_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == test_task_data["title"]
        assert data["event_id"] == event_id
        assert data["status"] == "todo"
    
    def test_get_event_tasks(self, authenticated_client: TestClient, test_event_data, test_task_data):
        """Test getting tasks for an event."""
        # Create an event
        create_response = authenticated_client.post("/api/v1/events/", json=test_event_data)
        event_id = create_response.json()["id"]
        
        # Create a task
        authenticated_client.post(
            f"/api/v1/events/{event_id}/tasks",
            json=test_task_data
        )
        
        # Get tasks
        response = authenticated_client.get(f"/api/v1/events/{event_id}/tasks")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["title"] == test_task_data["title"]
    
    def test_create_expense_for_event(self, authenticated_client: TestClient, test_event_data, test_expense_data):
        """Test creating an expense for an event."""
        # Create an event
        create_response = authenticated_client.post("/api/v1/events/", json=test_event_data)
        event_id = create_response.json()["id"]
        
        # Create an expense
        response = authenticated_client.post(
            f"/api/v1/events/{event_id}/expenses",
            json=test_expense_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == test_expense_data["title"]
        assert data["amount"] == test_expense_data["amount"]
        assert data["event_id"] == event_id
    
    def test_create_comment_on_event(self, authenticated_client: TestClient, test_event_data):
        """Test creating a comment on an event."""
        # Create an event
        create_response = authenticated_client.post("/api/v1/events/", json=test_event_data)
        event_id = create_response.json()["id"]
        
        # Create a comment
        comment_data = {
            "content": "This is a test comment on the event."
        }
        
        response = authenticated_client.post(
            f"/api/v1/events/{event_id}/comments",
            json=comment_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == comment_data["content"]
        assert data["event_id"] == event_id
    
    def test_create_poll_for_event(self, authenticated_client: TestClient, test_event_data):
        """Test creating a poll for an event."""
        # Create an event
        create_response = authenticated_client.post("/api/v1/events/", json=test_event_data)
        event_id = create_response.json()["id"]
        
        # Create a poll
        poll_data = {
            "title": "What time should we start?",
            "description": "Vote for the best start time",
            "multiple_choice": False,
            "anonymous": False,
            "options": [
                {"text": "7:00 PM"},
                {"text": "8:00 PM"},
                {"text": "9:00 PM"}
            ]
        }
        
        response = authenticated_client.post(
            f"/api/v1/events/{event_id}/polls",
            json=poll_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == poll_data["title"]
        assert data["event_id"] == event_id
        assert len(data["options"]) == 3

class TestEventPermissions:
    """Test event access permissions."""
    
    def test_access_private_event_unauthorized(self, client: TestClient, authenticated_client: TestClient, test_event_data):
        """Test accessing private event without permission."""
        # Create a private event
        test_event_data["is_public"] = False
        create_response = authenticated_client.post("/api/v1/events/", json=test_event_data)
        event_id = create_response.json()["id"]
        
        # Try to access without authentication
        response = client.get(f"/api/v1/events/{event_id}")
        assert response.status_code == 401
    
    def test_edit_event_unauthorized(self, client: TestClient, authenticated_client: TestClient, test_event_data):
        """Test editing event without permission."""
        # Create an event
        create_response = authenticated_client.post("/api/v1/events/", json=test_event_data)
        event_id = create_response.json()["id"]
        
        # Try to edit without authentication
        update_data = {"title": "Unauthorized Update"}
        response = client.put(f"/api/v1/events/{event_id}", json=update_data)
        assert response.status_code == 401
    
    def test_delete_event_unauthorized(self, client: TestClient, authenticated_client: TestClient, test_event_data):
        """Test deleting event without permission."""
        # Create an event
        create_response = authenticated_client.post("/api/v1/events/", json=test_event_data)
        event_id = create_response.json()["id"]
        
        # Try to delete without authentication
        response = client.delete(f"/api/v1/events/{event_id}")
        assert response.status_code == 401