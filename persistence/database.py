import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "PERSISTENCE_DB_URL",
    "postgresql+asyncpg://persist_user:persist_pass@localhost:5433/persistence_db",
).replace("postgresql://", "postgresql+asyncpg://")

_engine = create_async_engine(DATABASE_URL, echo=False, pool_size=5, max_overflow=10)
_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


async def init_persistence_db():
    from models import Base
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_session():
    return _factory()
