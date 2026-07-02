# TuneFlow — Autonomous Backend Performance Optimization

**Unicorn Track | AMD Developer Hackathon: ACT II**

---

## Pitch

Backend performance tuning is still largely manual: an engineer changes a connection pool size or a cache TTL, reruns a load test, eyeballs the numbers, and repeats — by hand, with no record of what was tried or why. TuneFlow automates that whole loop. Point it at a service, and it continuously benchmarks the running system under real load, diagnoses what's actually limiting performance, proposes a targeted configuration change, applies it for real, and validates whether the change helped — all against real k6 load tests and real metrics, never simulated numbers. Think of it as **GitHub Copilot for backend performance**: instead of suggesting code, it suggests — and proves — infrastructure configuration changes.

Under the hood, that loop is implemented as three specialized agents (a **Config Agent**, a **Judge Agent**, and an **Optimizer Agent**) coordinating through LangGraph, with the Judge holding veto power over any proposal that violates a safety constraint. That's an implementation detail, not the headline — but it's also not just architecture for its own sake: a single-agent **baseline mode** runs the identical workload through one model call per iteration, so the dashboard's side-by-side comparison gives a measured, real-numbers answer to "does the extra structure actually help," instead of asking you to take it on faith. All of the reasoning behind every diagnosis and every tuning decision executes through the Fireworks AI API, which runs on AMD GPUs.

---

## Track

**Unicorn Track** (AMD Developer Hackathon: ACT II) — open-ended, judged on Creativity/Originality, Product/Market Potential, Completeness, and Use of AMD Platforms. TuneFlow's "Use of AMD Platforms" story: every piece of agent reasoning — the Judge's bottleneck diagnosis, the Optimizer's tuning choices — runs on Fireworks AI, which serves its models on AMD GPUs.

---

## Scope & Limitations

> **These are deliberate design choices, not caveats to apologize for.**

- **Fixed, modest load only.** TuneFlow measures *relative configuration performance* at a fixed, modest load (50–200 concurrent virtual users). It does not simulate, predict, or extrapolate to production-scale traffic. The goal is a controlled A/B comparison of configuration quality, not a production load-testing tool.

- **Time budget per full run.** Load-test duration × repeats per config (2–3) × number of iterations (10–20) ≈ **15–25 minutes** total. This is intentional — a single hackathon demo run should complete in under 30 minutes.

- **No full service restarts.** All configuration changes happen via the `/admin/reconfigure` hot-swap endpoint, which drains and recreates the DB connection pool in-place. This is a hard constraint of the design — it ensures the load test measures configuration quality, not restart overhead.

- **Separate databases.** The service-under-test DB and the persistence DB (which stores run history) are separate Postgres instances to avoid cross-contamination.

---

## Vision (roadmap — not built for this submission)

This demo tunes one service under one fixed workload, which raises a fair question: doesn't it just find the same config every time? In a single, unchanging environment, yes — and that's by design for a 25-minute demo run. The actual product idea is broader: the "right" pool size, timeout, and cache TTL are different on a laptop than on an 8-core staging box than on a 32-core production cluster, and different again for a read-heavy workload than a write-heavy one. A real version of TuneFlow continuously re-tunes as the environment or traffic pattern changes, rather than finding one answer once.

Longer-term product direction: a customer connects a repository, TuneFlow deploys a benchmark against a staging copy of their service, runs the optimization loop, and surfaces the recommended change as a pull request with the load-test evidence attached — plus a dashboard and a weekly report tracking performance drift over time. None of that repo/PR integration exists yet; it's the direction this project is headed, not a claim about what's running today.

---

## Architecture

![TuneFlow Architecture](docs/architecture.png)

> The logical spec is [`docs/architecture.mmd`](docs/architecture.mmd) (Mermaid). The rendered
> source is the hand-authored [`docs/architecture.svg`](docs/architecture.svg). To regenerate the PNG:
> `pip install cairosvg && cairosvg docs/architecture.svg -o docs/architecture.png --scale 1.4`

