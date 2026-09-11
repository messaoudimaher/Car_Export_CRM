"""E.164 Phone Normalization & WhatsApp Identifier Utility (BR-014)."""

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat

from app.core.errors import ValidationException


def normalize_phone_number(raw_phone: str, default_region: str = "TN") -> str:
    """Normalize raw phone number string into ITU-T E.164 standard format.

    Args:
        raw_phone: Input phone number string (e.g. "098123456", "+216 98 123 456").
        default_region: ISO 3166-1 alpha-2 country code default ("TN" for Tunisia).

    Returns:
        str: E.164 formatted phone number (e.g. "+21698123456").

    Raises:
        ValidationException: If input cannot be parsed or is an invalid phone number.
    """
    if not raw_phone or not raw_phone.strip():
        raise ValidationException("Phone number input cannot be empty.")

    cleaned_phone = raw_phone.strip()

    try:
        parsed_number = phonenumbers.parse(cleaned_phone, default_region.upper())
    except NumberParseException as err:
        raise ValidationException(f"Invalid phone number format: '{raw_phone}'.") from err

    if not phonenumbers.is_valid_number(parsed_number):
        # Fallback check: try stripping leading '0' if local number prefix was prepended by user
        if cleaned_phone.startswith("0") and not cleaned_phone.startswith("00"):
            try:
                fallback_parsed = phonenumbers.parse(cleaned_phone[1:], default_region.upper())
                if phonenumbers.is_valid_number(fallback_parsed):
                    return phonenumbers.format_number(fallback_parsed, PhoneNumberFormat.E164)
            except NumberParseException:
                pass

        raise ValidationException(f"Invalid phone number format: '{raw_phone}'.")

    return phonenumbers.format_number(parsed_number, PhoneNumberFormat.E164)


def extract_whatsapp_id(e164_phone: str) -> str:
    """Extract raw Meta WhatsApp identifier (wa_id) from E.164 phone string.

    Args:
        e164_phone: E.164 formatted phone string (e.g. "+21698123456").

    Returns:
        str: Meta wa_id string without leading plus sign (e.g. "21698123456").
    """
    return e164_phone.lstrip("+")
