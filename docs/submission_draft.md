# lablab.ai Submission — Draft Text

This is draft copy for the AMD Developer Hackathon: ACT II submission form on
lablab.ai. It's pulled directly from the README and PROJECT_GUIDE — no new
claims, no new numbers. Edit freely before pasting; nothing here is final
until you paste and submit it yourself.

---

## Project Title

```
TuneFlow — Autonomous Backend Performance Optimization
```

Shorter alternative if there's a character limit:

```
TuneFlow: Self-Tuning Backend Performance
```

---

## Short Description

Aim for ~200 characters; lablab.ai's exact limit isn't confirmed, so two
lengths are given.

**Tight (~155 chars):**
```
TuneFlow automates backend performance tuning: it benchmarks a live service under real load, diagnoses bottlenecks, applies a fix, and validates it.
```

**Fuller (~230 chars):**
```
TuneFlow automates backend performance tuning end-to-end: it benchmarks a running service under real load, diagnoses what's limiting performance, applies a targeted configuration change, and validates whether it actually helped — continuously.
```

---

## Long Description

```
Backend performance tuning is still largely manual: an engineer changes a
connection pool size or a cache TTL, reruns a load test, eyeballs the
numbers, and repeats — by hand, with no record of what was tried or why.
TuneFlow automates that whole loop. Point it at a service, and it
continuously benchmarks the running system under real load, diagnoses
what's actually limiting performance, proposes a targeted configuration
change, applies it for real, and validates whether the change helped — all
against real k6 load tests and real metrics, never simulated numbers. Think
of it as GitHub Copilot for backend performance: instead of suggesting
code, it suggests — and proves — infrastructure configuration changes.

Under the hood, that loop is implemented as three specialized agents (a
Config Agent, a Judge Agent, and an Optimizer Agent) coordinating through
LangGraph, with the Judge holding veto power over any proposal that
violates a safety constraint. That's an implementation detail, not the
headline — but it's also not just architecture for its own sake: a
single-agent baseline mode runs the identical workload through one model
call per iteration, so the dashboard's side-by-side comparison gives a
measured, real-numbers answer to "does the extra structure actually help,"
instead of asking you to take it on faith. In our own test runs, the
baseline's performance score collapsed under sustained load while p99
latency nearly doubled, and the multi-agent version's Judge caught the same
kind of regression and corrected course on the very next iteration.

All of the reasoning behind every diagnosis and every tuning decision
executes through the Fireworks AI API, which runs on AMD GPUs — the Config
Agent, the Judge's text and vision diagnosis, the Optimizer's tradeoff
decisions, and the baseline's single-shot reasoning all go through
Fireworks, using different model roles matched to how hard each call site's
decision actually is.

The full stack is real, not a mockup: a FastAPI service under test, real
k6 load tests (not simulated metrics), two separate Postgres databases
(service-under-test vs. run-history persistence), a zero-downtime
hot-swap endpoint that reconfigures the service in place without a
restart, and a React dashboard with Run / History / Compare tabs — all
runnable end-to-end with `docker-compose up`.

This demo tunes one service under one fixed workload on purpose, to keep a
hackathon demo run under 30 minutes. The bigger product idea: a customer
connects a repository, TuneFlow benchmarks a staging copy, runs the
optimization loop, and opens a pull request with the load-test evidence
attached — continuously re-tuning as the environment and traffic pattern
change, the way a human engineer would if they had the time to keep
checking. None of that repo/PR integration is built yet; it's the direction
this project is headed, not a claim about what's running today.
```

---

## Technology / Category Tags

```
Python, FastAPI, React, LangGraph, Multi-Agent Systems, PostgreSQL,
Fireworks AI, AMD GPUs, Docker, k6, Load Testing, DevOps,
Performance Engineering, AI Agents, LLM-as-Judge
```

---

## Things this draft deliberately does NOT include

- No demo video link (record per `docs/demo_script.md`, then paste the link).
- No slide deck link (see the slide outline drafted separately — it still
  needs to actually be built into a `.pptx` and exported/uploaded).
- No cover image (see the generated SVG/PNG — pick one and upload it).
- No "Demo Application URL" — this is the one open question that needs a
  decision: deploy a real hosted instance (new public infra, costs money,
  needs your go-ahead) or find out whether lablab.ai's form accepts a
  local-only Docker Compose setup with the demo video as evidence instead.
  See the final checklist for this.
