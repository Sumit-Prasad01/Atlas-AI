"""Optional async Redis client creation."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from redis import asyncio as redis_asyncio
    from redis.exceptions import RedisError
except ModuleNotFoundError:  # Allows the API to run until the optional dependency is installed.
    redis_asyncio = None

    class RedisError(Exception):
        """Fallback error type used while the Redis package is unavailable."""


def create_redis_client(
    url: str | None,
    *,
    connect_timeout_seconds: float,
    socket_timeout_seconds: float,
) -> Any | None:
    """Create a decoded async Redis client, or return None when disabled."""

    if not url:
        logger.info("Redis cache is disabled because REDIS_URL is not configured")
        return None
    if redis_asyncio is None:
        logger.warning("Redis cache is disabled because the redis package is not installed")
        return None

    return redis_asyncio.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=connect_timeout_seconds,
        socket_timeout=socket_timeout_seconds,
        health_check_interval=30,
    )
