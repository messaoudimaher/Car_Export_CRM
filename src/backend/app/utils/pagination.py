"""Cursor Pagination Encoding & Decoding Utility (ADR 0009)."""

import base64
import json
from datetime import datetime
from uuid import UUID

from app.core.errors import ValidationException


def encode_cursor(created_at: datetime, record_id: UUID) -> str:
    """Encode created_at timestamp and UUID primary key into an opaque URL-safe cursor.

    Args:
        created_at: UTC timestamp of record.
        record_id: UUID primary key of record.

    Returns:
        str: Base64 URL-safe encoded cursor string.
    """
    payload = {
        "created_at": created_at.isoformat(),
        "id": str(record_id),
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    return encoded


def decode_cursor(cursor_str: str) -> tuple[datetime, UUID]:
    """Decode an opaque URL-safe base64 cursor into created_at timestamp and record UUID.

    Args:
        cursor_str: Opaque base64 encoded cursor string.

    Returns:
        tuple[datetime, UUID]: Decoded (created_at, record_id) tuple.

    Raises:
        ValidationException: If cursor string is malformed or invalid.
    """
    if not cursor_str or not cursor_str.strip():
        raise ValidationException("Pagination cursor cannot be empty.")

    try:
        decoded_json = base64.urlsafe_b64decode(cursor_str.strip().encode("utf-8")).decode("utf-8")
        data = json.loads(decoded_json)
        created_at = datetime.fromisoformat(data["created_at"])
        record_id = UUID(str(data["id"]))
        return created_at, record_id
    except Exception as err:
        raise ValidationException("Invalid pagination cursor parameter.") from err
