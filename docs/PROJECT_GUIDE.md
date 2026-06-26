# TuneFlow, Explained From the Ground Up

This is the deep-dive companion to the [README](../README.md) and [architecture.md](architecture.md).
Those two answer "what talks to what." This one answers "why does it work this way,"
walks through exactly what happens during one real iteration, and writes down every
bug this project hit during development and why each one was the kind of bug that
doesn't announce itself. Read it top to bottom once and you'll be able to trace any
behavior you see in a real run back to the line of code that produced it.

---

## 1. The problem, in one paragraph

A backend service has a handful of tunable knobs — connection pool size, query
timeout, cache TTL, batch size, retry interval — and the "right" values depend on
the actual workload and environment, not on intuition. Tuning them today is manual:
an engineer changes one, reruns a load test, eyeballs the result, repeats. TuneFlow
automates that loop end to end: propose a config, apply it for real (no simulation),
hammer it with a real load test, diagnose what's actually limiting performance,
propose the next change, and repeat until performance hits a target or stops
improving — continuously, not as a one-shot suggestion with no way to check whether
it actually helped.

*Under the hood* (this is implementation, not the headline): the loop is built as
three specialized agents — Config, Judge, Optimizer — that each own one phase and
hand off to the next, with the Judge holding veto power over changes that look
unsafe, coordinated through LangGraph. A single-agent "baseline god-agent" mode runs
the identical workload so that the difference between *this structure* and *one
model doing it all* is a measurable, real number sitting in the dashboard's Compare
tab, not a claim — useful supporting evidence for Completeness, not the project's
pitch. Every agent's reasoning runs through Fireworks AI, whose inference executes
on AMD GPUs — the project's concrete answer to the Unicorn Track's "Use of AMD
Platforms" criterion.

> **A note on this project's history.** TuneFlow was originally built for a
> different hackathon track that targeted Qwen Cloud (DashScope) for LLM calls and
> Alibaba Cloud for deployment. When the Alibaba Cloud account signup turned out to
> be blocked, the project was retargeted to the AMD Developer Hackathon: ACT II
> (Unicorn Track), and the LLM backend was swapped from Qwen Cloud to Fireworks AI —
> whose serverless models run on AMD GPU hardware. The multi-agent architecture,
> the veto mechanic, the real load-test ground truth, and the baseline comparison
> are all unchanged; only the model provider and the hackathon framing moved. The
> Alibaba deployment scripts under `infra/alibaba/` are kept in the repo but are not
> part of this submission.

---

## 2. The two halves, and why they're separate processes

TuneFlow is really two independent systems that only talk to each other over HTTP:

**The service under test** (`service/`) is an ordinary FastAPI + PostgreSQL app —
users, products, orders, a product-search cache. It knows nothing about agents or
tuning. It exposes one extra endpoint, `POST /admin/reconfigure`, that lets an
outside caller swap its connection-pool settings *without restarting the process*.
That single endpoint is the entire surface area the tuning system is allowed to
touch.

**The agent system** (`orchestrator/`, `agents/`, `loadtest/`, `persistence/`) treats
the service as a black box it pokes from the outside: change config → run load test
→ read the numbers → decide what to change next. It has its own database
(`persistence-db`, port 5433) that is completely separate from the service's own
database (`service-db`, port 5432). This separation is deliberate, not accidental —
if tuning-run history lived in the same database as the data being load-tested,
every config change and every load-test write would be contending for the exact
connections you're trying to measure, contaminating the experiment. Two Postgres
containers, two URLs, two SQLAlchemy engines, zero shared state.

Why hot-swap instead of restart? Restarting a process to apply a new pool size would
mean every iteration's load test partly measures "how long does FastAPI take to boot"
rather than "is this config actually faster." `service/database.py`'s
`hot_swap_pool()` builds a brand-new SQLAlchemy async engine with the new settings,
gives the old one half a second to drain in-flight queries, disposes it, and atomically
swaps a module-level pointer — the running process never stops accepting requests.

---

## 3. One full multi-agent iteration, traced through the actual code

This is the part worth reading slowly. Everything else in the project is in service
of this loop.

