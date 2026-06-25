/**
 * Side-by-side convergence chart: multi-agent run vs baseline.
 * This is the primary Track 3 proof chart.
 */
import React from "react";
import {
  CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

function buildChartData(runA, runB) {
  const itersA = runA?.iterations || [];
  const itersB = runB?.iterations || [];
  const maxLen = Math.max(itersA.length, itersB.length);
  const data = [];
  for (let i = 0; i < maxLen; i++) {
    const a = itersA[i];
    const b = itersB[i];
    data.push({
      iter: i + 1,
      a_p95: a ? (a.metrics?.p95_latency_ms ?? a.p95_latency_ms) : null,
      b_p95: b ? (b.metrics?.p95_latency_ms ?? b.p95_latency_ms) : null,
      a_p99: a ? (a.metrics?.p99_latency_ms ?? a.p99_latency_ms) : null,
      b_p99: b ? (b.metrics?.p99_latency_ms ?? b.p99_latency_ms) : null,
      a_rps: a ? (a.metrics?.throughput_rps ?? a.throughput_rps) : null,
      b_rps: b ? (b.metrics?.throughput_rps ?? b.throughput_rps) : null,
    });
  }
  return data;
}

export default function ComparisonChart({ runA, runB }) {
  if (!runA || !runB) {
    return (
      <div style={{ color: "#64748b", padding: 24, textAlign: "center" }}>
        Select two runs to compare
      </div>
    );
  }

  const data = buildChartData(runA, runB);
  const labelA = `${runA.mode} (${runA.run_id?.slice(0, 8)}…)`;
  const labelB = `${runB.mode} (${runB.run_id?.slice(0, 8)}…)`;

  return (
    <div style={{ background: "#1e2130", borderRadius: 12, padding: 20, marginBottom: 20 }}>
      <div style={{ fontSize: 15, fontWeight: 700, color: "#7dd3fc", marginBottom: 4 }}>
        Head-to-Head Comparison — Multi-Agent vs Baseline
      </div>
      <div style={{ fontSize: 12, color: "#64748b", marginBottom: 14 }}>
        p95 (solid) and p99 (light, dashed) latency across iterations. Lower = better.
        Faster convergence = more efficient agent strategy — watch for p99 diverging
        from p95 even when p95 looks like it's improving.
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e3a5f" />
          <XAxis dataKey="iter" stroke="#64748b" label={{ value: "Iteration", position: "insideBottom", offset: -2, fill: "#64748b" }} />
          <YAxis stroke="#64748b" label={{ value: "Latency (ms)", angle: -90, position: "insideLeft", fill: "#64748b" }} />
          <Tooltip
            contentStyle={{ background: "#1e2130", border: "1px solid #334155", borderRadius: 8 }}
            labelStyle={{ color: "#94a3b8" }}
          />
          <Legend />
          <Line type="monotone" dataKey="a_p95" name={`${labelA} p95`} stroke="#3b82f6" dot={{ r: 4 }} strokeWidth={2.5} />
          <Line type="monotone" dataKey="b_p95" name={`${labelB} p95`} stroke="#f97316" dot={{ r: 4 }} strokeWidth={2.5} strokeDasharray="5 3" />
          <Line type="monotone" dataKey="a_p99" name={`${labelA} p99`} stroke="#93c5fd" dot={{ r: 2 }} strokeWidth={1.5} strokeDasharray="2 2" />
          <Line type="monotone" dataKey="b_p99" name={`${labelB} p99`} stroke="#fdba74" dot={{ r: 2 }} strokeWidth={1.5} strokeDasharray="2 2" />
        </LineChart>
      </ResponsiveContainer>

      {/* Throughput comparison */}
      <div style={{ fontSize: 14, fontWeight: 600, color: "#94a3b8", margin: "18px 0 8px" }}>
        Throughput (req/s)
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e3a5f" />
          <XAxis dataKey="iter" stroke="#64748b" />
          <YAxis stroke="#64748b" />
          <Tooltip contentStyle={{ background: "#1e2130", border: "1px solid #334155", borderRadius: 8 }} />
          <Legend />
          <Line type="monotone" dataKey="a_rps" name={labelA} stroke="#3b82f6" dot={{ r: 3 }} strokeWidth={2} />
          <Line type="monotone" dataKey="b_rps" name={labelB} stroke="#f97316" dot={{ r: 3 }} strokeWidth={2} strokeDasharray="5 3" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
