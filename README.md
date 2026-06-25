# TuneFlow — Self-Tuning Backend Performance Agent

**Track 3: Agent Society | Global AI Hackathon Series with Qwen Cloud**

---

## Pitch

TuneFlow is a society of specialized agents that negotiate over backend configuration changes using real load-test ground truth — no simulated metrics, no LLM hallucinating performance numbers. A **Config Agent** proposes configuration changes, a **Judge Agent** applies them, runs real k6 load tests, and diagnoses bottlenecks using both structured metric analysis and Qwen's vision model on rendered performance charts. An **Optimizer Agent** proposes the next targeted change using Qwen's strongest reasoning model, the Judge Agent holds veto power over unsafe proposals (with a code-enforced one-revision round limit so no stuck negotiation can eat the time budget), and a shared termination module stops the loop when target performance is hit, a plateau is detected, or the iteration cap is reached. A single-agent **baseline god-agent** runs the same workload and iteration budget in one Qwen call per iteration, so the dashboard's side-by-side convergence chart provides a direct, measurable efficiency comparison across the exact same ground-truth load tests.

---

## Track

**Track 3: Agent Society** — judged on how agents decompose tasks and assign roles, how they resolve disagreements and execution conflicts, and a measurable efficiency gain over a single-agent baseline.

---

## Scope & Limitations

> **These are deliberate design choices, not caveats to apologize for.**

- **Fixed, modest load only.** TuneFlow measures *relative configuration performance* at a fixed, modest load (50–200 concurrent virtual users). It does not simulate, predict, or extrapolate to production-scale traffic. The goal is a controlled A/B comparison of configuration quality, not a production load-testing tool.

- **Time budget per full run.** Load-test duration × repeats per config (2–3) × number of iterations (10–20) ≈ **15–25 minutes** total. This is intentional — a single hackathon demo run should complete in under 30 minutes.

- **No full service restarts.** All configuration changes happen via the `/admin/reconfigure` hot-swap endpoint, which drains and recreates the DB connection pool in-place. This is a hard constraint of the design — it ensures the load test measures configuration quality, not restart overhead.

- **Separate databases.** The service-under-test DB and the persistence DB (which stores run history) are separate Postgres instances to avoid cross-contamination.

---

## Architecture

```
┌─────────────┐         ┌──────────────────────────────────────────────┐
│  Dashboard  │◄───────►│  Orchestrator API (:8080)                    │
│  React +    │         │  Start run / poll status / fetch history      │
│  recharts   │         └────────────┬─────────────────────────────────┘
└─────────────┘                      │
                                     ▼
                          ┌──────────────────────┐
                          │   LangGraph Graph     │
                          │                       │
                          │  ┌─────────────────┐  │      ┌──────────────────┐
                          │  │  Config Agent   │  │      │   Qwen Cloud     │
                          │  └────────┬────────┘  │◄────►│                  │
                          │           ▼            │      │ text model:      │
                          │  ┌─────────────────┐  │      │   qwen-plus      │
                          │  │  Judge Agent    │  │      │ optimizer model: │
                          │  │  (apply+test+   │  │      │   qwen-max       │
                          │  │   diagnose+veto)│  │      │ vision model:    │
                          │  └────────┬────────┘  │      │   qwen-vl-plus   │
                          │           ▼            │      └──────────────────┘
                          │  ┌─────────────────┐  │
                          │  │ Optimizer Agent │  │
                          │  └────────┬────────┘  │
                          │           ▼            │
                          │  ┌─────────────────┐  │
                          │  │   Veto Node     │  │
                          │  │ (1-round limit) │  │
                          │  └────────┬────────┘  │
                          │           ▼            │
                          │  ┌─────────────────┐  │
                          │  │  Terminate Node │  │
                          │  └─────────────────┘  │
                          └──────────┬────────────┘
                                     │
              ┌──────────────────────┼───────────────────────┐
              ▼                      ▼                        ▼
   ┌─────────────────┐   ┌─────────────────────┐  ┌──────────────────────┐
   │ Service Under   │   │  Persistence DB     │  │  Alibaba Cloud       │
   │ Test (:8000)    │   │  (run/iteration     │  │                      │
   │ FastAPI +       │   │   history, jsonb)   │  │  ECS (service+orch)  │
   │ PostgreSQL      │   └─────────────────────┘  │  ApsaraDB PostgreSQL │
   └─────────────────┘                            └──────────────────────┘
```

> **TODO:** Replace this ASCII diagram with a rendered diagram image (`docs/architecture.png`) once the system is stable. Export from draw.io, Mermaid live, or Excalidraw showing the same components. Place the image here: `![Architecture](docs/architecture.png)`

---

## Key Design Decisions (Track 3 Rubric)

| Rubric criterion | How TuneFlow addresses it |
|---|---|
| **Task decomposition / role assignment** | Three specialized agents (Config, Judge, Optimizer) each own a distinct phase; the LangGraph graph enforces the sequence |
| **Disagreement resolution** | Judge Agent holds veto power; one revision allowed per iteration, enforced in code (`veto_node`) — logged to persistence |
| **Measurable efficiency gain** | Dashboard Compare tab shows side-by-side convergence: multi-agent vs. single god-agent over the same load test ground truth |
| **Vision model integration** | Judge uses `qwen-vl-plus` to analyze rendered Matplotlib charts; visual pattern feeds into the text diagnosis |
| **Different models per call site** | Config Agent uses `qwen-plus`; Optimizer uses `qwen-max`; Judge vision uses `qwen-vl-plus` |

---

## Setup

### Prerequisites

