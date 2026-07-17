#!/usr/bin/env python3
"""
Evaluate Disagreement-Based Abstention (DBA, arXiv:2602.04853) empirically.

Question: when the Judge's direct diagnosis disagrees with its decomposed
diagnosis, is the decomposed diagnosis's proposal actually more likely to be
wrong than when the two agree? DBA assumes yes. This script checks.

Real abstention (DBA_ABSTENTION=true, DBA_SHADOW_MODE=false) keeps the config
unchanged on disagreement, which makes this unanswerable after the fact —
there's no outcome to inspect. To collect evidence, run with:

    DBA_ABSTENTION=true DBA_SHADOW_MODE=true

Shadow mode still records every disagreement event but lets the proposal
through regardless, so every iteration has a real "did the next iteration's
score improve" outcome to check against.

Method: for each iteration i with a following iteration i+1, compute
score_from_metrics(i) and score_from_metrics(i+1) (lower = better — p95 +
error_rate*10000, same scoring the termination logic uses). Bucket iteration i
by its veto_event["dba"]["agrees"] flag, then compare the improvement rate and
mean score delta between the "agree" and "disagree" buckets.

If disagreement iterations improve less often / less on average than
agreement iterations, that's evidence the disagreement signal is real and
abstaining on it is the right call. If the two buckets look statistically
indistinguishable, that's evidence against DBA in this domain, and the
"direct prompt is just weaker, not independently informative" objection wins.

Usage:
    # From a JSON run-history export (matches GET /runs/{id}/history shape):
    python3 scripts/analyze_dba_outcomes.py --file docs/sample_run_output/multi_agent_run.json

    # Directly from a live orchestrator:
    python3 scripts/analyze_dba_outcomes.py --run-id <uuid> --api-url http://localhost:8080

    # Multiple runs at once (recommended — single-run N is too small to trust):
    python3 scripts/analyze_dba_outcomes.py --file run1.json --file run2.json --file run3.json
"""
import argparse
import json
import statistics
import sys
import urllib.request
from dataclasses import dataclass, field
from typing import Optional


def score_from_metrics(metrics: dict) -> float:
    """Same scoring as agents/termination.py — kept standalone so this script
    has no import dependency on the agents package."""
    p95 = metrics.get("p95_latency_ms", float("inf"))
    err_rate = metrics.get("error_rate", 0.0)
    return p95 + err_rate * 10000


@dataclass
class OutcomeRow:
    run_id: str
    iteration_number: int
    bucket: str  # "agree" | "disagree_shadow" | "disagree_abstained" | "no_dba_data"
    score_before: float
    score_after: Optional[float]
    improved: Optional[bool]
    score_delta: Optional[float]  # positive = improved (score went down)
    direct_bottleneck: Optional[str] = None
    decomposed_bottleneck: Optional[str] = None


