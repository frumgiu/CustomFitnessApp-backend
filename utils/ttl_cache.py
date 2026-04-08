import time
from typing import Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    """Cache in-memoria con TTL. Thread-safe per app single-user con uvicorn single-worker."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._store: dict[int, tuple[float, T]] = {}
        self.ttl = ttl_seconds

    def get(self, key: int) -> T | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.time() - ts > self.ttl:
            del self._store[key]
            return None
        return value

    def set(self, key: int, value: T) -> None:
        self._store[key] = (time.time(), value)
