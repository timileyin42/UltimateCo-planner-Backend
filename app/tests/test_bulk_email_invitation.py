from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from limits.storage import MemoryStorage
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.main import app
from app.core.deps import get_current_user
from app.core.database import get_db
from app.models.user_models import User
from app.models.event_models import Event


ENDPOINT = "/api/v1/contacts/invitations/bulk-email"


@pytest.fixture(autouse=True)
def use_memory_rate_limiter():
    """Replace Redis-backed limiter with in-memory for all tests in this module."""
    memory_limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")
    original = app.state.limiter
    app.state.limiter = memory_limiter
    yield
    app.state.limiter = original


def _make_user():
    user = MagicMock(spec=User)
    user.id = 1
    user.full_name = "Test User"
    user.email = "testuser@example.com"
    return user


def _make_event(event_id=10):
    event = MagicMock(spec=Event)
    event.id = event_id
    event.title = "Birthday Bash"
    event.description = "A great party"
    event.venue_name = "The Lounge"
    event.venue_address = "123 Main St"
    event.start_datetime = datetime.utcnow() + timedelta(days=7)
    return event


def _mock_db(event=None, existing_contact=None, recipient_user=None):
    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        if model.__name__ == "Event":
            q.filter.return_value.first.return_value = event
        elif model.__name__ == "UserContact":
            q.filter.return_value.first.return_value = existing_contact
        elif model.__name__ == "User":
            q.filter.return_value.first.return_value = recipient_user
        else:
            q.filter.return_value.first.return_value = None
        return q

    db.query.side_effect = query_side_effect
    # flush assigns a fake id to new ORM objects
    def flush_side_effect():
        for call in db.add.call_args_list:
            obj = call[0][0]
            if not getattr(obj, "id", None):
                obj.id = 999
    db.flush.side_effect = flush_side_effect
    return db


@pytest.fixture
def client_with_auth():
    user = _make_user()
    db = _mock_db()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    with TestClient(app) as c:
        yield c, user, db

    app.dependency_overrides.clear()


@pytest.fixture
def client_with_auth_and_event():
    user = _make_user()
    event = _make_event()
    db = _mock_db(event=event)

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    with TestClient(app) as c:
        yield c, user, event, db

    app.dependency_overrides.clear()


class TestBulkEmailInvitation:

    def test_requires_authentication(self):
        with TestClient(app) as c:
            response = c.post(ENDPOINT, json={"emails": ["a@test.com"]})
        assert response.status_code == 401

    @patch("app.services.email_service.EmailService.send_email", new_callable=AsyncMock, return_value=True)
    @patch("app.services.email_service.EmailService.render_template", return_value="<html>invite</html>")
    def test_general_invite_no_event(self, mock_render, mock_send, client_with_auth):
        client, _, _ = client_with_auth
        response = client.post(ENDPOINT, json={
            "emails": ["alice@example.com", "bob@example.com"],
            "message": "Join me!",
            "auto_add_to_contacts": False
        })
        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 2
        assert data["success_count"] == 2
        assert data["failure_count"] == 0
        assert len(data["sent"]) == 2
        assert mock_send.call_count == 2
        # Each sent entry should carry the invite_url
        for item in data["sent"]:
            assert "invite_url" in item
            assert "/invite/" in item["invite_url"]

    @patch("app.services.email_service.EmailService.send_email", new_callable=AsyncMock, return_value=True)
    @patch("app.services.email_service.EmailService.render_template", return_value="<html>event invite</html>")
    def test_event_invite_uses_event_invitation_template(self, mock_render, mock_send, client_with_auth_and_event):
        client, _, event, _ = client_with_auth_and_event
        response = client.post(ENDPOINT, json={
            "emails": ["guest@example.com"],
            "event_id": event.id,
            "message": "Come to my party!"
        })
        assert response.status_code == 201
        assert response.json()["success_count"] == 1

        mock_render.assert_called_once()
        template_name, context = mock_render.call_args[0]
        assert template_name == "event_invitation.html"
        assert context["event_title"] == event.title
        assert context["invitation_message"] == "Come to my party!"

    @patch("app.services.email_service.EmailService.send_email", new_callable=AsyncMock, return_value=True)
    @patch("app.services.email_service.EmailService.render_template", return_value="<html>welcome</html>")
    def test_general_invite_uses_welcome_template(self, mock_render, mock_send, client_with_auth):
        client, _, _ = client_with_auth
        response = client.post(ENDPOINT, json={"emails": ["newuser@example.com"]})
        assert response.status_code == 201
        template_name, _ = mock_render.call_args[0]
        assert template_name == "welcome.html"

    def test_invalid_event_id_returns_404(self, client_with_auth):
        client, _, _ = client_with_auth
        response = client.post(ENDPOINT, json={
            "emails": ["someone@example.com"],
            "event_id": 99999
        })
        assert response.status_code == 404
        assert response.json()["detail"] == "Event not found"

    @patch("app.services.email_service.EmailService.send_email", new_callable=AsyncMock, return_value=False)
    @patch("app.services.email_service.EmailService.render_template", return_value="<html>invite</html>")
    def test_failed_delivery_tracked(self, mock_render, mock_send, client_with_auth):
        client, _, _ = client_with_auth
        response = client.post(ENDPOINT, json={"emails": ["bad@example.com"]})
        assert response.status_code == 201
        data = response.json()
        assert data["failure_count"] == 1
        assert data["success_count"] == 0
        assert data["failed"][0]["email"] == "bad@example.com"
        assert "reason" in data["failed"][0]

    @patch("app.services.email_service.EmailService.send_email", new_callable=AsyncMock, side_effect=[True, False, True])
    @patch("app.services.email_service.EmailService.render_template", return_value="<html>invite</html>")
    def test_partial_success(self, mock_render, mock_send, client_with_auth):
        client, _, _ = client_with_auth
        response = client.post(ENDPOINT, json={
            "emails": ["a@example.com", "b@example.com", "c@example.com"]
        })
        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 3
        assert data["success_count"] == 2
        assert data["failure_count"] == 1

    def test_empty_emails_rejected(self, client_with_auth):
        client, _, _ = client_with_auth
        response = client.post(ENDPOINT, json={"emails": []})
        assert response.status_code == 422
