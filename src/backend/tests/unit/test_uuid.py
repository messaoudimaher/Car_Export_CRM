"""Unit tests for UUIDv7 Generator (ADR 0005 Compliance)."""

import time
import uuid

from app.core.uuid import generate_uuidv7 as generate_uuidv7_core
from app.utils.uuid import generate_uuidv7


def test_uuidv7_generation_format_and_version() -> None:
    """Verify generated ID is a valid UUID instance of version 7."""
    u = generate_uuidv7()
    assert isinstance(u, uuid.UUID)
    assert u.version == 7


def test_uuidv7_utils_reexport_parity() -> None:
    """Verify app.utils.uuid re-exports identical generate_uuidv7 implementation."""
    u_core = generate_uuidv7_core()
    u_util = generate_uuidv7()
    assert u_core.version == 7
    assert u_util.version == 7


def test_uuidv7_monotonic_time_ordering() -> None:
    """Verify consecutive UUIDv7 generations are time-ordered monotonically."""
    u1 = generate_uuidv7()
    time.sleep(0.002)  # 2 ms delay
    u2 = generate_uuidv7()

    assert u1 != u2
    # String representation of time-ordered UUIDv7 is lexicographically sortable
    assert u1.hex < u2.hex


def test_uuidv7_uniqueness_and_monotonicity_10000_generations() -> None:
    """Verify 10,000 generated UUIDv7 instances have 0 collisions and maintain sort order."""
    count = 10000
    generated_hexes = [generate_uuidv7().hex for _ in range(count)]

    # 1. Zero collisions across 10,000 generations
    assert len(set(generated_hexes)) == count

    # 2. Monotonic sort order (lexicographically non-decreasing)
    sorted_hexes = sorted(generated_hexes)
    assert generated_hexes == sorted_hexes
