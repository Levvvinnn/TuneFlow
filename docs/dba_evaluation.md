# Evaluating Disagreement-Based Abstention in TuneFlow

Adapting "Decomposed Prompting Does Not Fix Knowledge Gaps, But Helps Models
Say 'I Don't Know'" (Madhwal, Zhang, Roth & Gupta, arXiv:2602.04853) to a
non-QA setting: autonomous backend performance tuning.

## The paper's core mechanism

DBA compares a model's answer under **Direct** prompting to its answer under
a **decomposed** prompting regime (Assistive/Incremental) on the same
question. Because factual knowledge is stable across prompting regimes while
hallucination is stochastic, disagreement between the two regimes is a
precise, training-free signal that the model's underlying belief is fragile
— more informative than the model's self-reported confidence. The paper
turns this into an abstention policy: on disagreement, refuse to answer
rather than risk a confident hallucination.

## The adaptation

TuneFlow's [Judge Agent](../agents/judge_agent.py) already produces a
**decomposed** diagnosis of the load-test metrics — a scaffolded prompt that
walks through p95, error rate, and throughput signals against explicit
decision rules before naming a bottleneck (`diagnose_text`). We added a
**Direct** counterpart (`diagnose_direct`) — the identical question, same
inputs, no scaffold — run concurrently so there's no added latency.
[`veto_node`](../agents/graph.py) now checks agreement between the two
before letting the Optimizer's proposal through: on disagreement, the
iteration **abstains** by keeping the current config, exactly as DBA
abstains from answering.

## Why this needed a genuine empirical check, not just an argument

A reasonable objection: the Direct prompt lacks the decomposed prompt's
explicit heuristics (e.g. "high error rate + high latency → pool
exhaustion"), so a disagreement might just mean the Direct prompt is a
*weaker* prompt, not an *independent* one — in which case treating
disagreement as an uncertainty signal is unjustified, and abstaining throws
away good decomposed diagnoses for no reason.

This is exactly the question the paper's methodology is built to answer, so
we built the same kind of check for TuneFlow: measure whether disagreement
iterations produce worse **downstream outcomes** than agreement iterations,
rather than assuming either side of the argument.

## Method

Real abstention keeps the config unchanged on disagreement, which erases the
counterfactual — there's no outcome to inspect for "what if we'd applied
the decomposed proposal anyway." So evaluation requires **shadow mode**
(`DBA_SHADOW_MODE=true`): every disagreement is still recorded on
`veto_event`, but the proposal is applied regardless. This produces two
comparable populations of iterations, agree and disagree, each with a real
next-iteration outcome.

For every iteration *i* with a following iteration *i+1*:

```
score(metrics) = p95_latency_ms + error_rate * 10000     # same scoring as termination.py
score_delta    = score(i) - score(i+1)                    # positive = improved
```

Iterations are bucketed by their own `veto_event.dba.agrees` flag, then
compared:

- **improvement rate** — fraction of iterations in the bucket followed by a
  lower score
- **mean / median score delta** — average magnitude of improvement or
  regression

If disagreement iterations improve less often and by less on average, that
supports DBA: the disagreement really does track diagnosis reliability. If
the two buckets look statistically indistinguishable, that supports the
"Direct is just weaker" objection, and abstaining is discarding good
proposals for a signal that isn't real in this domain.

Implementation: [`scripts/analyze_dba_outcomes.py`](../scripts/analyze_dba_outcomes.py).
Tested against synthetic fixtures in [`tests/test_analyze_dba_outcomes.py`](../tests/test_analyze_dba_outcomes.py)
to confirm the bucketing/scoring logic is correct before trusting it on real
run data.

## Running the evaluation

```bash
# 1. Enable shadow mode so disagreements are recorded but not acted on
echo "DBA_SHADOW_MODE=true" >> .env

# 2. Run several multi-agent runs (more than one — n per run is typically
#    10-20 iterations, too small to trust alone)
curl -X POST http://localhost:8080/runs \
  -H "Content-Type: application/json" \
  -d '{"mode":"multi_agent","max_iterations":15,"vus":100,"load_duration_seconds":30}'
# repeat for several runs, collecting run_ids

# 3. Analyze
python3 scripts/analyze_dba_outcomes.py \
  --run-id <run_1> --run-id <run_2> --run-id <run_3> \
  --api-url http://localhost:8080 \
  --json-out docs/dba_evaluation_results.json
```

Or against exported JSON files matching the `GET /runs/{id}/history` shape
(e.g. `docs/sample_run_output/*.json` once regenerated with DBA-enabled
runs):

```bash
python3 scripts/analyze_dba_outcomes.py --file run1.json --file run2.json
```

## Status

Not yet run against live data — this sandbox has no Docker Compose stack or
Fireworks AI credits to generate real shadow-mode runs. The instrumentation,
scoring logic, and reporting are built and unit-tested (`tests/test_disagreement.py`,
`tests/test_analyze_dba_outcomes.py`); a synthetic fixture confirms the
script correctly detects a known effect when one is injected into the data,
but that is a test of the *tool*, not evidence about DBA's real-world
validity in this domain.

**Next step**: run `DBA_SHADOW_MODE=true` for several multi-agent runs
against the live service and fill in real numbers here.
