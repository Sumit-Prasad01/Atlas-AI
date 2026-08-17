"""Cache-service tests that run without a live Redis server."""

import asyncio
from fnmatch import fnmatch

from backend.app.cache.invalidation import CacheInvalidator
from backend.app.cache.keys import CacheKeys
from backend.app.cache.service import CacheService


class FakeRedis:
    """Small async Redis substitute for cache-service unit tests."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool:
        if nx and key in self.values:
            return False
        self.values[key] = value
        if ex is not None:
            self.ttls[key] = ex
        return True

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self.values:
                del self.values[key]
                self.ttls.pop(key, None)
                deleted += 1
        return deleted

    async def exists(self, key: str) -> int:
        return int(key in self.values)

    async def scan_iter(self, *, match: str, count: int):
        del count
        for key in list(self.values):
            if fnmatch(key, match):
                yield key

    async def incr(self, key: str) -> int:
        count = int(self.values.get(key, "0")) + 1
        self.values[key] = str(count)
        return count

    async def expire(self, key: str, seconds: int) -> bool:
        self.ttls[key] = seconds
        return True

    async def ttl(self, key: str) -> int:
        return self.ttls.get(key, -1)

    async def eval(self, _: str, __: int, key: str, token: str) -> int:
        if self.values.get(key) != token:
            return 0
        await self.delete(key)
        return 1


class UnavailableRedis:
    """Client that simulates an unavailable Redis server."""

    async def ping(self) -> bool:
        raise OSError("Redis is unavailable")


def test_cache_aside_loads_once_and_reuses_value() -> None:
    async def scenario() -> None:
        cache = CacheService(client=FakeRedis())
        await cache.connect()
        calls = 0

        async def loader() -> dict[str, str]:
            nonlocal calls
            calls += 1
            return {"value": "fresh"}

        key = CacheKeys.tasks("user-1", {"status": "open"})
        assert await cache.get_or_set(key, loader, ttl_seconds=60, lock_ttl_seconds=5) == {"value": "fresh"}
        assert await cache.get_or_set(key, loader, ttl_seconds=60, lock_ttl_seconds=5) == {"value": "fresh"}
        assert calls == 1
        assert cache.metrics_snapshot().hit_rate > 0

    asyncio.run(scenario())


def test_invalidation_removes_related_task_and_dashboard_keys() -> None:
    async def scenario() -> None:
        cache = CacheService(client=FakeRedis())
        await cache.connect()
        invalidator = CacheInvalidator(cache)
        user_id = "user-1"

        task_key = CacheKeys.tasks(user_id, {"status": "open"})
        dashboard_key = CacheKeys.dashboard(user_id)
        await cache.set(task_key, {"items": []}, ttl_seconds=60)
        await cache.set(dashboard_key, {"today": []}, ttl_seconds=60)

        await invalidator.task_changed(user_id)

        assert await cache.get(task_key) is None
        assert await cache.get(dashboard_key) is None

    asyncio.run(scenario())


def test_rate_limit_rejects_requests_after_the_limit() -> None:
    async def scenario() -> None:
        cache = CacheService(client=FakeRedis())
        await cache.connect()
        key = CacheKeys.rate_limit("user-1", "chat")

        first = await cache.check_rate_limit(key, limit=2, window_seconds=60)
        second = await cache.check_rate_limit(key, limit=2, window_seconds=60)
        third = await cache.check_rate_limit(key, limit=2, window_seconds=60)

        assert first.allowed and first.remaining == 1
        assert second.allowed and second.remaining == 0
        assert not third.allowed and third.retry_after_seconds == 60

    asyncio.run(scenario())


def test_cache_outage_falls_back_to_the_loader() -> None:
    async def scenario() -> None:
        cache = CacheService(client=UnavailableRedis())
        await cache.connect()

        async def loader() -> dict[str, bool]:
            return {"from_durable_store": True}

        value = await cache.get_or_set("cache:v1:test:fallback", loader, ttl_seconds=60)

        assert value == {"from_durable_store": True}
        assert not cache.available
        assert cache.metrics_snapshot().errors > 0

    asyncio.run(scenario())
