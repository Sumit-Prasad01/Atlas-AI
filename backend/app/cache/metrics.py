"""In-process cache metrics suitable for initial observability."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CacheMetricsSnapshot:
    """A point-in-time view of cache behavior."""

    hits: int
    misses: int
    errors: int
    writes: int
    invalidations: int
    lock_contention: int

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


@dataclass
class CacheMetrics:
    """Track cache events without storing sensitive key or value data."""

    hits: int = 0
    misses: int = 0
    errors: int = 0
    writes: int = 0
    invalidations: int = 0
    lock_contention: int = 0

    def snapshot(self) -> CacheMetricsSnapshot:
        return CacheMetricsSnapshot(
            hits=self.hits,
            misses=self.misses,
            errors=self.errors,
            writes=self.writes,
            invalidations=self.invalidations,
            lock_contention=self.lock_contention,
        )
