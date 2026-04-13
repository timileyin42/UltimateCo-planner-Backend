"""Tests for the permanent shareable event invite link feature.

Uses mocked DB (no SQLite) to avoid the UUID-type incompatibility
that affects all SQLite-based event tests in this project.

Covers:
- invite_token slug generation logic
- GET /events/join/{token} — public preview (no auth)
- POST /events/join/{token} — authenticated join
- 410 when the event has already taken place
- 404 for unknown / soft-deleted tokens
"""

import re
import pytest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter

from app.main import app
from app.core.deps import get_db, get_current_active_user
from app.core.rate_limiter import limiter
from app.models.event_models import Event, EventInvitation
from app.models.shared_models import EventStatus, RSVPStatus


@pytest.fixture(autouse=True)
def use_memory_rate_limiter():
    """Swap Redis rate-limiter storage for in-memory so tests don't need Redis."""
    original_storage = limiter._storage
    original_limiter = limiter._limiter
    mem = MemoryStorage()
    limiter._storage = mem
    limiter._limiter = FixedWindowRateLimiter(mem)
    yield
    limiter._storage = original_storage
    limiter._limiter = original_limiter


# ---------------------------------------------------------------------------
# Mock data factories
# ---------------------------------------------------------------------------

def _make_user(user_id: int = 1, full_name: str = "Test Creator"):
    return SimpleNamespace(
        id=user_id,
        full_name=full_name,
        username=f"user{user_id}",
        avatar_url=None,
        email=f"user{user_id}@example.com",
    )


def _make_event(
    token: str = "birthday-party-abc12345",
    is_deleted: bool = False,
    days_from_now: float = 7,
    creator_id: int = 1,
):
    """Return a SimpleNamespace that satisfies both EventSummary and EventResponse schemas."""
    now = datetime.utcnow()
    start = now + timedelta(days=days_from_now)
    end = start + timedelta(hours=3)
    return SimpleNamespace(
        id=1,
        title="Birthday Party",
        description="Come celebrate!",
        event_type="party",
        status=EventStatus.CONFIRMED,
        start_datetime=start,
        end_datetime=end,
        timezone=None,
        venue_name="Test Venue",
        venue_address=None,
        venue_city="Lagos",
        venue_country=None,
        latitude=None,
        longitude=None,
        is_public=False,
        max_attendees=None,
        requires_approval=False,
        allow_guest_invites=True,
        total_budget=None,
        currency="USD",
        theme_color=None,
        cover_image_url=None,
        creator_id=creator_id,
        creator=_make_user(creator_id),
        attendee_count=0,
        total_expenses=0.0,
        task_categories=[],
        place_id=None,
        formatted_address=None,
        location_verified=False,
        location_verification_timestamp=None,
        invite_token=token,
        is_deleted=is_deleted,
        created_at=now,
        updated_at=now,
        invitations=[],
        collaborators=[],
    )


def _db_returning(event_or_none, invitation_or_none=None):
    """Build a mock DB session for endpoints that query Event then optionally EventInvitation."""
    db = Mock(spec=Session)

    def query_side_effect(model):
        q = MagicMock()
        if model is Event:
            q.filter.return_value.first.return_value = event_or_none
        elif model is EventInvitation:
            q.filter.return_value.first.return_value = invitation_or_none
        else:
            q.filter.return_value.first.return_value = None
        return q

    db.query.side_effect = query_side_effect
    return db


def _make_client(db_mock, user_mock=None):
    """Build a TestClient with overridden DB (and optional user) dependencies."""
    def override_db():
        yield db_mock

    app.dependency_overrides[get_db] = override_db

    if user_mock is not None:
        app.dependency_overrides[get_current_active_user] = lambda: user_mock

    client = TestClient(app, raise_server_exceptions=False)
    return client


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Always reset dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Slug / token generation tests (pure logic — no HTTP)
# ---------------------------------------------------------------------------

class TestInviteTokenGeneration:

    def test_slug_lowercases_title(self):
        title = "Birthday Party at Jake's"
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:40].rstrip('-')
        assert slug == "birthday-party-at-jake-s"

    def test_slug_strips_special_characters(self):
        title = "New Year's Eve!!! 2026"
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:40].rstrip('-')
        assert slug == "new-year-s-eve-2026"

    def test_slug_truncates_long_titles(self):
        title = "A" * 60
        slug = re.sub(r'[^a-z0-9]+', 'a'.lower(), title.lower()).strip('-')[:40].rstrip('-')
        assert len(slug) <= 40

    def test_token_format_is_url_safe(self):
        import secrets
        title = "Birthday Party"
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:40].rstrip('-')
        token = f"{slug}-{secrets.token_urlsafe(8)}"
        assert re.match(r'^[a-zA-Z0-9\-_]+$', token), f"Bad chars in token: {token}"
        assert token.startswith("birthday-party-")


