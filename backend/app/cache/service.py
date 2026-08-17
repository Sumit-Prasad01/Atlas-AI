"""Cache-aside, distributed-lock, and rate-limit operations."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar
from uuid import uuid4

from backend.app.cache.client import RedisError, create_redis_client
from backend.app.cache.locks import DistributedLock
from backend.app.cache.metrics import CacheMetrics, CacheMetricsSnapshot
from backend.app.cache.serializer import CacheSerializer

logger = logging.getLogger(__name__)
Result = TypeVar("Result")

_RELEASE_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


@dataclass(frozen=True)
class RateLimitResult:
    """The result of a windowed rate-limit check."""

    allowed: bool
    remaining: int
    retry_after_seconds: int | None


class CacheService:
    """Access Redis through safe, application-level cache operations."""

    def __init__(
        self,
        *,
        redis_url: str | None = None,
        connect_timeout_seconds: float = 1.0,
        socket_timeout_seconds: float = 1.0,
        client: Any | None = None,
    ) -> None:
        self._redis_url = redis_url
        self._connect_timeout_seconds = connect_timeout_seconds
        self._socket_timeout_seconds = socket_timeout_seconds
        self._client = client
        self._available = False
        self.metrics = CacheMetrics()

    @classmethod
    def from_settings(cls, settings: Any) -> "CacheService":
        """Build the cache service from typed application settings."""

        return cls(
            redis_url=settings.redis_url,
            connect_timeout_seconds=settings.redis_connect_timeout_seconds,
            socket_timeout_seconds=settings.redis_socket_timeout_seconds,
        )

    @property
    def available(self) -> bool:
        """Whether Redis responded successfully during the latest operation."""

        return self._available

    async def connect(self) -> bool:
        """Connect lazily and leave the application usable if Redis is down."""

        if self._client is None:
            self._client = create_redis_client(
                self._redis_url,
                connect_timeout_seconds=self._connect_timeout_seconds,
                socket_timeout_seconds=self._socket_timeout_seconds,
            )
        if self._client is None:
            return False

        try:
            await self._client.ping()
        except (RedisError, OSError, TimeoutError) as exc:
            self._mark_unavailable("connect", exc)
            return False

        self._available = True
        logger.info("Redis cache connected")
        return True

    async def close(self) -> None:
        """Close the client when the FastAPI process stops."""

        if self._client is None:
            return
        close = getattr(self._client, "aclose", None)
        if close is not None:
            try:
                await close()
            except (RedisError, OSError, TimeoutError) as exc:
                self._mark_unavailable("close", exc)

    async def get(self, key: str) -> Any | None:
        """Return a decoded cached value or None on a miss/unavailable Redis."""

        client = await self._get_client()
        if client is None:
            return None

        try:
            raw_value = await client.get(key)
        except (RedisError, OSError, TimeoutError) as exc:
            self._mark_unavailable("get", exc)
            return None

        if raw_value is None:
            self.metrics.misses += 1
            return None

        try:
            value = CacheSerializer.loads(raw_value)
        except (TypeError, ValueError) as exc:
            self.metrics.errors += 1
            logger.warning("Failed to deserialize cache value for key category=%s: %s", self._key_category(key), exc)
            await self.delete(key)
            return None

        self.metrics.hits += 1
        return value

    async def set(self, key: str, value: Any, *, ttl_seconds: int) -> bool:
        """Store a JSON value with a positive TTL."""

        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        client = await self._get_client()
        if client is None:
            return False

        try:
            payload = CacheSerializer.dumps(value)
        except (TypeError, ValueError) as exc:
            self.metrics.errors += 1
            logger.warning("Failed to serialize cache value for key category=%s: %s", self._key_category(key), exc)
            return False

        try:
            await client.set(key, payload, ex=ttl_seconds)
        except (RedisError, OSError, TimeoutError) as exc:
            self._mark_unavailable("set", exc)
            return False

        self.metrics.writes += 1
        return True

    async def delete(self, key: str) -> bool:
        """Delete a cache key if Redis is currently available."""

        client = await self._get_client()
        if client is None:
            return False
        try:
            deleted = await client.delete(key)
        except (RedisError, OSError, TimeoutError) as exc:
            self._mark_unavailable("delete", exc)
            return False

        self.metrics.invalidations += int(deleted)
        return bool(deleted)

    async def delete_by_pattern(self, pattern: str) -> int:
        """Delete matching keys in small batches for targeted invalidation."""

        client = await self._get_client()
        if client is None:
            return 0

        deleted_count = 0
        try:
            keys: list[str] = []
            async for key in client.scan_iter(match=pattern, count=100):
                keys.append(key)
                if len(keys) == 100:
                    deleted_count += await client.delete(*keys)
                    keys.clear()
            if keys:
                deleted_count += await client.delete(*keys)
        except (RedisError, OSError, TimeoutError) as exc:
            self._mark_unavailable("delete_by_pattern", exc)
            return deleted_count

        self.metrics.invalidations += deleted_count
        return deleted_count

    async def exists(self, key: str) -> bool:
        """Check whether a cache key exists."""

        client = await self._get_client()
        if client is None:
            return False
        try:
            return bool(await client.exists(key))
        except (RedisError, OSError, TimeoutError) as exc:
            self._mark_unavailable("exists", exc)
            return False

    async def get_or_set(
        self,
        key: str,
        loader: Callable[[], Awaitable[Result]],
        *,
        ttl_seconds: int,
        lock_ttl_seconds: int | None = None,
    ) -> Result:
        """Use cache-aside loading and optional single-flight lock protection."""

        cached_value = await self.get(key)
        if cached_value is not None:
            return cached_value

        if not lock_ttl_seconds:
            return await self._load_and_cache(key, loader, ttl_seconds)

        lock = await self.acquire_lock(f"lock:cache:{key}", ttl_seconds=lock_ttl_seconds)
        async with lock:
            if lock.acquired:
                cached_value = await self.get(key)
                if cached_value is not None:
                    return cached_value
                return await self._load_and_cache(key, loader, ttl_seconds)

        await asyncio.sleep(0.05)
        cached_value = await self.get(key)
        if cached_value is not None:
            return cached_value
        return await self._load_and_cache(key, loader, ttl_seconds)

    async def acquire_lock(self, key: str, *, ttl_seconds: int) -> DistributedLock:
        """Acquire a short-lived distributed lock, degrading safely if offline."""

        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")

        token = str(uuid4())
        client = await self._get_client()
        if client is None:
            return DistributedLock(self, key, token, acquired=True)

        try:
            acquired = bool(await client.set(key, token, nx=True, ex=ttl_seconds))
        except (RedisError, OSError, TimeoutError) as exc:
            self._mark_unavailable("acquire_lock", exc)
            return DistributedLock(self, key, token, acquired=True)

        if not acquired:
            self.metrics.lock_contention += 1
        return DistributedLock(self, key, token, acquired=acquired)

    async def check_rate_limit(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Apply an atomic Redis counter/window rate limit when available."""

        if limit <= 0 or window_seconds <= 0:
            raise ValueError("limit and window_seconds must be positive")

        client = await self._get_client()
        if client is None:
            return RateLimitResult(allowed=True, remaining=limit, retry_after_seconds=None)

        try:
            current_count = int(await client.incr(key))
            if current_count == 1:
                await client.expire(key, window_seconds)
            retry_after = int(await client.ttl(key))
        except (RedisError, OSError, TimeoutError) as exc:
            self._mark_unavailable("check_rate_limit", exc)
            return RateLimitResult(allowed=True, remaining=limit, retry_after_seconds=None)

        return RateLimitResult(
            allowed=current_count <= limit,
            remaining=max(limit - current_count, 0),
            retry_after_seconds=retry_after if current_count > limit and retry_after > 0 else None,
        )

    def metrics_snapshot(self) -> CacheMetricsSnapshot:
        """Return in-process counters for a future observability endpoint."""

        return self.metrics.snapshot()

    async def _get_client(self) -> Any | None:
        if self._available:
            return self._client
        if await self.connect():
            return self._client
        return None

    async def _load_and_cache(
        self,
        key: str,
        loader: Callable[[], Awaitable[Result]],
        ttl_seconds: int,
    ) -> Result:
        value = await loader()
        await self.set(key, value, ttl_seconds=ttl_seconds)
        return value

    async def _release_lock(self, key: str, token: str) -> bool:
        client = await self._get_client()
        if client is None:
            return False
        try:
            released = await client.eval(_RELEASE_LOCK_SCRIPT, 1, key, token)
        except (RedisError, OSError, TimeoutError) as exc:
            self._mark_unavailable("release_lock", exc)
            return False
        return bool(released)

    def _mark_unavailable(self, operation: str, exc: Exception) -> None:
        self._available = False
        self.metrics.errors += 1
        logger.warning("Redis cache %s failed; falling back to durable stores: %s", operation, exc)

    @staticmethod
    def _key_category(key: str) -> str:
        parts = key.split(":")
        return parts[2] if len(parts) > 2 and parts[0] == "cache" else parts[0]
