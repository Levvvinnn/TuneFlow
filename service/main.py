"""
TuneFlow Service Under Test — the FastAPI + PostgreSQL service that the
multi-agent optimization loop benchmarks and reconfigures in real time.

Endpoints:
  GET  /health                  — liveness probe
  GET  /users/{id}              — point lookup
  GET  /users/sample-ids        — random sample for load test setup
  GET  /products/search         — cached full-text search (cache-sensitive)
  GET  /products/sample-ids     — random sample for load test setup
  POST /orders/                 — create order (write with batch product lookup)
  GET  /orders/{id}             — fetch order with items (join)
  GET  /orders/sample-ids       — random sample for load test setup
  POST /admin/reconfigure       — hot-swap DB connection pool (zero-downtime)
  GET  /admin/config            — current runtime config
  GET  /admin/db-stats          — live pg_stat_activity connection counts
  POST /admin/reset-data        — truncate and reseed test data
"""
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from database import init_db
from routers import users, products, orders, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="TuneFlow Service Under Test", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
