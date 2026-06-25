import asyncio
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import get_config

DATABASE_URL = os.getenv(
    "SERVICE_DB_URL",
    "postgresql+asyncpg://service_user:service_pass@localhost:5432/service_db",
).replace("postgresql://", "postgresql+asyncpg://")

# Module-level engine/session — replaced atomically during hot-swap
_engine = None
_session_factory = None
_engine_lock = asyncio.Lock()


def _build_engine(cfg=None):
    if cfg is None:
        cfg = get_config()
    timeout_secs = cfg.query_timeout_ms / 1000
    return create_async_engine(
        DATABASE_URL,
        pool_size=cfg.pool_size,
        max_overflow=cfg.pool_max_overflow,
        pool_pre_ping=True,
        connect_args={
            "command_timeout": timeout_secs,
            "server_settings": {
                "statement_timeout": str(cfg.query_timeout_ms),
            },
        },
        echo=False,
    )


def _build_session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db():
    global _engine, _session_factory
    _engine = _build_engine()
    _session_factory = _build_session_factory(_engine)


async def hot_swap_pool(new_cfg) -> dict:
    """Dispose old engine, build new one with new config, return pool info."""
    global _engine, _session_factory
    async with _engine_lock:
        old_engine = _engine
        new_engine = _build_engine(new_cfg)
        new_factory = _build_session_factory(new_engine)

        # Drain in-flight: give active connections a moment to finish
        if old_engine is not None:
            await asyncio.sleep(0.5)
            await old_engine.dispose()

        _engine = new_engine
        _session_factory = new_factory

    return {
        "pool_size": new_cfg.pool_size,
        "max_overflow": new_cfg.pool_max_overflow,
    }


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = _session_factory
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


class Base(DeclarativeBase):
    pass
