# TuneFlow Architecture

## System Overview

TuneFlow consists of two logical halves connected by the Orchestrator API.

### Left half: Agent Intelligence Layer

```
Browser (Dashboard)
    │  React + recharts
    │  3 views: Run / History / Compare
    ▼
Orchestrator API  (FastAPI, :8080)
    │  POST /runs → start multi-agent or baseline run
    │  GET /runs/{id}/status → live iteration count + score
    │  GET /runs/{id}/history → full per-iteration data
    │  GET /compare → both run_ids for side-by-side
    ▼
LangGraph Graph  (multi-agent)
    │
    ├── Config Agent  ──────────────────────────── qwen-plus
    │     iteration 1: propose initial config
    │     later: targeted change from Judge analysis
    │
    ├── Judge Agent  ───────────────────────────── qwen-plus (text)
    │     apply config via /admin/reconfigure         + qwen-vl-plus (vision)
    │     run k6 load test (2–3 repeats)
    │     text diagnosis (bottleneck, severity, trend)
    │     vision diagnosis (chart image → visual pattern)
    │     veto unsafe Optimizer proposals
    │
    ├── Optimizer Agent  ───────────────────────── qwen-max
    │     propose next config change
    │     one revision on veto (round limit = 1, enforced in code)
    │
    ├── Veto Node
    │     check safety constraints
    │     allow 1 revision, then forced fallback
    │
    ├── Persist Node
    │     save iteration to Persistence DB
    │
    └── Terminate Node
          target_hit → stop
          plateau (N consecutive no-improvement) → stop
          max_iterations → stop

Baseline God-Agent  (separate loop, same infra)
    │  single qwen-plus call per iteration: diagnose+propose+decide
    └── same termination logic as multi-agent (fair comparison)
```

### Right half: Infrastructure Layer

```
FastAPI Service Under Test  (:8000)
    │  Endpoints:
    │    GET  /users/sample-ids
    │    GET  /users/{id}
    │    GET  /products/search?q=...&category=...
    │    POST /orders/
    │    GET  /health
    │    POST /admin/reconfigure   ← hot-swap endpoint
    │    POST /admin/reset-data    ← truncate + reseed
    │    GET  /admin/config
    │    GET  /admin/db-stats
    ▼
Service PostgreSQL  (:5432)
    │  Tables: users (2k), products (5k), orders (10k), order_items
    │  Extensions: pg_trgm (fuzzy search)
    └── ApsaraDB for PostgreSQL on Alibaba Cloud (production)

Persistence PostgreSQL  (:5433)
    │  Tables: runs, iterations
    │  Stores: per-iteration config, metrics, Judge analysis (text+vision),
    │           Optimizer proposal, veto events, final decisions
    └── Separate from service DB to prevent cross-contamination

k6 Load Test
    │  loadtest.js: 50–200 VUs, realistic mixed CRUD
    │    40% product search (cache-sensitive)
    │    25% get user (point lookup)
    │    20% create order (write + batch product fetch)
    │    15% get order (read with join)
    └── runner.py: triggers k6, parses JSON summary → LoadTestMetrics
```

## Data Flow (one multi-agent iteration)

```
1. Config Agent proposes {pool_size: N, cache_ttl: T, ...}
2. Judge Agent:
   a. POST /admin/reconfigure → pool drains, new engine created
   b. k6 run × 2 repeats → averaged metrics (p95, p99, rps, err_rate)
   c. GET /admin/db-stats → connection count
   d. Text call (qwen-plus): structured bottleneck diagnosis
   e. Render Matplotlib chart → vision call (qwen-vl-plus): visual pattern
   f. Combine text + vision into unified diagnosis
3. Optimizer Agent (qwen-max): propose next config change
4. Veto Node: check safety constraints
   → if violated: Optimizer revises (1 retry max, then forced fallback)
   → if safe: accept as final_decision
5. Persist Node: save all iteration data to Persistence DB
6. Terminate Node: check target_hit / plateau / max_iterations
   → if stop: mark run finished
   → if continue: iteration_number++, loop back to Config Agent
```

## Comparison with Baseline

The baseline god-agent follows the same data flow but compresses steps 2–3 into
a single Qwen call that does diagnose + propose in one shot, using qwen-plus with
no inter-agent negotiation. This gives the dashboard's Compare tab a fair head-to-head
convergence comparison.

## Architecture Diagram Image

**TODO:** Generate `docs/architecture.png` from the above using draw.io, Mermaid Live,
or Excalidraw. The image should show the two logical halves with labeled arrows for:
- Dashboard ↔ Orchestrator (HTTP REST)
- Orchestrator → LangGraph nodes (function calls)
- Agents ↔ Qwen Cloud (HTTPS API)
- Judge Agent → Service /admin/reconfigure (HTTP)
- Judge Agent → k6 subprocess (shell)
- Service → Service DB (asyncpg)
- Persist Node → Persistence DB (asyncpg)
- ECS → ApsaraDB (internal VPC)
