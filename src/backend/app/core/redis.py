"""Redis Connection & ARQ Task Enqueueing Helpers (SEC-011)."""

import uuid

from arq.connections import ArqRedis, RedisSettings, create_pool

from app.core.config import settings
from app.core.logging import logger


def get_redis_settings() -> RedisSettings:
    """Return ARQ RedisSettings instance initialized from application configuration."""
    return RedisSettings.from_dsn(settings.REDIS_URL)


_redis_pool: ArqRedis | None = None


async def get_redis_pool() -> ArqRedis:
    """Return singleton ArqRedis pool connection instance."""
    global _redis_pool
    if _redis_pool is None:
        redis_settings = get_redis_settings()
        _redis_pool = await create_pool(redis_settings)
    return _redis_pool


async def close_redis_pool() -> None:
    """Close active ArqRedis pool connection on shutdown."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None


async def enqueue_inbound_message_job(
    message_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> str | None:
    """Enqueue process_inbound_message job into ARQ Redis queue.

    Args:
        message_id: InboundMessage UUID primary key.
        tenant_id: Tenant UUID primary key context.

    Returns:
        str | None: Job ID if enqueued successfully, or None in fallback/dev mode.
    """
    try:
        pool = await get_redis_pool()
        job = await pool.enqueue_job(
            "process_inbound_message",
            message_id=str(message_id),
            tenant_id=str(tenant_id),
        )
        job_id = job.job_id if job else None
        logger.info(
            "Enqueued inbound message processing job",
            extra={"message_id": str(message_id), "tenant_id": str(tenant_id), "job_id": job_id},
        )
        return job_id
    except Exception as err:
        logger.warning(
            "Redis queue offline or enqueue failed, falling back cleanly",
            extra={"message_id": str(message_id), "tenant_id": str(tenant_id), "error": str(err)},
        )
        return None
