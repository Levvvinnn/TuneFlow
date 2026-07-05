import hashlib
import json
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from sqlalchemy import and_, func, or_, select

from cache import get_product_cache
from config import get_config
from database import get_session
from models import Product

router = APIRouter(prefix="/products", tags=["products"])


class ProductResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    price: float
    category: str
    stock_quantity: int

    model_config = {"from_attributes": True}


@router.get("/sample-ids")
async def sample_product_ids(limit: int = Query(50, le=200)):
    async with get_session() as session:
        result = await session.execute(select(Product.id).order_by(func.random()).limit(limit))
        return [str(row[0]) for row in result.fetchall()]


@router.get("/search", response_model=list[ProductResponse])
async def search_products(
    q: Optional[str] = Query(None, description="Search term"),
    category: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
):
    cfg = get_config()
    cache_key = hashlib.md5(
        json.dumps({"q": q, "category": category, "limit": limit}).encode()
    ).hexdigest()

    cache = get_product_cache()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    async with get_session() as session:
        stmt = select(Product)
        filters = []
        if q:
            filters.append(
                or_(
                    Product.name.ilike(f"%{q}%"),
                    Product.description.ilike(f"%{q}%"),
                )
            )
        if category:
            filters.append(Product.category == category)
        if filters:
            stmt = stmt.where(and_(*filters))
        stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        products = result.scalars().all()

    out = [
        ProductResponse(
            id=str(p.id),
            name=p.name,
            description=p.description,
            price=float(p.price),
            category=p.category,
            stock_quantity=p.stock_quantity,
        )
        for p in products
    ]
    cache.set(cache_key, out)
    return out
