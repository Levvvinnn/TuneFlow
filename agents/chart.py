"""Generate performance chart images for the Judge Agent's vision analysis."""
import os
import tempfile
from typing import Optional

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def render_performance_chart(
    iterations: list[dict],
    output_path: Optional[str] = None,
) -> Optional[str]:
    """
    Render a PNG chart of latency, throughput, and error rate across iterations.
    Returns the file path of the saved PNG, or None if matplotlib is not available.

    Each entry in `iterations` should have keys:
        iteration_number, p95_latency_ms, p99_latency_ms, throughput_rps,
        error_rate, config_applied (dict)
    """
    if not HAS_MPL or len(iterations) == 0:
        return None

    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)

    xs = [it["iteration_number"] for it in iterations]
    p95s = [it.get("p95_latency_ms", 0) for it in iterations]
    p99s = [it.get("p99_latency_ms", 0) for it in iterations]
    rps = [it.get("throughput_rps", 0) for it in iterations]
    errs = [it.get("error_rate", 0) * 100 for it in iterations]

    fig = plt.figure(figsize=(12, 8))
    fig.suptitle("TuneFlow — Performance Across Iterations", fontsize=14, fontweight="bold")
    gs = gridspec.GridSpec(3, 1, hspace=0.45)

    # Latency
    ax1 = fig.add_subplot(gs[0])
    ax1.plot(xs, p95s, "o-", color="#e74c3c", label="p95 latency (ms)", linewidth=2)
    ax1.plot(xs, p99s, "s--", color="#c0392b", label="p99 latency (ms)", linewidth=1.5, alpha=0.7)
    ax1.set_ylabel("Latency (ms)")
    ax1.set_title("Latency")
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.set_xticks(xs)

    # Throughput
    ax2 = fig.add_subplot(gs[1])
    ax2.plot(xs, rps, "o-", color="#2980b9", linewidth=2)
    ax2.set_ylabel("Requests/sec")
    ax2.set_title("Throughput")
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks(xs)

    # Error rate
    ax3 = fig.add_subplot(gs[2])
    ax3.bar(xs, errs, color="#e67e22", alpha=0.75)
    ax3.set_ylabel("Error Rate (%)")
    ax3.set_title("Error Rate")
    ax3.set_xlabel("Iteration")
    ax3.set_xticks(xs)
    ax3.grid(True, alpha=0.3, axis="y")

    plt.savefig(output_path, dpi=96, bbox_inches="tight")
    plt.close(fig)
    return output_path