---

## Key Design Decisions (Unicorn Track Judging Criteria)

| Judging criterion | How TuneFlow addresses it |
|---|---|
| **Product / Market Potential** | Generalizes beyond this demo service to any backend with tunable knobs (pool size, timeouts, cache TTL, batch size) — the optimization loop, safety net, and comparison framework are service-agnostic. See [Vision](#vision-roadmap--not-built-for-this-submission) for where this goes as a product |
| **Creativity / Originality** | Treats backend tuning as a continuous, automated loop validated against real load tests — not a chatbot wrapper, and not a one-shot "AI suggests a config" tool with no way to check if the suggestion actually helped |
| **Completeness** | Full working stack: real FastAPI service, real k6 load tests, dual-Postgres persistence, a React dashboard with live polling — runnable end-to-end via `docker-compose up`. As supporting evidence, not the headline: a single-agent baseline mode runs the identical workload, and the dashboard's head-to-head comparison chart gives a measured answer for whether the extra structure (specialized roles + a veto safety check) actually outperforms one model doing everything in a single call |
| **Use of AMD Platforms** | Every piece of agent reasoning — diagnosis, tuning decisions, the baseline mode's single-shot reasoning — runs through the Fireworks AI API (`agents/fireworks_client.py`), which serves its models on AMD GPUs |

Lower-level technical details that back up Completeness, for anyone who wants to look under the hood: the loop is implemented as a Config Agent, Judge Agent, and Optimizer Agent coordinating through LangGraph; the Judge holds veto power with a code-enforced one-revision round limit (`veto_node`); the Judge's diagnosis combines structured metric analysis with a Fireworks vision model reading rendered performance charts; and the Config/Optimizer/baseline/vision call sites each use a different Fireworks model role (`FIREWORKS_TEXT_MODEL`, `FIREWORKS_OPTIMIZER_MODEL`, `FIREWORKS_VISION_MODEL`) matched to how hard that call site's decision actually is.

---

## Setup

### Prerequisites

- Docker + Docker Compose
- k6 installed (or use the orchestrator container which installs it)
- Node.js 20+ (for dashboard dev server)
- A Fireworks AI API key (from the [Fireworks AI console](https://fireworks.ai))
- An Alibaba Cloud account is **not** required — `infra/alibaba/` is a legacy deployment path from an earlier hackathon target and is optional/unused for this submission

### Environment variables

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
# Edit .env — at minimum set FIREWORKS_API_KEY
```

**Required for any run:**
```
FIREWORKS_API_KEY=fw_...
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
  fireworks_client.py  Centralized Fireworks AI client (text + vision)
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

## Legacy: Alibaba Cloud Deployment

TuneFlow was originally built for a different hackathon track that required a Qwen Cloud + Alibaba Cloud stack. That deployment path is **not used** for the AMD Developer Hackathon: ACT II submission, but the script is kept in the repo for reference: [`infra/alibaba/deploy.sh`](infra/alibaba/deploy.sh) (ECS + ApsaraDB for PostgreSQL) and [`infra/alibaba/verify_deployment.py`](infra/alibaba/verify_deployment.py) (proof-of-deployment via the Alibaba SDK). Running either spends real money/credits and is entirely optional.

---

## AMD Developer Hackathon: ACT II Submission

See [`docs/demo_script.md`](docs/demo_script.md) for the shot-by-shot recording guide. Submission goes through lablab.ai and needs: project title, short/long description, technology tags, cover image, video presentation, slide presentation, this public GitHub repo, and a demo application URL.

**Video presentation:** `[Demo Video — to be added after recording]`

**Slide presentation:** `[Slides — to be added]`

**Demo application URL:** `[to be added — local docker-compose unless a hosted demo is set up]`

---

## License

MIT — see [LICENSE](LICENSE)
