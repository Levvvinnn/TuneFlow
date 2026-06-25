"""Seed the service DB with enough data to stress pool and query performance."""
import asyncio
import os
import random
import sys
import uuid
from datetime import datetime

from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

fake = Faker()

DATABASE_URL = os.getenv(
    "SERVICE_DB_URL",
    "postgresql+asyncpg://service_user:service_pass@localhost:5432/service_db",
).replace("postgresql://", "postgresql+asyncpg://")

CATEGORIES = ["electronics", "clothing", "books", "home", "sports", "food", "toys", "beauty"]
NUM_USERS = 2000
NUM_PRODUCTS = 5000
NUM_ORDERS = 10000
ITEMS_PER_ORDER = (1, 5)


async def seed_database():
    engine = create_async_engine(DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with factory() as session:
        # Enable pg_trgm extension for fuzzy search
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await session.commit()

    # Create tables
    from database import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with factory() as session:
        print(f"Seeding {NUM_USERS} users...")
        user_ids = []
        for i in range(0, NUM_USERS, 500):
            batch_users = []
            for _ in range(min(500, NUM_USERS - i)):
                uid = uuid.uuid4()
                user_ids.append(uid)
                batch_users.append({
                    "id": uid,
                    "username": fake.unique.user_name(),
                    "email": fake.unique.email(),
                    "full_name": fake.name(),
                })
            await session.execute(
                text(
                    "INSERT INTO users (id, username, email, full_name) "
                    "VALUES (:id, :username, :email, :full_name) ON CONFLICT DO NOTHING"
                ),
                batch_users,
            )
            await session.commit()

        print(f"Seeding {NUM_PRODUCTS} products...")
        product_ids = []
        for i in range(0, NUM_PRODUCTS, 500):
            batch_products = []
            for _ in range(min(500, NUM_PRODUCTS - i)):
                pid = uuid.uuid4()
                product_ids.append(pid)
                batch_products.append({
                    "id": pid,
                    "name": fake.catch_phrase(),
                    "description": fake.paragraph(nb_sentences=3),
                    "price": round(random.uniform(1.99, 999.99), 2),
                    "category": random.choice(CATEGORIES),
                    "stock_quantity": random.randint(0, 500),
                })
            await session.execute(
                text(
                    "INSERT INTO products (id, name, description, price, category, stock_quantity) "
                    "VALUES (:id, :name, :description, :price, :category, :stock_quantity) ON CONFLICT DO NOTHING"
                ),
                batch_products,
            )
            await session.commit()

        print(f"Seeding {NUM_ORDERS} orders...")
        for i in range(0, NUM_ORDERS, 200):
            batch_orders = []
            batch_items = []
            for _ in range(min(200, NUM_ORDERS - i)):
                oid = uuid.uuid4()
                uid = random.choice(user_ids)
                n_items = random.randint(*ITEMS_PER_ORDER)
                total = 0.0
                for _ in range(n_items):
                    pid = random.choice(product_ids)
                    qty = random.randint(1, 3)
                    price = round(random.uniform(1.99, 999.99), 2)
                    total += price * qty
                    batch_items.append({
                        "id": uuid.uuid4(),
                        "order_id": oid,
                        "product_id": pid,
                        "quantity": qty,
                        "unit_price": price,
                    })
                batch_orders.append({
                    "id": oid,
                    "user_id": uid,
                    "status": random.choice(["pending", "processing", "shipped", "delivered"]),
                    "total_amount": round(total, 2),
                })
            await session.execute(
                text(
                    "INSERT INTO orders (id, user_id, status, total_amount) "
                    "VALUES (:id, :user_id, :status, :total_amount) ON CONFLICT DO NOTHING"
                ),
                batch_orders,
            )
            await session.execute(
                text(
                    "INSERT INTO order_items (id, order_id, product_id, quantity, unit_price) "
                    "VALUES (:id, :order_id, :product_id, :quantity, :unit_price) ON CONFLICT DO NOTHING"
                ),
                batch_items,
            )
            await session.commit()

    await engine.dispose()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed_database())
