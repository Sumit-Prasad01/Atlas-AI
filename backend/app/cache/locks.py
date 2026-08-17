"""Redis distributed-lock value object."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.cache.service import CacheService


@dataclass
class DistributedLock:
    """A short-lived lock with a unique ownership token."""

    service: "CacheService"
    key: str
    token: str
    acquired: bool

    async def release(self) -> bool:
        """Release the lock only if this caller still owns it."""

        if not self.acquired:
            return False
        released = await self.service._release_lock(self.key, self.token)
        self.acquired = False
        return released

    async def __aenter__(self) -> "DistributedLock":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.release()
