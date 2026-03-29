"""Tests for bulk email invitation feature."""
from types import SimpleNamespace
from unittest.mock import Mock, patch, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.contact_models import ContactInviteStatus
from app.services.contact_service import ContactService


def _make_sender():
    return SimpleNamespace(id=1, full_name="Alice Smith", email="alice@example.com")


def _make_db_with_sender(sender):
    """Return a mock DB that returns the sender for User queries and None for everything else."""
    db = Mock(spec=Session)

    contact_mock = Mock()
    contact_mock.id = 10

    def query_side_effect(model):
        from app.models.user_models import User
        from app.models.contact_models import UserContact
        from app.models.event_models import Event

        q = Mock()
        if model is User:
            inner = Mock()
            inner.first.return_value = sender
            q.filter.return_value = inner
        elif model is UserContact:
            inner = Mock()
            inner.first.return_value = None  # no existing contact
            q.filter.return_value = inner
        elif model is Event:
            inner = Mock()
            inner.first.return_value = None
            q.filter.return_value = inner
        else:
            q.filter.return_value = Mock(first=Mock(return_value=None))
        return q

    db.query.side_effect = query_side_effect

    # flush assigns id to new ORM objects
    def flush_side_effect():
        pass

    db.flush.side_effect = flush_side_effect
    db.add.return_value = None
    db.commit.return_value = None

    return db


class TestBulkSendEmailInvitations:

    def test_successful_send(self):
        sender = _make_sender()
        db = _make_db_with_sender(sender)

        with patch.object(
            ContactService,
            "__init__",
            lambda self, db: (
                setattr(self, "db", db),
                setattr(self, "sms_service", Mock()),
                setattr(self, "email_service", Mock(
                    send_contact_invite_email_sync=Mock(return_value=True)
                )),
            ) and None,
        ):
            service = ContactService.__new__(ContactService)
            service.db = db
            service.sms_service = Mock()
            service.email_service = Mock()
            service.email_service.send_contact_invite_email_sync = Mock(return_value=True)

            result = service.bulk_send_email_invitations(
                sender_id=1,
                emails=["bob@example.com", "carol@example.com"],
            )

        assert result["total"] == 2
        assert result["success_count"] == 2
        assert result["failure_count"] == 0
        assert len(result["sent"]) == 2
        assert len(result["failed"]) == 0
        assert result["sent"][0]["email"] == "bob@example.com"
        assert result["sent"][1]["email"] == "carol@example.com"

    def test_email_delivery_failure_marks_failed(self):
        sender = _make_sender()
        db = _make_db_with_sender(sender)

        service = ContactService.__new__(ContactService)
        service.db = db
        service.sms_service = Mock()
        service.email_service = Mock()
        service.email_service.send_contact_invite_email_sync = Mock(return_value=False)

        result = service.bulk_send_email_invitations(
            sender_id=1,
            emails=["bob@example.com"],
        )

        assert result["success_count"] == 0
        assert result["failure_count"] == 1
        assert result["failed"][0]["email"] == "bob@example.com"
        assert "failed" in result["failed"][0]["error"].lower()

    def test_sender_not_found_raises_404(self):
        db = Mock(spec=Session)
        q = Mock()
        q.filter.return_value.first.return_value = None
        db.query.return_value = q

        service = ContactService.__new__(ContactService)
        service.db = db
        service.sms_service = Mock()
        service.email_service = Mock()

        with pytest.raises(HTTPException) as exc:
            service.bulk_send_email_invitations(sender_id=999, emails=["x@example.com"])

        assert exc.value.status_code == 404

    def test_partial_failure_continues(self):
        """One email fails to send, but others still succeed."""
        sender = _make_sender()
        db = _make_db_with_sender(sender)

        call_count = {"n": 0}

        def alternating_send(**kwargs):
            call_count["n"] += 1
            return call_count["n"] % 2 == 1  # True for 1st, False for 2nd

        service = ContactService.__new__(ContactService)
        service.db = db
        service.sms_service = Mock()
        service.email_service = Mock()
        service.email_service.send_contact_invite_email_sync = Mock(side_effect=alternating_send)

        result = service.bulk_send_email_invitations(
            sender_id=1,
            emails=["good@example.com", "bad@example.com"],
        )

        assert result["total"] == 2
        assert result["success_count"] == 1
        assert result["failure_count"] == 1

    def test_empty_email_list_raises_validation(self):
        """Schema should reject empty list before the service is called."""
        from pydantic import ValidationError
        from app.schemas.contact_schemas import BulkEmailInvitationCreate

        with pytest.raises(ValidationError):
            BulkEmailInvitationCreate(emails=[])

    def test_too_many_emails_raises_validation(self):
        from pydantic import ValidationError
        from app.schemas.contact_schemas import BulkEmailInvitationCreate

        with pytest.raises(ValidationError):
            BulkEmailInvitationCreate(emails=[f"user{i}@example.com" for i in range(51)])

    def test_invalid_email_raises_validation(self):
        from pydantic import ValidationError
        from app.schemas.contact_schemas import BulkEmailInvitationCreate

        with pytest.raises(ValidationError):
            BulkEmailInvitationCreate(emails=["not-an-email"])

    def test_send_contact_invite_email_sync_success(self):
        """EmailService.send_contact_invite_email_sync returns True on successful Resend call."""
        from app.services.email_service import EmailService

        service = EmailService()

        with patch("app.services.email_service.settings") as mock_settings, \
             patch("app.services.email_service.resend") as mock_resend, \
             patch.object(service, "render_template", return_value="<html>invite</html>"), \
             patch.object(service, "is_configured", return_value=True):

            mock_settings.DEEP_LINK_BASE_URL = "https://app.planetal.com"
            mock_settings.FRONTEND_URL = "https://app.planetal.com"
            mock_resend.Emails.send.return_value = {"id": "email-id-123"}

            result = service.send_contact_invite_email_sync(
                to_email="bob@example.com",
                inviter_name="Alice",
                invitation_token="tok-abc",
            )

        assert result is True

    def test_send_contact_invite_email_sync_not_configured(self):
        """Returns False immediately when Resend is not configured."""
        from app.services.email_service import EmailService

        service = EmailService()
        with patch.object(service, "is_configured", return_value=False):
            result = service.send_contact_invite_email_sync(
                to_email="bob@example.com",
                inviter_name="Alice",
                invitation_token="tok-abc",
            )

        assert result is False

    def test_send_contact_invite_email_sync_resend_error(self):
        """Returns False and doesn't raise when Resend throws."""
        from app.services.email_service import EmailService

        service = EmailService()

        with patch("app.services.email_service.resend") as mock_resend, \
             patch.object(service, "render_template", return_value="<html>x</html>"), \
             patch.object(service, "is_configured", return_value=True):

            mock_resend.Emails.send.side_effect = Exception("Resend API down")

            result = service.send_contact_invite_email_sync(
                to_email="bob@example.com",
                inviter_name="Alice",
                invitation_token="tok-abc",
            )

        assert result is False
