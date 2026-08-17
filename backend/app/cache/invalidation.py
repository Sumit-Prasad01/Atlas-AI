"""Domain-oriented invalidation helpers for future application services."""

from backend.app.cache.keys import CacheKeys
from backend.app.cache.service import CacheService


class CacheInvalidator:
    """Invalidate related cache entries after durable data changes."""

    def __init__(self, cache: CacheService) -> None:
        self._cache = cache

    async def task_changed(self, user_id: str, project_id: str | None = None) -> None:
        await self._cache.delete_by_pattern(CacheKeys.tasks_pattern(user_id))
        await self._cache.delete(CacheKeys.dashboard(user_id))
        if project_id:
            await self._cache.delete(CacheKeys.project(project_id))

    async def note_changed(self, user_id: str, project_id: str | None = None) -> None:
        await self._cache.delete(CacheKeys.dashboard(user_id))
        await self._cache.delete_by_pattern(f"{CacheKeys.prefix}:search:{user_id}:*")
        if project_id:
            await self._cache.delete(CacheKeys.project(project_id))

    async def document_reindexed(self, user_id: str, document_id: str) -> None:
        await self._cache.delete(CacheKeys.document_summary(user_id, document_id))
        await self._cache.delete_by_pattern(f"{CacheKeys.prefix}:rag:{user_id}:*")
