import asyncio
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from cache import reset_product_cache
from config import ServiceConfig, get_config, swap_config
from database import hot_swap_pool, get_session
from models import User, Product, Order, OrderItem

router = APIRouter(prefix="/admin", tags=["admin"])


class ReconfigurePayload(BaseModel):
    pool_size: Optional[int] = Field(None, ge=1, le=100)
    pool_max_overflow: Optional[int] = Field(None, ge=0, le=200)
    query_timeout_ms: Optional[int] = Field(None, ge=100, le=30000)
    cache_ttl_seconds: Optional[int] = Field(None, ge=1, le=3600)
    batch_size: Optional[int] = Field(None, ge=1, le=10000)
    retry_interval_ms: Optional[int] = Field(None, ge=10, le=5000)


class ReconfigureResponse(BaseModel):
    status: str
    previous_config: dict
    new_config: dict
    pool_info: dict


@router.post("/reconfigure", response_model=ReconfigureResponse)
async def reconfigure(payload: ReconfigurePayload):
    """Hot-swap DB connection pool and in-memory config without restart."""
    current = get_config()
    prev_dict = current.to_dict()

    new_cfg = ServiceConfig(**prev_dict)
    updates = payload.model_dump(exclude_none=True)
    new_cfg.update(**updates)

    # Swap config object first so new requests use new settings immediately
    swap_config(new_cfg)

    # Hot-swap the connection pool (drains old, creates new)
    pool_info = await hot_swap_pool(new_cfg)

    # Reset product cache TTL if changed
    if "cache_ttl_seconds" in updates:
        reset_product_cache(new_cfg.cache_ttl_seconds)

    return ReconfigureResponse(
        status="ok",
        previous_config=prev_dict,
        new_config=new_cfg.to_dict(),
        pool_info=pool_info,
    )


@router.post("/reset-data")
async def reset_data():
    """Truncate all test tables and reseed with fresh data."""
    from seed import seed_database
    async with get_session() as session:
        # Truncate in dependency order
        await session.execute(text("DELETE FROM order_items"))
        await session.execute(text("DELETE FROM orders"))
        await session.execute(text("DELETE FROM products"))
        await session.execute(text("DELETE FROM users"))
        await session.commit()

    await seed_database()
    return {"status": "ok", "message": "Data reset and reseeded"}


@router.get("/config")
async def get_current_config():
    return get_config().to_dict()


@router.get("/db-stats")
async def get_db_stats():
    """Return pg_stat_activity connection counts — cheap DB-side metric."""
    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT state, count(*) FROM pg_stat_activity "
                "WHERE datname = current_database() "
                "GROUP BY state"
            )
        )
        rows = result.fetchall()
        stats = {row[0] or "unknown": row[1] for row in rows}
        total_result = await session.execute(
            text(
                "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
            )
        )
        total = total_result.scalar()
        return {"connection_states": stats, "total_connections": total}
