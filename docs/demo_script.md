# TuneFlow — Demo Recording Script (~3 minutes)

## Before you hit record

1. Both a **multi-agent run** and a **baseline run** should already be **finished** (or in their final iteration) from the full-size smoke run. Have both `run_id`s ready.
2. The dashboard is open at `http://localhost:3000`, Compare tab pre-loaded with both runs selected.
3. Browser window at 1920×1080 or similar. No other windows visible.
4. Have the orchestrator logs (`docker-compose logs -f orchestrator`) ready in a side terminal in case you want to show activity — not required.

---

## Shot-by-shot outline

### 0:00–0:25 — Title + one-sentence pitch (screen record or simple slide)

**What to show:** Brief title card or just start with the dashboard already open.

**What to say (roughly):**
> "TuneFlow is a society of specialized agents that tune a backend service's configuration using real load-test ground truth. A Config Agent proposes changes, a Judge Agent applies them and runs k6 load tests, and an Optimizer Agent proposes the next move — with the Judge holding veto power. We'll watch it converge in real time and compare it against a single-agent baseline."

---

### 0:25–0:55 — Run tab: launch a new multi-agent run (30 s)

**UI actions:**
1. Click the **Run** tab.
2. Set the parameters on screen: Max Iterations = **15**, VUs = **100**, Duration = **30**, Repeats = **2**.
3. Click **Launch Multi-Agent Run** — show the "Run started: `<run_id>`" confirmation appear.
4. After ~5 seconds, the StatusBar appears below: status = `running`, current iteration = 1.

**What to say:**
> "Clicking Launch sends a POST to the orchestrator, which kicks off the LangGraph graph in the background. The Config Agent has already proposed an initial connection pool config — the Judge Agent is applying it now and running the first load test."

---

### 0:55–1:30 — History tab: watch live convergence (35 s)

**UI actions:**
1. Click **History** tab — the ConvergenceChart is visible with real data for the already-finished full run (or auto-refreshing if the run is still live).
2. Point to the **p95 latency line** dropping across iterations.
3. Scroll down to the **IterationTable** — show 2–3 rows. Click "▼ analysis" on one row to expand the Judge's bottleneck diagnosis (e.g., "bottleneck: pool_exhaustion, reasoning: …").
4. If a veto event occurred: scroll until you see a row with a purple **VETOED** badge. Click "▼ proposal" to show what the Optimizer originally proposed. Explain what the veto caught.

**What to say:**
> "The Judge Agent's text diagnosis calls out the specific bottleneck — here it flagged pool exhaustion. The Optimizer proposed increasing pool_size, the Judge checked it against safety constraints, accepted it, and the next iteration shows lower p95 latency. You can see the iteration where a proposal was vetoed — the Optimizer's revised proposal passed, and performance kept improving."

*(If no veto fired on this run: "The safety constraints weren't triggered this run, which means the Optimizer stayed within bounds the whole time — still, the negotiation pathway is live and tested.")*

---

### 1:30–1:50 — Also launch baseline run (20 s)

**UI actions:**
1. Click **Run** tab again.
2. Set **identical parameters** to the multi-agent run.
3. Click **Launch Baseline Run** — note the different `run_id`.

**What to say:**
> "Now we launch the baseline — a single god-agent that does propose, diagnose, and decide in one Qwen call per iteration. Same load, same iteration budget. This is our apples-to-apples comparison."

*(If both runs are already finished from the smoke test, skip the live launch and just say "both runs are already finished — let's go straight to the comparison.")*

---

### 1:50–2:40 — Compare tab: the Track 3 proof chart (50 s)

**UI actions:**
1. Click **Compare** tab.
2. In the Run Selector, choose the **multi-agent run** as Run A and the **baseline run** as Run B.
3. The side-by-side chart loads. Point to:
   - **p95 latency chart**: multi-agent line should converge faster (reaches low p95 in fewer iterations).
   - **Throughput chart**: multi-agent RPS should be higher by the final iterations.
4. Scroll down to the two IterationTable panels side by side — show the multi-agent one has richer analysis (Judge diagnosis + vision insight + veto column) vs. the baseline's single "god-agent decision" column.

**What to say:**
> "This is the key Track 3 result: the multi-agent run, here in blue, converges to a lower p95 latency in fewer iterations than the single-agent baseline in orange. The society of specialized agents — each with a focused role and the ability to veto unsafe changes — finds better configurations faster than one agent doing everything in a single call."

---

### 2:40–3:00 — Closing + infrastructure callout (20 s)

**UI actions:**
1. Optional: switch back to the Run tab and show the StatusBar confirming the run finished with reason = `plateau` or `target_hit`.
2. Optional: show the `docs/sample_run_output/` JSON files briefly in a file explorer or terminal.

**What to say:**
> "The service under test is a FastAPI + PostgreSQL app running on Alibaba Cloud ECS with ApsaraDB — real infrastructure, real load tests, not simulated. The full source code, architecture diagram, and run history are in the repo. Thank you."

---

## Tips for a clean recording

- Record at full screen (no cursor jitter on tiny UI elements).
- Use a browser zoom of 90% so the full dashboard fits without scrolling during critical shots.
- If a run is still going live, keep the History tab auto-refreshing — the chart updating in real time is more compelling than a static screenshot.
- The **veto event** (purple VETOED badge in the iteration table) is the single most important visual for Track 3 — if it appeared in your run, zoom in and hold on it for 2–3 seconds.
- Keep the voiceover brief — judges will pause and read the charts themselves.
