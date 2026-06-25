import time
from threading import RLock
from typing import Any, Optional


class TTLCache:
    """Thread-safe in-memory TTL cache."""

    def __init__(self, ttl_seconds: int = 60, maxsize: int = 1024):
        self._store: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl_seconds
        self._maxsize = maxsize
        self._lock = RLock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._store) >= self._maxsize:
                # Evict oldest
                oldest = min(self._store, key=lambda k: self._store[k][1])
                del self._store[oldest]
            self._store[key] = (value, time.monotonic() + self._ttl)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def resize(self, ttl_seconds: int) -> None:
        with self._lock:
            self._ttl = ttl_seconds


# Global product search cache — TTL reset on reconfigure
_product_cache = TTLCache(ttl_seconds=60)


def get_product_cache() -> TTLCache:
    return _product_cache


def reset_product_cache(ttl_seconds: int) -> None:
    _product_cache.clear()
    _product_cache.resize(ttl_seconds)