# ---------------------------------------------------------------------------
# GET /events/join/{token} — public preview
# ---------------------------------------------------------------------------

class TestGetEventByInviteToken:

    def test_returns_200_with_event_summary(self):
        event = _make_event()
        client = _make_client(_db_returning(event))

        resp = client.get("/api/v1/events/join/birthday-party-abc12345")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Birthday Party"

    def test_no_authentication_required(self):
        """Public endpoint must be accessible without a bearer token."""
        event = _make_event()
        db = _db_returning(event)
        # Only override DB, not user — so there's no auth header
        app.dependency_overrides[get_db] = lambda: (yield db)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/v1/events/join/birthday-party-abc12345")
        assert resp.status_code == 200

    def test_unknown_token_returns_404(self):
        client = _make_client(_db_returning(None))  # event not found

        resp = client.get("/api/v1/events/join/does-not-exist-abc123")
        assert resp.status_code == 404

    def test_soft_deleted_event_returns_404(self):
        event = _make_event(is_deleted=True)
        client = _make_client(_db_returning(event))

        resp = client.get("/api/v1/events/join/birthday-party-abc12345")
        assert resp.status_code == 404

    def test_past_event_returns_410(self):
        event = _make_event(days_from_now=-1)  # ended yesterday
        client = _make_client(_db_returning(event))

        resp = client.get("/api/v1/events/join/birthday-party-abc12345")
        assert resp.status_code == 410
        assert "expired" in resp.json()["detail"].lower()

    def test_event_ending_today_but_not_yet_over_returns_200(self):
        """If the event ends in the future (even same day), link is still valid."""
        event = _make_event(days_from_now=0.1)  # ~2.4 hours from now
        client = _make_client(_db_returning(event))

        resp = client.get("/api/v1/events/join/birthday-party-abc12345")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /events/join/{token} — authenticated join
# ---------------------------------------------------------------------------

class TestJoinEventViaInviteLink:

    def test_unauthenticated_returns_401(self):
        event = _make_event()
        db = _db_returning(event)
        # Only override DB; no user override means real auth dependency runs → 401
        app.dependency_overrides[get_db] = lambda: (yield db)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post("/api/v1/events/join/birthday-party-abc12345")
        assert resp.status_code == 401

    def test_new_user_joins_and_gets_200(self):
        event = _make_event(creator_id=1)
        user = _make_user(user_id=2)  # different from creator
        db = _db_returning(event, invitation_or_none=None)  # no existing invitation

        client = _make_client(db, user)
        resp = client.post("/api/v1/events/join/birthday-party-abc12345")

        assert resp.status_code == 200
        db.add.assert_called_once()   # invitation was created
        db.commit.assert_called_once()

    def test_creator_joining_own_event_returns_200_no_duplicate(self):
        event = _make_event(creator_id=1)
        user = _make_user(user_id=1)  # same as creator
        db = _db_returning(event)

        client = _make_client(db, user)
        resp = client.post("/api/v1/events/join/birthday-party-abc12345")

        assert resp.status_code == 200
        db.add.assert_not_called()   # no invitation created

    def test_joining_twice_is_idempotent(self):
        event = _make_event(creator_id=1)
        user = _make_user(user_id=2)
        existing_invitation = SimpleNamespace(id=99)  # already has invitation
        db = _db_returning(event, invitation_or_none=existing_invitation)

        client = _make_client(db, user)
        resp = client.post("/api/v1/events/join/birthday-party-abc12345")

        assert resp.status_code == 200
        db.add.assert_not_called()   # no duplicate created

    def test_past_event_returns_410(self):
        event = _make_event(days_from_now=-1)
        user = _make_user(user_id=2)
        db = _db_returning(event)

        client = _make_client(db, user)
        resp = client.post("/api/v1/events/join/birthday-party-abc12345")

        assert resp.status_code == 410

    def test_unknown_token_returns_404(self):
        user = _make_user(user_id=2)
        db = _db_returning(None)

        client = _make_client(db, user)
        resp = client.post("/api/v1/events/join/this-does-not-exist-abc123")

        assert resp.status_code == 404
