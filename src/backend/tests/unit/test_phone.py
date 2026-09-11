"""Unit tests for E.164 phone normalization and WhatsApp ID utilities (BR-014)."""

import pytest

from app.core.errors import ValidationException
from app.utils.phone import extract_whatsapp_id, normalize_phone_number


def test_normalize_tunisian_phone_formats() -> None:
    """Verify various Tunisian phone number input formats normalize to +216 E.164 standard."""
    assert normalize_phone_number("098123456", "TN") == "+21698123456"
    assert normalize_phone_number("98123456", "TN") == "+21698123456"
    assert normalize_phone_number("+216 98 123 456", "TN") == "+21698123456"
    assert normalize_phone_number("0021698123456", "TN") == "+21698123456"
    assert normalize_phone_number(" 98 123 456 ", "TN") == "+21698123456"


def test_normalize_french_phone_formats() -> None:
    """Verify French phone number input formats normalize to +33 E.164 standard."""
    assert normalize_phone_number("0612345678", "FR") == "+33612345678"
    assert normalize_phone_number("+33 6 12 34 56 78", "TN") == "+33612345678"
    assert normalize_phone_number("0033612345678", "TN") == "+33612345678"


def test_normalize_german_phone_formats() -> None:
    """Verify German phone number input formats normalize to +49 E.164 standard."""
    assert normalize_phone_number("015112345678", "DE") == "+4915112345678"
    assert normalize_phone_number("+49 151 12345678", "TN") == "+4915112345678"
    assert normalize_phone_number("004915112345678", "TN") == "+4915112345678"


def test_normalize_international_phone_formats() -> None:
    """Verify UAE, UK, and US international formats normalize correctly."""
    assert normalize_phone_number("+971 50 123 4567", "TN") == "+971501234567"
    assert normalize_phone_number("+44 7911 123456", "TN") == "+447911123456"
    assert normalize_phone_number("+1 202 555 0143", "TN") == "+12025550143"


def test_normalize_invalid_phone_formats_raises_validation_exception() -> None:
    """Verify invalid phone number strings raise ValidationException (HTTP 400)."""
    with pytest.raises(ValidationException, match="Phone number input cannot be empty."):
        normalize_phone_number("")

    with pytest.raises(ValidationException, match="Phone number input cannot be empty."):
        normalize_phone_number("   ")

    with pytest.raises(ValidationException, match="Invalid phone number format"):
        normalize_phone_number("123", "TN")

    with pytest.raises(ValidationException, match="Invalid phone number format"):
        normalize_phone_number("invalid_phone", "TN")

    with pytest.raises(ValidationException, match="Invalid phone number format"):
        normalize_phone_number("+2160000000000000", "TN")


def test_extract_whatsapp_id() -> None:
    """Verify WhatsApp wa_id extraction strips leading plus sign."""
    assert extract_whatsapp_id("+21698123456") == "21698123456"
    assert extract_whatsapp_id("+33612345678") == "33612345678"
    assert extract_whatsapp_id("+12025550143") == "12025550143"