**Entry point.** The dashboard (or a raw `curl`) does:
```
POST /runs  {"mode": "multi_agent", "max_iterations": 15, "plateau_n": 3, "vus": 100, ...}
```
`orchestrator/main.py`'s `start_run()` calls `persistence/store.py`'s `create_run()`
to insert a `Run` row (status `"running"`), then fires `_run_multi_agent_bg()` as a
FastAPI `BackgroundTask` and immediately returns `{"run_id": ..., "status": "started"}`
— the HTTP request does not block for the ~15–25 minutes the full run takes. The
dashboard polls `GET /runs/{id}/status` afterward.

**The graph.** `_run_multi_agent_bg()` calls `agents/graph.py`'s `run_multi_agent()`,
which builds an initial `AgentState` dict (a `TypedDict` — current_config, scores,
iteration_history, etc.) and hands it to a compiled LangGraph `StateGraph`. The graph
has six nodes wired as:
```
config → judge → optimizer → veto → persist → terminate ─┬→ config (loop)
                                                            └→ END
```
Every node is an `async def node(state) -> dict` function. LangGraph merges whatever
dict a node returns into the shared state before calling the next node — nodes don't
call each other directly, they only ever read and write this one shared state object.
That single fact is the source of the most serious bug this project had (section 7
below), so hold onto it.

**Node 1 — `config_node`.** Iteration 1: calls `config_agent.py`'s
`propose_initial_config()`, which asks Fireworks AI's text model
(`FIREWORKS_TEXT_MODEL`) for a sensible starting point within `PARAM_BOUNDS` (e.g.
`pool_size: 2-50`, `query_timeout_ms: 500-15000`).
Iteration 2+: does **not** call any agent — it just reads `state["proposed_config"]`,
which was placed there by `terminate_node` at the end of the *previous* iteration.
(Why this matters is section 7.)

**Node 2 — `judge_node`.** This is the only node that touches the real world.
`judge_agent.py`'s `full_judge_cycle()` does, in order:
1. `apply_config()` — `POST /admin/reconfigure` against the service, triggering the
   hot-swap described above.
2. `run_and_measure()` — calls `loadtest/runner.py`'s `run_load_test_with_repeats()`,
   which shells out to the real `k6` binary against `loadtest/loadtest.js` (a mixed
   CRUD workload: 40% product search, 25% user lookup, 20% order create, 15% order
   read — see the script for the exact `Math.random()` routing), parses the
   `--summary-export` JSON, and averages 2 repeats together to smooth out noise.
3. `diagnose_text()` — sends the metrics + recent history to Fireworks AI's text
   model (`FIREWORKS_TEXT_MODEL`) and asks for a structured JSON diagnosis:
   `bottleneck`, `severity`, `reasoning`, `recommended_direction`, `trend`.
4. `diagnose_vision()` — `chart.py` renders a 3-panel Matplotlib PNG (latency,
   throughput, error rate across all iterations so far), and that image is sent to
   Fireworks AI's vision model (`FIREWORKS_VISION_MODEL`) with a prompt asking it to
   read the *shape* of each panel. This is a second, independent signal on top of
   the text diagnosis — the same underlying numbers, looked at as a picture instead
   of a table.

**Node 3 — `optimizer_node`.** `optimizer_agent.py`'s `propose_next_config()` takes
the Judge's full output (text diagnosis + vision diagnosis + raw metrics) and asks
Fireworks AI's stronger reasoning model (`FIREWORKS_OPTIMIZER_MODEL`) to pick the
single most impactful change. This is a deliberately different, stronger model than
the Config Agent uses — the Optimizer's job (weighing tradeoffs under uncertainty) is
harder than the Config Agent's job (picking a reasonable starting point), so it gets
the better model.

**Node 4 — `veto_node`.** Checks the Optimizer's proposal against
`judge_agent.py`'s `SAFETY_CONSTRAINTS` (hard floors like `pool_size >= 2`,
`query_timeout_ms >= 500`). If safe, the proposal becomes `final_decision` as-is. If
not, the Optimizer gets exactly **one** revision attempt
(`optimizer.revise_proposal()`, told the specific veto reason) — and the round limit
of 1 is enforced by `veto_node`'s own code, not by hoping the model stops on its own.
If the revision is *also* unsafe, the node forces a fallback to the current
(already-known-safe) config rather than letting an unsafe value through by
exhaustion. This veto/one-revision mechanic is the concrete demonstration of
disagreement resolution between agents that backs up the project's Creativity and
Completeness story for the Unicorn Track.

