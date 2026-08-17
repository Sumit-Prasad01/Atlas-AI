"""Optional decorator for cache-aside service methods."""

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from backend.app.cache.service import CacheService

Params = ParamSpec("Params")
Result = TypeVar("Result")


def cached(
    key_builder: Callable[Params, str],
    *,
    ttl_seconds: int,
    lock_ttl_seconds: int | None = None,
) -> Callable[[Callable[Params, Awaitable[Result]]], Callable[Params, Awaitable[Result]]]:
    """Cache a coroutine when it receives a `cache` keyword argument."""

    def decorator(function: Callable[Params, Awaitable[Result]]) -> Callable[Params, Awaitable[Result]]:
        @wraps(function)
        async def wrapped(*args: Params.args, **kwargs: Params.kwargs) -> Result:
            cache = kwargs.get("cache")
            if not isinstance(cache, CacheService):
                return await function(*args, **kwargs)

            key = key_builder(*args, **kwargs)
            return await cache.get_or_set(
                key,
                lambda: function(*args, **kwargs),
                ttl_seconds=ttl_seconds,
                lock_ttl_seconds=lock_ttl_seconds,
            )

        return wrapped

    return decorator