- Docker + Docker Compose
- k6 installed (or use the orchestrator container which installs it)
- Node.js 20+ (for dashboard dev server)
- A Qwen Cloud API key (from the Qwen Cloud console)
- An Alibaba Cloud account (for deployment; optional for local dev)

### Environment variables

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
# Edit .env — at minimum set QWEN_API_KEY
```

**Required for any run:**
```
QWEN_API_KEY=sk-...
```

**Required for Alibaba Cloud deployment:**
```
ALIBABA_ACCESS_KEY_ID=...
ALIBABA_ACCESS_KEY_SECRET=...
```

### Local dev (Docker Compose)

```bash
# Start all services (service DB, persistence DB, service, orchestrator)
docker-compose up -d

# Seed the service DB (run once, or after reset-data)
docker-compose run --rm seed

# Dashboard (separate, if not using the compose dashboard service)
cd dashboard
npm install
npm start   # opens at http://localhost:3000
```

Services:
- Service under test: http://localhost:8000
- Orchestrator: http://localhost:8080
- Dashboard: http://localhost:3000

### Running the agent loop (via API)

```bash
# Start a multi-agent run
curl -X POST http://localhost:8080/runs \
  -H "Content-Type: application/json" \
  -d '{"mode":"multi_agent","max_iterations":15,"vus":100,"load_duration_seconds":30}'

# Start a baseline run for comparison
curl -X POST http://localhost:8080/runs \
  -H "Content-Type: application/json" \
  -d '{"mode":"baseline","max_iterations":15,"vus":100,"load_duration_seconds":30}'
```

Or use the dashboard's **Run** tab.

### Running tests

```bash
pip install -r tests/requirements.txt
pytest tests/ -v

# With live service (hot-swap integration tests):
LIVE_TEST_URL=http://localhost:8000 pytest tests/test_hotswap.py -v
```

---

## Repo Structure

```
/service          FastAPI service under test
  main.py         App entry point + lifespan
  config.py       In-memory ServiceConfig + atomic swap
  database.py     Async SQLAlchemy engine + hot_swap_pool()
  cache.py        Thread-safe TTL cache (product search)
  seed.py         Seed 2k users, 5k products, 10k orders
  routers/        users.py, products.py, orders.py, admin.py

/loadtest
  loadtest.js     k6 script (mixed CRUD, 50-200 VUs)
  runner.py       Python wrapper → structured metrics

/agents
  qwen_client.py  Centralized Qwen Cloud client (text + vision)
  config_agent.py Config Agent (initial + targeted proposals)
  judge_agent.py  Judge Agent (apply, test, diagnose, veto)
  optimizer_agent.py  Optimizer Agent (propose, revise)
  graph.py        LangGraph multi-agent graph
  baseline.py     Single god-agent baseline loop
  termination.py  Shared stop logic (target/plateau/max-iter)
  chart.py        Matplotlib chart renderer for vision analysis

/persistence
  models.py       SQLAlchemy Run + Iteration models
  database.py     Async engine for persistence DB
  store.py        Read/write access layer

/orchestrator
  main.py         FastAPI: start run, poll, history, compare

/dashboard
  src/
    App.jsx       Main app (3 tabs: Run / History / Compare)
    api.js        Orchestrator API client
    components/
      RunLauncher.jsx     Launch multi-agent or baseline run
      ConvergenceChart.jsx  p95/p99/RPS across iterations
      ComparisonChart.jsx   Side-by-side multi-agent vs baseline
      IterationTable.jsx    Per-iteration table with veto flags
      StatusBar.jsx         Live run status with polling
      RunSelector.jsx       Select two runs for comparison
    hooks/usePolling.js

/infra
  docker/
    Dockerfile.service
    Dockerfile.orchestrator
  alibaba/
    deploy.sh             aliyun CLI deployment script
    verify_deployment.py  SDK call proof of Alibaba deployment
    requirements.txt

/docs
  architecture.md   (see below)

/tests
  conftest.py
  test_termination.py   target / plateau / max-iter
  test_veto.py          safety constraints + round-limit
  test_hotswap.py       config swap + cache reset + live endpoint

docker-compose.yml
pytest.ini
.env.example
LICENSE
README.md
```

---

## Alibaba Cloud Deployment

See [`infra/alibaba/deploy.sh`](infra/alibaba/deploy.sh) for the full deployment script (ECS + ApsaraDB for PostgreSQL).

**Proof of deployment:** [`infra/alibaba/verify_deployment.py`](infra/alibaba/verify_deployment.py) makes real Alibaba Cloud SDK calls to describe the deployed ECS and RDS instances.

```bash
pip install -r infra/alibaba/requirements.txt
python infra/alibaba/verify_deployment.py
```

---

## Demo Video

> **TODO:** Record a ~3-minute demo video showing:
> 1. The dashboard launching a multi-agent run and a baseline run
> 2. The live convergence chart updating across iterations
> 3. A veto event visible in the iteration table
> 4. The Compare tab showing the side-by-side efficiency improvement
>
> **Upload link:** `[Demo Video — to be added]`
>
> **Alibaba Cloud deployment proof recording:** `[Deployment Recording — to be added]`

---

## Architecture Diagram

> **TODO:** Generate a polished architecture diagram using draw.io, Mermaid, or Excalidraw
> showing the components in the ASCII diagram above. Save as `docs/architecture.png` and
> replace the ASCII diagram in this README with:
> `![TuneFlow Architecture](docs/architecture.png)`
>
> The diagram should show two logical halves:
> - **Left:** Dashboard ↔ Orchestrator ↔ LangGraph Agents ↔ Qwen Cloud
> - **Right:** Service Under Test ↔ Service Postgres / ApsaraDB ↔ Alibaba Cloud ECS

---

## License

MIT — see [LICENSE](LICENSE)
