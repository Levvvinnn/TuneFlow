import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from config import get_config
from database import get_session
from models import Order, OrderItem, Product, User

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity: int = 1


class OrderCreate(BaseModel):
    user_id: uuid.UUID
    items: List[OrderItemCreate]


class OrderItemResponse(BaseModel):
    id: str
    product_id: str
    quantity: int
    unit_price: float


class OrderResponse(BaseModel):
    id: str
    user_id: str
    status: str
    total_amount: float
    items: List[OrderItemResponse]


@router.get("/sample-ids")
async def sample_order_ids(limit: int = Query(50, le=200)):
    async with get_session() as session:
        result = await session.execute(select(Order.id).order_by(func.random()).limit(limit))
        return [str(row[0]) for row in result.fetchall()]


@router.post("/", response_model=OrderResponse, status_code=201)
async def create_order(payload: OrderCreate):
    cfg = get_config()

    async with get_session() as session:
        # Verify user exists
        user = await session.get(User, payload.user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        # Fetch products in batch
        product_ids = [item.product_id for item in payload.items]
        result = await session.execute(
            select(Product).where(Product.id.in_(product_ids))
        )
        products_map = {p.id: p for p in result.scalars().all()}

        total = 0.0
        order = Order(
            user_id=payload.user_id,
            status="pending",
            total_amount=0.0,
        )
        session.add(order)
        await session.flush()

        items_out = []
        for item_in in payload.items:
            product = products_map.get(item_in.product_id)
            if product is None:
                raise HTTPException(status_code=404, detail=f"Product {item_in.product_id} not found")
            unit_price = float(product.price)
            total += unit_price * item_in.quantity
            oi = OrderItem(
                order_id=order.id,
                product_id=item_in.product_id,
                quantity=item_in.quantity,
                unit_price=unit_price,
            )
            session.add(oi)
            items_out.append(
                OrderItemResponse(
                    id=str(oi.id) if oi.id else "",
                    product_id=str(item_in.product_id),
                    quantity=item_in.quantity,
                    unit_price=unit_price,
                )
            )

        order.total_amount = total
        await session.flush()

        return OrderResponse(
            id=str(order.id),
            user_id=str(order.user_id),
            status=order.status,
            total_amount=total,
            items=items_out,
        )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: uuid.UUID):
    async with get_session() as session:
        result = await session.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        return OrderResponse(
            id=str(order.id),
            user_id=str(order.user_id),
            status=order.status,
            total_amount=float(order.total_amount),
            items=[
                OrderItemResponse(
                    id=str(i.id),
                    product_id=str(i.product_id),
                    quantity=i.quantity,
                    unit_price=float(i.unit_price),
                )
                for i in order.items
            ],
        )