**Node 5 — `persist_node`.** Writes one `Iteration` row to the persistence DB via
`store.py`'s `save_iteration()` — every artifact from this iteration (config proposed,
config applied, raw metrics, both diagnoses, the optimizer's proposal, the veto event,
the final decision) goes into one JSONB-heavy row. Persistence failures are caught
and swallowed here deliberately (`except Exception: pass`) — a DB write failing
should never crash a 20-minute tuning run; it should just mean that one iteration's
history is thinner.

**Node 6 — `terminate_node`.** Calls the shared `termination.py` logic (section 6)
and decides: stop, or loop back to `config_node` with `iteration_number + 1` and,
critically, `proposed_config` set to this iteration's `final_decision` — carrying the
veto-checked decision forward into the next iteration's `config_node` read.

---

## 4. Baseline mode, and why it's structurally simpler

`agents/baseline.py`'s `run_baseline()` is a plain Python `for` loop, not a graph —
there's no LangGraph state machine because there's only one decision-maker per
iteration. Each iteration: apply the current config, run the same load test, make
**one** Fireworks AI call (`god_agent_step()`, using `FIREWORKS_TEXT_MODEL`) that
diagnoses *and* proposes *and* explains in a single JSON response, persist, check
termination, and set `current_config = result["next_config"]` directly for the next
loop pass.

There's no Optimizer, no veto, no two-agent handoff — which also means there's no
"discard the wrong thing" failure mode of the kind multi-agent had (section 7),
because there's only ever one value in flight per iteration, and it always becomes
both `config_applied` for this round and the literal input to next round. Simpler
architecture, structurally immune to that particular bug class, but also no safety
gate and no second opinion. That tradeoff — and a concrete, measured instance of it —
is the demo's punchline: see section 8.

---

## 5. Fireworks AI integration

Every LLM call goes through one file, `agents/fireworks_client.py` — nothing else in
the codebase constructs an HTTP request to an LLM provider directly. Three model
roles, each overridable via env var:

| Role | Env var | Default | Used by |
|---|---|---|---|
| Text / reasoning | `FIREWORKS_TEXT_MODEL` | `accounts/fireworks/models/llama-v3p1-70b-instruct` | Config Agent, Judge's text diagnosis, baseline god-agent |
| Stronger reasoning | `FIREWORKS_OPTIMIZER_MODEL` | `accounts/fireworks/models/deepseek-v3` | Optimizer Agent only |
| Vision | `FIREWORKS_VISION_MODEL` | `accounts/fireworks/models/llama-v3p2-11b-vision-instruct` | Judge's chart analysis only |

`json_completion()` is the workhorse: it calls `text_completion()`, strips markdown
code fences if the model wrapped its JSON in them, and raises a clear `ValueError`
with the raw text included if parsing still fails — so a malformed model response
shows up as a readable error instead of a silent `{}`. `_raise_with_body()` exists
because `httpx`'s default error message for a 4xx/5xx response discards the response
body, and Fireworks AI's API puts the actually-useful information — wrong model ID,
expired key, no quota — in that body. Without this wrapper, a 403 just says "403
Forbidden"; with it, the log line tells you exactly why.

