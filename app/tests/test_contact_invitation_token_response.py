from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.contact_models import ContactInviteStatus
from app.services.contact_service import ContactService


def test_token_response_allows_rebinding_for_pre_response_status():
    db = Mock(spec=Session)
    service = ContactService(db)
    invitation = SimpleNamespace(
        invitation_token="token-1",
        status=ContactInviteStatus.SENT,
        expires_at=datetime.utcnow() + timedelta(hours=1),
        recipient_id=999,
        event_id=None,
        created_at=datetime.utcnow(),
        responded_at=None,
    )

    query_mock = Mock()
    query_mock.filter.return_value.first.return_value = invitation
    db.query.return_value = query_mock

    updated = service.respond_to_invitation_token("token-1", 123, "accepted")

    assert updated.status == ContactInviteStatus.ACCEPTED
    assert updated.recipient_id == 123
    assert updated.responded_at is not None
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(invitation)


def test_token_response_blocks_rebinding_after_response_status():
    db = Mock(spec=Session)
    service = ContactService(db)
    invitation = SimpleNamespace(
        invitation_token="token-2",
        status=ContactInviteStatus.ACCEPTED,
        expires_at=datetime.utcnow() + timedelta(hours=1),
        recipient_id=999,
        event_id=None,
        created_at=datetime.utcnow(),
        responded_at=datetime.utcnow(),
    )

    query_mock = Mock()
    query_mock.filter.return_value.first.return_value = invitation
    db.query.return_value = query_mock

    with pytest.raises(HTTPException) as exc:
        service.respond_to_invitation_token("token-2", 123, "declined")

    assert exc.value.status_code == 403