def load_from_file(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def load_from_api(run_id: str, api_url: str) -> dict:
    url = f"{api_url.rstrip('/')}/runs/{run_id}/history"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


def classify_iteration(it: dict) -> tuple[str, Optional[str], Optional[str]]:
    """Return (bucket, direct_bottleneck, decomposed_bottleneck) for one iteration."""
    veto_event = it.get("veto_event") or {}
    dba = veto_event.get("dba")

    if dba is None:
        # Real abstention path stores dba info flattened onto veto_event directly
        # (no "dba" sub-key) rather than nested, since it returns early. Handle both.
        if veto_event.get("veto_type") == "disagreement_abstention":
            return (
                "disagree_abstained",
                veto_event.get("direct_bottleneck"),
                veto_event.get("decomposed_bottleneck"),
            )
        return "no_dba_data", None, None

    direct_b = dba.get("direct_bottleneck")
    decomposed_b = dba.get("decomposed_bottleneck")
    if dba.get("agrees"):
        return "agree", direct_b, decomposed_b
    # Disagreed but not real-abstained → shadow mode let it through
    return "disagree_shadow", direct_b, decomposed_b


def build_outcome_rows(run_id: str, iterations: list[dict]) -> list[OutcomeRow]:
    rows = []
    sorted_its = sorted(iterations, key=lambda x: x["iteration_number"])
    for idx, it in enumerate(sorted_its):
        metrics = it.get("metrics") or {}
        if not metrics:
            continue
        bucket, direct_b, decomposed_b = classify_iteration(it)
        score_before = score_from_metrics(metrics)

        score_after = None
        improved = None
        score_delta = None
        if idx + 1 < len(sorted_its):
            next_metrics = sorted_its[idx + 1].get("metrics") or {}
            if next_metrics:
                score_after = score_from_metrics(next_metrics)
                score_delta = score_before - score_after  # positive = improved
                improved = score_delta > 0

        rows.append(OutcomeRow(
            run_id=run_id,
            iteration_number=it["iteration_number"],
            bucket=bucket,
            score_before=score_before,
            score_after=score_after,
            improved=improved,
            score_delta=score_delta,
            direct_bottleneck=direct_b,
            decomposed_bottleneck=decomposed_b,
        ))
    return rows


def summarize(rows: list[OutcomeRow]) -> dict:
    """Bucket rows (excluding the final iteration of each run, which has no outcome) and
    compute improvement rate + mean score delta per bucket."""
    summary = {}
    for bucket in ("agree", "disagree_shadow", "disagree_abstained", "no_dba_data"):
        bucket_rows = [r for r in rows if r.bucket == bucket and r.improved is not None]
        n = len(bucket_rows)
        if n == 0:
            summary[bucket] = {"n": 0}
            continue
        improved_count = sum(1 for r in bucket_rows if r.improved)
        deltas = [r.score_delta for r in bucket_rows]
        summary[bucket] = {
            "n": n,
            "improved_rate": improved_count / n,
            "mean_score_delta": statistics.mean(deltas),
            "median_score_delta": statistics.median(deltas),
            "stdev_score_delta": statistics.stdev(deltas) if n > 1 else 0.0,
        }
    return summary


def print_report(rows: list[OutcomeRow], summary: dict) -> None:
    print("=" * 78)
    print("DBA Outcome Analysis — arXiv:2602.04853 applied to TuneFlow")
    print("=" * 78)
    print()
    print(f"Total scored iterations: {len([r for r in rows if r.improved is not None])}")
    print()

    labels = {
        "agree": "Direct & decomposed AGREE",
        "disagree_shadow": "Disagreed, proposal applied anyway (shadow mode)",
        "disagree_abstained": "Disagreed, real abstention (no outcome — informational only)",
        "no_dba_data": "No DBA data (DBA disabled for this iteration/run)",
    }

    for bucket, label in labels.items():
        s = summary.get(bucket, {"n": 0})
        n = s["n"]
        print(f"[{label}]")
        if n == 0:
            print("  n=0 — no data")
            print()
            continue
        print(f"  n = {n}")
        print(f"  improved next iteration: {s['improved_rate']*100:.1f}%")
        print(f"  mean score delta (positive = improved): {s['mean_score_delta']:+.2f}")
        print(f"  median score delta: {s['median_score_delta']:+.2f}")
        print(f"  stdev: {s['stdev_score_delta']:.2f}")
        print()

    agree = summary.get("agree", {"n": 0})
    disagree = summary.get("disagree_shadow", {"n": 0})
    if agree.get("n", 0) > 0 and disagree.get("n", 0) > 0:
        print("-" * 78)
        print("Comparison (agree vs. disagree-shadow):")
        rate_diff = disagree["improved_rate"] - agree["improved_rate"]
        delta_diff = disagree["mean_score_delta"] - agree["mean_score_delta"]
        print(f"  improvement-rate gap: {rate_diff*100:+.1f} pp (disagree − agree)")
        print(f"  mean-score-delta gap: {delta_diff:+.2f} (disagree − agree)")
        print()
        if rate_diff < -0.05 and delta_diff < 0:
            verdict = (
                "Disagreement iterations improve less often AND by less on average.\n"
                "  → Evidence SUPPORTS DBA: disagreement correlates with worse outcomes."
            )
        elif rate_diff > 0.05 or delta_diff > 0:
            verdict = (
                "Disagreement iterations do NOT look worse than agreement iterations.\n"
                "  → Evidence does NOT support DBA in this domain — the direct prompt's\n"
                "    disagreement may just reflect it being a weaker prompt, not an\n"
                "    independent reliability signal. Consider disabling DBA_ABSTENTION\n"
                "    or gating it on repeated disagreement instead of a single one."
            )
        else:
            verdict = "Difference is small — inconclusive with this sample size. Collect more runs."
        print(verdict)
        print()
        if n < 30:
            print(f"NOTE: n={disagree['n']} disagreement iterations is a small sample.")
            print("Run several shadow-mode runs before drawing conclusions.")
            print()

    print("=" * 78)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", action="append", default=[], help="Path to a run-history JSON file (repeatable)")
    parser.add_argument("--run-id", action="append", default=[], help="Run ID to fetch from a live orchestrator (repeatable)")
    parser.add_argument("--api-url", default="http://localhost:8080", help="Orchestrator base URL (used with --run-id)")
    parser.add_argument("--json-out", default=None, help="Optional path to write the raw summary as JSON")
    args = parser.parse_args()

    if not args.file and not args.run_id:
        parser.error("Provide at least one --file or --run-id")

    all_rows: list[OutcomeRow] = []
    for path in args.file:
        data = load_from_file(path)
        all_rows.extend(build_outcome_rows(data.get("run_id", path), data.get("iterations", [])))
    for run_id in args.run_id:
        data = load_from_api(run_id, args.api_url)
        all_rows.extend(build_outcome_rows(run_id, data.get("iterations", [])))

    summary = summarize(all_rows)
    print_report(all_rows, summary)

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump({
                "summary": summary,
                "rows": [vars(r) for r in all_rows],
            }, f, indent=2)
        print(f"Wrote raw data to {args.json_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