**Historical note (from the Qwen Cloud days):** the project's original provider,
Qwen Cloud (via DashScope), had a real operational gotcha where the free quota was
region-specific — the base URL had to point at the Singapore (`dashscope-intl`)
endpoint to use the free tier (task #1, fixed early in the project). Fireworks AI
has no equivalent region-quota split, so this particular gotcha doesn't carry over
to the current provider — noted here only because the bug was real and the fix
pattern (read the error body, don't trust the status code alone) is still relevant.

---

## 6. Termination logic, fully explained (this one trips people up)

`agents/termination.py`'s `check_termination()` is shared verbatim by both modes —
same function, same thresholds, called with the same arguments — which is what makes
the multi-agent-vs-baseline comparison fair. Three conditions, checked in this order:

1. **Target hit**: latest score `<=` `target_p95_ms` (if a target was given at all).
2. **Max iterations**: `iteration_number >= max_iterations`.
3. **Plateau**: take the last `plateau_n` scores, compare the *oldest* score in that
   window against the *best* (lowest) score in that window. If the improvement is
   smaller than `max(2.0, oldest_score * 0.01)` — a 1% relative floor with a 2.0
   absolute floor for when scores are already small — call it a plateau and stop.

The score itself (`score_from_metrics()`) is just `p95_latency_ms + error_rate *
10000` — lower is better, and a single bad error spike is weighted as heavily as
~10 seconds of p95 latency, which is intentional (errors should dominate the score).
Note this score is **p95-only** — `p99_latency_ms` is tracked, displayed, and fed to
the Judge's diagnosis, but it does not directly affect termination or scoring. A run
can "successfully" plateau while p99 is quietly getting worse; section 8's case
study is exactly this.

The thing that has caused the most confusion during development: with a small
`plateau_n` (the smoke-test payloads in this repo use `plateau_n: 2`), plateau
evaluation starts the moment there are only 2 scores total — i.e., as early as the
end of iteration 2. So a smoke-test run stopping after iteration 2 with
`reason=plateau` is not a bug, it's `plateau_n: 2` doing exactly what it says: "stop
as soon as 2 consecutive iterations show no meaningful improvement." For a real
demo run, use a more patient `plateau_n` (3–5, as `.env.example`'s default
`PLATEAU_N=3` suggests) so the loop actually gets a few iterations to explore before
calling it quits.

---

## 7. The "silently wrong, not loudly broken" bug class

Every real bug found in this project during development shared one shape: something
defaulted, fell back, got recomputed, or got discarded — without raising an
exception — and the rest of the system treated the result as if it were correct. No
stack trace ever pointed at any of these; each one required noticing that a *number*
looked implausible and tracing backward from there. Logging this pattern explicitly
because it's the single most useful debugging habit this project reinforced.

**Bug 1 — `termination_reason` column too narrow.** The persistence DB's
`termination_reason` column was sized for short labels like `"plateau"`, but a failed
agent node could put a full exception message (sometimes the entire DashScope error
body) into that same field, which silently truncated and raised its own masking
error inside the failure handler. Fixed by widening the column to `Text` — see the
comment directly in `persistence/models.py`.

**Bug 2 — k6 summary schema mismatch.** `loadtest/runner.py`'s metric parser assumed
k6's `--summary-export` JSON nested every stat under a `"values"` sub-key (true for
older k6 versions). The actual k6 version in use exports stats directly on the metric
object. The code's `m.get("values", {})` therefore always got an empty dict, every
`.get(stat, default)` silently hit `default`, and **every single metric** — p95,
p99, avg, throughput, total requests — came back as a flat `0.0` with no error at
all. The loop kept running, agents kept "reasoning" about all-zero metrics, and
nothing crashed. Fixed by falling back to the metric object itself when `"values"`
is absent, so the same code works against either schema.

**Bug 3 — p99 export omitted entirely.** Even after fixing bug 2, `p99_latency_ms`
stayed at `0.0`. Root cause was one level up: k6's default `summaryTrendStats`
(`avg`, `min`, `med`, `max`, `p(90)`, `p(95)`) never included `p(99)` in the exported
JSON in the first place — it didn't matter how the parser read the file, because the
key was never written to it. `thresholds` in `loadtest.js` *checked* p99 internally
without needing it in the summary export, which is why it looked like p99 was being
used somewhere even though it never reached `runner.py`. Fixed by explicitly listing
`summaryTrendStats: [..., "p(99)"]` in the k6 script's `options`.

**Bug 4 — the Optimizer's veto-checked decision was discarded every iteration.**
This is the most serious one, and it's the direct payoff of remembering "nodes only
communicate through shared state" from section 3. `config_node`'s iteration-2-plus
branch used to call `config_agent.propose_config_change(current_config=
state["current_config"], ...)` — a *second*, independent Config Agent call — instead
of reading `state["proposed_config"]`. Two problems compounded: first,
`state["current_config"]` is the config that was just *measured*, not the
veto-checked decision about what to apply *next* (that lives in `proposed_config`,
set by `terminate_node` from `final_decision`). Second, and worse: this fresh
Config Agent call never passed through `veto_node` at all — it ran *after* veto had
already done its job for the iteration. So from iteration 2 onward, the value
`veto_node` had safety-checked was computed, displayed in the dashboard, written to
the database... and then silently thrown away in favor of an unchecked number from a
completely different code path. The dashboard would show a sensible "Optimizer
decided cache_ttl_seconds=120" and the very next row would show "config_applied:
cache_ttl_seconds=300" with no explanation, because nothing was technically
*wrong* — both numbers were valid, just from two different unconnected decisions.
Fixed by deleting that redundant call entirely: `config_node` for iteration 2+ now
does `state.get("proposed_config") or state["current_config"]`, full stop. The
now-unused `propose_config_change()` function was removed from `config_agent.py`
during cleanup — Config Agent's job is now *only* "propose the iteration-1 starting
point," which is a cleaner story than it used to tell.

The common thread: none of these four needed a stack trace to exist, and none of
them would show up in a code review that only checks "does this compile / does this
type-check." They only show up when you compare a real number the system produced
against what you independently know it should be — which is exactly why every fix
above was verified against a real `docker-compose` run's actual JSON output, not
just a passing unit test.

---

## 8. Multi-agent vs. baseline: a real, measured difference

With both bugs above fixed, two separate real local smoke-test runs (5 iterations,
30 VUs each — one baseline, one multi-agent, same load pattern and config bounds,
not the same literal run) produced a concrete, useful comparison:

**Baseline** chased its composite score down by repeatedly raising
`query_timeout_ms` (5000 → 7500 → 10000ms across the run) — the score (p95 +
error-rate penalty) fell from 257.6 → 97.0 → 34.6 → 32.0 → 52.1 — but **p99 rose the
entire time** (358ms → 699ms), because a longer timeout just lets pathologically
slow queries run longer instead of failing fast. `score_from_metrics()` is p95-only
(section 6), so the single god-agent optimizing that score directly had no signal
telling it p99 was getting worse, and it never caught it.

**Multi-agent**, on its own comparable run, hit an iteration where the Judge's text
diagnosis explicitly flagged the latency trend as `"degrading"` after p99 nearly
tripled (524ms → 1586ms) between iterations — and the Optimizer's next proposal
*decreased* `query_timeout_ms` rather than raising it further, the opposite move
baseline made when facing the analogous tradeoff. That's the Judge+Optimizer split
earning its complexity: the Judge's diagnosis is a second read on the metrics
that isn't reducible to the one number the loop terminates on, and it caught a
regression that scoring alone would have missed.

This is real output from this project's own runs, not a hypothetical. It isn't the
project's headline — the headline is "TuneFlow continuously optimizes backend
configuration"; this is the receipts underneath that claim, the answer to "does the
extra structure (Judge + Optimizer + veto) actually outperform one model doing
everything in a single call." Worth keeping the actual run JSON on hand for the
demo as supporting evidence; for a cleaner A/B, consider using
`/compare?run_a=...&run_b=...` to pull both runs' p95/p99 series side by side from
the same comparison endpoint the dashboard uses.

---

## 9. The persistence layer and what the dashboard actually reads

`persistence/models.py` defines exactly two tables. `runs`: one row per tuning run
(mode, status, target/max-iterations/plateau-n settings, termination_reason).
`iterations`: one row per iteration, with seven JSONB columns —
`config_proposed`, `config_applied`, `metrics`, `judge_analysis`,
`judge_vision_analysis`, `optimizer_proposal`, `veto_event`, `final_decision`,
`baseline_decision` (this last one is `NULL` for every multi-agent row and
populated only in baseline mode — the two modes share one table rather than having
parallel schemas, which is what makes `/compare` a single simple query instead of a
union).

`orchestrator/main.py` exposes this as three read endpoints: `/runs/{id}/status`
(cheap, for polling — backed by an in-memory `_run_status` dict that's faster than
a DB round-trip for "what iteration are we on right now"), `/runs/{id}/history`
(every column of every iteration, what you want when actually inspecting a run),
and `/compare?run_a=...&run_b=...` (a slimmed-down parallel view of two runs' p95 /
p99 / throughput / error-rate / veto-flag series, which is exactly what the
dashboard's `ComparisonChart.jsx` plots). Note: `/compare` didn't actually return
`p99_latency_ms` until this cleanup pass — it was being silently dropped between
`/history`'s full metrics dict and `/compare`'s slimmed-down one, which meant the
dashboard's headline chart couldn't show the exact divergence section 8 relies on.
Fixed by adding the field to the endpoint and a dashed p99 line to the chart
itself.

---

## 10. Running and inspecting it yourself

```bash
# Bring up service DB, persistence DB, service, orchestrator
docker-compose up -d --build

# Seed the service DB (2k users / 5k products / 10k orders) — once, or after a reset
docker-compose run --rm seed

# Kick off a run
curl -X POST http://localhost:8080/runs \
  -H "Content-Type: application/json" \
  -d '{"mode":"multi_agent","max_iterations":15,"plateau_n":3,"vus":100,"load_duration_seconds":30,"load_repeats":2}'

# Poll status (cheap)
curl http://localhost:8080/runs/<run_id>/status

# Full per-iteration data once it's done (or mid-run)
curl http://localhost:8080/runs/<run_id>/history | python3 -m json.tool

# Run the unit test suite (mocks the LLM client, no live infra needed for most of it)
pip install -r tests/requirements.txt
pytest tests/ -v
```

When reading a `/history` response, the fields worth checking against each other to
confirm the loop is behaving (this is literally how every bug in section 7 was
caught): does `config_applied` in iteration N+1 match `final_decision` from
iteration N? Does `p99_latency_ms` look like a plausible multiple of `p95_latency_ms`
rather than exactly `0.0`? Does `veto_event.vetoed` ever come back `true`, and if so
does the following `final_decision` actually reflect the revision rather than just
re-stating the original unsafe proposal?

---

## 11. Where things live (quick index)

```
service/            the app being tuned — knows nothing about agents
  config.py            in-memory ServiceConfig + thread-safe swap_config()
  database.py          hot_swap_pool() — the only place a restart is avoided
  routers/admin.py      /admin/reconfigure, /admin/db-stats, /admin/reset-data

loadtest/
  loadtest.js           k6 script — the actual traffic pattern
  runner.py             shells out to k6, parses summary JSON → LoadTestMetrics

agents/
  fireworks_client.py    the only file that talks to Fireworks AI's API
  config_agent.py        iteration-1 starting config only (see bug 4)
  judge_agent.py          apply + measure + diagnose (text & vision) + veto check
  optimizer_agent.py      propose next change + handle one revision
  graph.py                LangGraph wiring — config→judge→optimizer→veto→persist→terminate
  baseline.py             single-agent god-agent loop, no graph needed
  termination.py          target/plateau/max-iter — shared by both modes
  chart.py                renders the 3-panel PNG fed to the vision model

persistence/
  models.py              Run + Iteration tables (JSONB-heavy)
  store.py                every read/write goes through here

orchestrator/main.py     FastAPI: POST /runs, GET status/history/compare

dashboard/src/            React UI — Run / History / Compare tabs
```

---

## 12. What's done, and what's still open

Local end-to-end is solid for both modes as of this writing — every bug in section
7 has been fixed and re-verified against fresh real run data, and the cleanup pass
(dead code, stray debug files, a stricter `.gitignore`) is done. Three items are
intentionally **not** done on your behalf, because each one needs a decision only
you can make:

- **Flipping the GitHub repo public.** It's already pushed privately with a LICENSE
  in place. Going public is a one-click decision, but it's yours to make — and the
  AMD Developer Hackathon: ACT II submission requires a public repo.
- **Alibaba Cloud deployment.** No longer the active deployment plan — the AMD
  hackathon submission runs locally via `docker-compose up`. `infra/alibaba/deploy.sh`
  and `verify_deployment.py` still work if you ever want to revisit that path, but
  running them spends real money/credits and isn't needed for this submission.
- **Recording the demo video and slides.** The shot list is already written in
  `docs/demo_script.md` (updated for the Fireworks AI / AMD framing). Section 8
  above gives you a concrete, real-numbers talking point to use in it (baseline's
  p99 regression vs. multi-agent catching it). The AMD ACT II submission on
  lablab.ai also needs a slide presentation, a cover image, and a demo application
  URL — none of those exist yet.
- **Setting a real `FIREWORKS_API_KEY` and double-checking model slugs.** The
  defaults in `.env.example` were real, live Fireworks model slugs as of when this
  pivot was made — worth a quick check against https://fireworks.ai/models before
  the demo, and again once AMD ACT II's kickoff (Jul 6, 2026) reveals the
  AMD-hosted model catalog, in case anything's changed.

Everything else — the actual tuning loop, both modes, the bug fixes, the cleanup —
is done and verified against real runs, not just unit tests.

**A note on positioning, not code.** This demo tunes one service under one fixed
workload, so a fair challenge is "doesn't it just find the same config every time?"
In a single unchanging environment, yes — that's intentional for a short demo run.
The README's [Vision](../README.md#vision-roadmap--not-built-for-this-submission)
section lays out the actual product idea: the right config differs by environment
(laptop vs. staging vs. production) and by workload shape (read-heavy vs.
write-heavy), so a real deployment of this re-tunes continuously rather than
solving once. None of the repo-connect/PR-automation part of that vision is built —
it's pitch material for the submission, not a claim about current capability.
