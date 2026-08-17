"""Namespaced and privacy-scoped Redis key builders."""

import hashlib
import json
from typing import Any


class CacheKeys:
    """Build predictable keys for cache, rate-limit, lock, and job state."""

    prefix = "cache:v1"

    @classmethod
    def dashboard(cls, user_id: str) -> str:
        return cls._cache_key("dashboard", user_id)

    @classmethod
    def tasks(cls, user_id: str, filters: dict[str, Any] | None = None) -> str:
        return cls._cache_key("tasks", user_id, cls.digest(filters or {}))

    @classmethod
    def tasks_pattern(cls, user_id: str) -> str:
        return cls._cache_key("tasks", user_id, "*")

    @classmethod
    def project(cls, project_id: str) -> str:
        return cls._cache_key("project", project_id)

    @classmethod
    def search(cls, user_id: str, query: str, filters: dict[str, Any] | None = None) -> str:
        return cls._cache_key("search", user_id, cls.digest({"query": query, "filters": filters or {}}))

    @classmethod
    def rag(
        cls,
        user_id: str,
        query: str,
        index_version: str,
        project_id: str | None = None,
    ) -> str:
        return cls._cache_key(
            "rag",
            user_id,
            cls.digest({"query": query, "project_id": project_id, "index_version": index_version}),
        )

    @classmethod
    def document_summary(cls, user_id: str, document_id: str) -> str:
        return cls._cache_key("summary", user_id, document_id)

    @classmethod
    def url(cls, user_id: str, url: str) -> str:
        return cls._cache_key("url", user_id, cls.digest(url))

    @classmethod
    def session(cls, session_id: str) -> str:
        return f"session:{session_id}"

    @classmethod
    def rate_limit(cls, user_id: str, endpoint: str) -> str:
        return f"rate_limit:user:{user_id}:{cls.digest(endpoint)}"

    @classmethod
    def lock(cls, resource_type: str, resource_id: str) -> str:
        return f"lock:{resource_type}:{resource_id}"

    @classmethod
    def job(cls, job_id: str) -> str:
        return f"job:{job_id}"

    @classmethod
    def digest(cls, value: Any) -> str:
        serialized = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:24]

    @classmethod
    def _cache_key(cls, category: str, *parts: str) -> str:
        return ":".join((cls.prefix, category, *map(str, parts)))
