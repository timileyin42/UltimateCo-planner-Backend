from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.main import app
from app.core.deps import get_current_user
from app.core.database import get_db
from app.models.user_models import User


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


def _bulk_email_result(emails, success=True):
    """Build the dict that ContactService.bulk_send_email_invitations returns."""
    sent = [{"email": e, "invitation_id": 100 + i} for i, e in enumerate(emails)] if success else []
    failed = [] if success else [{"email": e, "error": "Email delivery failed"} for e in emails]
    return {
        "sent": sent,
        "failed": failed,
        "total": len(emails),
        "success_count": len(sent),
        "failure_count": len(failed),
    }


@pytest.fixture
def client_with_auth():
    user = _make_user()
    db = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    with TestClient(app) as c:
        yield c, user, db

    app.dependency_overrides.clear()


class TestBulkEmailInvitation:

    def test_requires_authentication(self):
        with TestClient(app) as c:
            response = c.post(ENDPOINT, json={"emails": ["a@test.com"]})
        assert response.status_code == 401

    @patch("app.services.contact_service.ContactService.bulk_send_email_invitations")
    def test_general_invite_no_event(self, mock_bulk, client_with_auth):
        client, _, _ = client_with_auth
        emails = ["alice@example.com", "bob@example.com"]
        mock_bulk.return_value = _bulk_email_result(emails)

        response = client.post(ENDPOINT, json={
            "emails": emails,
            "message": "Join me!",
            "auto_add_to_contacts": False
        })
        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 2
        assert data["success_count"] == 2
        assert data["failure_count"] == 0
        assert len(data["sent"]) == 2
        mock_bulk.assert_called_once()

    @patch("app.services.contact_service.ContactService.bulk_send_email_invitations")
    def test_event_invite_passes_event_id(self, mock_bulk, client_with_auth):
        client, _, _ = client_with_auth
        emails = ["guest@example.com"]
        mock_bulk.return_value = _bulk_email_result(emails)

        response = client.post(ENDPOINT, json={
            "emails": emails,
            "event_id": 42,
            "message": "Come to my party!"
        })
        assert response.status_code == 201
        call_kwargs = mock_bulk.call_args[1]
        assert call_kwargs["event_id"] == 42
        assert call_kwargs["message"] == "Come to my party!"

    @patch("app.services.contact_service.ContactService.bulk_send_email_invitations")
    def test_failed_delivery_tracked(self, mock_bulk, client_with_auth):
        client, _, _ = client_with_auth
        emails = ["bad@example.com"]
        mock_bulk.return_value = _bulk_email_result(emails, success=False)

        response = client.post(ENDPOINT, json={"emails": emails})
        assert response.status_code == 201
        data = response.json()
        assert data["failure_count"] == 1
        assert data["success_count"] == 0
        assert data["failed"][0]["email"] == "bad@example.com"

    @patch("app.services.contact_service.ContactService.bulk_send_email_invitations")
    def test_partial_success(self, mock_bulk, client_with_auth):
        client, _, _ = client_with_auth
        emails = ["a@example.com", "b@example.com", "c@example.com"]
        mock_bulk.return_value = {
            "sent": [{"email": "a@example.com", "invitation_id": 1},
                     {"email": "c@example.com", "invitation_id": 2}],
            "failed": [{"email": "b@example.com", "error": "failed"}],
            "total": 3,
            "success_count": 2,
            "failure_count": 1,
        }
        response = client.post(ENDPOINT, json={"emails": emails})
        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 3
        assert data["success_count"] == 2
        assert data["failure_count"] == 1

    def test_empty_emails_rejected(self, client_with_auth):
        client, _, _ = client_with_auth
        response = client.post(ENDPOINT, json={"emails": []})
        assert response.status_code == 422

    def test_invalid_email_format_rejected(self, client_with_auth):
        client, _, _ = client_with_auth
        response = client.post(ENDPOINT, json={"emails": ["not-an-email"]})
        assert response.status_code == 422

    @patch("app.services.contact_service.ContactService.bulk_send_email_invitations")
    def test_auto_add_to_contacts_passed(self, mock_bulk, client_with_auth):
        client, _, _ = client_with_auth
        mock_bulk.return_value = _bulk_email_result(["x@example.com"])

        client.post(ENDPOINT, json={
            "emails": ["x@example.com"],
            "auto_add_to_contacts": True
        })
        call_kwargs = mock_bulk.call_args[1]
        assert call_kwargs["auto_add_to_contacts"] is True
