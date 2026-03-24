import pytest
from unittest.mock import Mock
from sqlalchemy.orm import Session

from app.services.contact_service import ContactService
from app.services.sms_service import SMSService


def test_contact_service_normalizes_nigeria_local_mobile_number():
    service = ContactService(Mock(spec=Session))
    assert service._clean_phone_number("09166128503") == "+2349166128503"


def test_contact_service_normalizes_nigeria_number_without_plus():
    service = ContactService(Mock(spec=Session))
    assert service._clean_phone_number("2349166128503") == "+2349166128503"


def test_contact_service_keeps_international_e164_numbers():
    service = ContactService(Mock(spec=Session))
    assert service._clean_phone_number("+447700900123") == "+447700900123"
    assert service._clean_phone_number("+14155552671") == "+14155552671"


def test_contact_service_rejects_ambiguous_non_nigeria_local_number():
    service = ContactService(Mock(spec=Session))
    with pytest.raises(ValueError):
        service._clean_phone_number("9166128503")


def test_contact_service_phone_validation_matches_normalization_rules():
    service = ContactService(Mock(spec=Session))
    assert service._is_valid_phone_number("09166128503") is True
    assert service._is_valid_phone_number("+447700900123") is True
    assert service._is_valid_phone_number("+14155552671") is True
    assert service._is_valid_phone_number("9166128503") is False


def test_sms_service_normalizes_nigeria_local_mobile_number():
    sms_service = SMSService()
    assert sms_service._clean_phone_number("09166128503") == "+2349166128503"


def test_sms_service_rejects_ambiguous_non_nigeria_local_number():
    sms_service = SMSService()
    with pytest.raises(ValueError):
        sms_service._clean_phone_number("9166128503")
