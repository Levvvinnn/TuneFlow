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

## Status: first real result (2026-07-18)

Ran with `DBA_SHADOW_MODE=true` against a live Docker Compose stack
(Fireworks AI, `deepseek-v4-flash`). Four 15-iteration multi-agent runs were
launched; three completed cleanly (all terminated on `plateau` around
iteration 3), one hit a `ConnectTimeout`/`429 RATE_LIMIT_EXCEEDED` from
Fireworks under concurrent load and was excluded except for the iterations
it completed before failing. Combined sample: **7 scored iterations — 4
agree, 3 disagree (shadow-applied), 0 no-DBA-data** (confirming the
disagreement check executed on every iteration). Raw data:
[`dba_evaluation_results.json`](dba_evaluation_results.json).

| Bucket | n | improved next iteration | mean score delta |
|---|---|---|---|
| Agree | 4 | 75.0% | +9.99 |
| Disagree (shadow) | 3 | 33.3% | −131.97 |

Gap: −41.7pp improvement rate, −141.96 mean score delta (disagree − agree).
`analyze_dba_outcomes.py`'s own verdict: *"Evidence SUPPORTS DBA: disagreement
correlates with worse outcomes."*

**A nuance worth being upfront about**, since it affects how much weight the
agree-bucket number deserves: of the 4 scored "agree" rows, only 2 are
genuine matching-bottleneck agreements (`slow_queries == slow_queries`,
outcomes: one improved, one regressed — a wash). The other 2 are cases where
the direct diagnosis returned `"unknown"`, which `check_diagnosis_agreement`
treats as non-comparable and defaults into the agree bucket by design (see
[Method](#the-adaptation) above) — both of those happened to improve. So the
strong 75% agree-bucket number is partly inflated by non-comparable cases,
not purely by confirmed agreement.

The disagree-shadow bucket has no such artifact: all 3 rows are genuine
conflicts between two named bottlenecks (`pool_exhaustion` vs `slow_queries`,
twice, and the reverse once) — exactly the "confident conflict" case DBA is
meant to catch, with no `unknown` noise diluting it. 2 of those 3 show large
regressions (−220.9, −191.5); one improved slightly (+16.5). That the same
`pool_exhaustion` vs `slow_queries` conflict recurred across two independent
runs with similarly bad outcomes both times is a small point in favor of this
being a real pattern rather than pure noise — but n=3 is still far too small
to treat as confirmed.

**Honest read**: directionally exactly what DBA predicts, and the
disagreement sample itself is clean (no unknown-driven artifacts inflating
it the way the agree bucket has), which is a mildly encouraging sign. But
n=3 disagreements is not a result you can defend under any real scrutiny —
this is "the effect is plausible and worth continuing to measure," not
"DBA is validated." One rate-limited run and the fact that all four attempted
runs terminated on `plateau` by iteration 3 (short by the 15-iteration budget)
both point at the same fix: space runs out over time and consider raising
`plateau_n` or lowering the plateau sensitivity so runs generate more
iterations per run, since more iterations per run is cheaper than more runs
(fewer cold-start iterations wasted, less exposure to Fireworks rate limits).

**Next step**: repeat with a larger, rate-limit-respecting batch — e.g. 8-10
runs launched a few minutes apart rather than concurrently — before treating
this as a real conclusion rather than a promising first look.
