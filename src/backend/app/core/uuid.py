"""UUIDv7 Generator Utility strictly complying with ADR 0005."""

import uuid

import uuid6


def generate_uuidv7() -> uuid.UUID:
    """Generate a time-ordered UUIDv7 conforming to RFC 9562 & ADR 0005.

    UUIDv7 embeds a 48-bit UNIX millisecond timestamp followed by 74 bits
    of pseudo-randomness, offering optimal B-Tree index insertion locality
    and preventing ID enumeration attacks.

    Returns:
        uuid.UUID: A 128-bit UUIDv7 instance.
    """
    u = uuid6.uuid7()
    # Cast uuid6 object to Python standard library uuid.UUID for typing compatibility
    return uuid.UUID(bytes=u.bytes)
