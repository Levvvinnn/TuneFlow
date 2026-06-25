import os
import threading
from dataclasses import dataclass, field, asdict


@dataclass
class ServiceConfig:
    pool_size: int = int(os.getenv("INITIAL_POOL_SIZE", "5"))
    pool_max_overflow: int = 10
    query_timeout_ms: int = int(os.getenv("INITIAL_QUERY_TIMEOUT_MS", "5000"))
    cache_ttl_seconds: int = int(os.getenv("INITIAL_CACHE_TTL_SECONDS", "60"))
    batch_size: int = int(os.getenv("INITIAL_BATCH_SIZE", "100"))
    retry_interval_ms: int = int(os.getenv("INITIAL_RETRY_INTERVAL_MS", "100"))

    def to_dict(self) -> dict:
        return asdict(self)

    def update(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)


# Global mutable config — lock protects concurrent reads during hot-swap
_lock = threading.RLock()
_current_config = ServiceConfig()


def get_config() -> ServiceConfig:
    with _lock:
        return _current_config


def swap_config(new_cfg: ServiceConfig) -> ServiceConfig:
    global _current_config
    with _lock:
        _current_config = new_cfg
        return _current_config
