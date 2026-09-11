"""Unit tests for UUIDv7 Generator (ADR 0005 Compliance)."""

import time
import uuid

from app.core.uuid import generate_uuidv7


def test_uuidv7_generation_format_and_version() -> None:
    """Verify generated ID is a valid UUID instance of version 7."""
    u = generate_uuidv7()
    assert isinstance(u, uuid.UUID)
    assert u.version == 7


def test_uuidv7_monotonic_time_ordering() -> None:
    """Verify consecutive UUIDv7 generations are time-ordered monotonically."""
    u1 = generate_uuidv7()
    time.sleep(0.002)  # 2 ms delay
    u2 = generate_uuidv7()

    assert u1 != u2
    # String representation of time-ordered UUIDv7 is lexicographically sortable
    assert u1.hex < u2.hex
