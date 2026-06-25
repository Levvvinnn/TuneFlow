"""Python wrapper around k6 — triggers a load test run and returns structured metrics."""
import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import httpx

SCRIPT_PATH = Path(__file__).parent / "loadtest.js"
SERVICE_URL = os.getenv("SERVICE_HOST", "http://localhost:8000")


@dataclass
class LoadTestMetrics:
    p95_latency_ms: float
    p99_latency_ms: float
    avg_latency_ms: float
    throughput_rps: float
    error_rate: float
    total_requests: int
    duration_seconds: float
    db_connection_count: Optional[int] = None
    raw_summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def score(self) -> float:
        """Composite score: lower is better. Combines p95 + error penalty."""
        error_penalty = self.error_rate * 10000
        return self.p95_latency_ms + error_penalty


def _fetch_db_stats() -> Optional[int]:
    try:
        r = httpx.get(f"{SERVICE_URL}/admin/db-stats", timeout=5.0)
        if r.status_code == 200:
            data = r.json()
            return data.get("total_connections")
    except Exception:
        pass
    return None


def run_load_test(
    vus: int = 100,
    duration_seconds: int = 30,
    service_url: str = SERVICE_URL,
    extra_env: Optional[dict] = None,
) -> LoadTestMetrics:
    """Run k6 load test and return parsed metrics."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        summary_path = f.name

    env = {
        **os.environ,
        "SERVICE_URL": service_url,
        "VUS": str(vus),
        "DURATION": str(duration_seconds),
        **(extra_env or {}),
    }

    cmd = [
        "k6", "run",
        "--out", f"json={summary_path}",
        "--summary-export", summary_path.replace(".json", "_summary.json"),
        "-e", f"SERVICE_URL={service_url}",
        "-e", f"VUS={vus}",
        "-e", f"DURATION={duration_seconds}",
        str(SCRIPT_PATH),
    ]

    start = time.time()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        timeout=duration_seconds + 60,
    )
    elapsed = time.time() - start

    if result.returncode != 0 and result.returncode != 99:
        # 99 = threshold failure (still have metrics)
        raise RuntimeError(
            f"k6 exited with code {result.returncode}:\n{result.stderr[:2000]}"
        )

    summary_file = summary_path.replace(".json", "_summary.json")
    try:
        with open(summary_file) as f:
            summary = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Could not parse k6 summary: {e}\nstdout: {result.stdout[:1000]}")
    finally:
        for p in [summary_path, summary_file]:
            try:
                os.unlink(p)
            except FileNotFoundError:
                pass

    metrics = summary.get("metrics", {})

    def _val(metric_name: str, stat: str = "p(95)", default: float = 0.0, fallback_stats: tuple = ()) -> float:
        """Pull a stat out of a k6 summary-export metric object.

        k6's --summary-export JSON schema changed across versions: older k6
        nests each metric's stats under a "values" sub-key
        (e.g. {"http_req_duration": {"values": {"p(95)": 127.8}}}), while the
        k6 version actually running here exports them directly on the metric
        object ({"http_req_duration": {"p(95)": 127.8}}). Falling back to the
        metric object itself when "values" is absent means this works against
        either schema — previously every stat silently hit `default` because
        `m.get("values", {})` was always empty, so every iteration's
        p95/p99/avg/throughput/total_requests came back as a flat 0.0 with no
        error, masking real load test results behind fake zeros.
        """
        m = metrics.get(metric_name, {})
        vals = m.get("values", m)
        for key in (stat, *fallback_stats):
            if key in vals:
                return float(vals[key])
        return default

    p95 = _val("http_req_duration", "p(95)")
    p99 = _val("http_req_duration", "p(99)")
    avg = _val("http_req_duration", "avg")
    total_reqs = int(_val("http_reqs", "count", 0))
    rps = _val("http_reqs", "rate", 0.0)
    # Rate-type metrics (error_rate, checks, http_req_failed) report their
    # ratio under "value" in the flat schema; older k6 used "rate" under
    # "values". Try both rather than assuming one.
    err_rate = _val("error_rate", "rate", 0.0, fallback_stats=("value",))

    db_conns = _fetch_db_stats()

    return LoadTestMetrics(
        p95_latency_ms=p95,
        p99_latency_ms=p99,
        avg_latency_ms=avg,
        throughput_rps=rps,
        error_rate=err_rate,
        total_requests=total_reqs,
        duration_seconds=elapsed,
        db_connection_count=db_conns,
        raw_summary=metrics,
    )


def run_load_test_with_repeats(
    vus: int = 100,
    duration_seconds: int = 30,
    repeats: int = 2,
    service_url: str = SERVICE_URL,
) -> LoadTestMetrics:
    """Run multiple repeats and return the average metrics (reduces noise)."""
    results = []
    for i in range(repeats):
        try:
            m = run_load_test(vus=vus, duration_seconds=duration_seconds, service_url=service_url)
            results.append(m)
        except Exception as e:
            if i == 0:
                raise
            # Partial success — use what we have
            break

    if not results:
        raise RuntimeError("All load test repeats failed")

    # Average the numeric fields
    avg_metrics = LoadTestMetrics(
        p95_latency_ms=sum(r.p95_latency_ms for r in results) / len(results),
        p99_latency_ms=sum(r.p99_latency_ms for r in results) / len(results),
        avg_latency_ms=sum(r.avg_latency_ms for r in results) / len(results),
        throughput_rps=sum(r.throughput_rps for r in results) / len(results),
        error_rate=sum(r.error_rate for r in results) / len(results),
        total_requests=sum(r.total_requests for r in results),
        duration_seconds=sum(r.duration_seconds for r in results) / len(results),
        db_connection_count=results[-1].db_connection_count,
        raw_summary=results[-1].raw_summary,
    )
    return avg_metrics


if __name__ == "__main__":
    import sys
    vus = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    dur = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    print(f"Running load test: {vus} VUs, {dur}s")
    m = run_load_test(vus=vus, duration_seconds=dur)
    print(json.dumps(m.to_dict(), indent=2))
