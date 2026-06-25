import React from "react";
import {
  CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const COLORS = { p95: "#ef4444", p99: "#f97316", rps: "#3b82f6", err: "#a855f7" };

export default function ConvergenceChart({ iterations, title }) {
  if (!iterations || iterations.length === 0) {
    return (
      <div style={{ color: "#64748b", padding: 24, textAlign: "center" }}>
        No iteration data yet
      </div>
    );
  }

  const data = iterations.map((it) => ({
    iter: it.iteration_number,
    p95: it.metrics?.p95_latency_ms ?? it.p95_latency_ms ?? null,
    p99: it.metrics?.p99_latency_ms ?? it.p99_latency_ms ?? null,
    rps: it.metrics?.throughput_rps ?? it.throughput_rps ?? null,
    errPct: ((it.metrics?.error_rate ?? it.error_rate ?? 0) * 100).toFixed(2),
  }));

  return (
    <div style={{ background: "#1e2130", borderRadius: 12, padding: 20, marginBottom: 20 }}>
      <div style={{ fontSize: 15, fontWeight: 700, color: "#7dd3fc", marginBottom: 12 }}>
        {title || "Convergence — Latency & Throughput"}
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e3a5f" />
          <XAxis dataKey="iter" stroke="#64748b" label={{ value: "Iteration", position: "insideBottom", offset: -2, fill: "#64748b" }} />
          <YAxis yAxisId="left" stroke="#64748b" label={{ value: "ms", angle: -90, position: "insideLeft", fill: "#64748b" }} />
          <YAxis yAxisId="right" orientation="right" stroke="#3b82f6" label={{ value: "req/s", angle: 90, position: "insideRight", fill: "#3b82f6" }} />
          <Tooltip
            contentStyle={{ background: "#1e2130", border: "1px solid #334155", borderRadius: 8 }}
            labelStyle={{ color: "#94a3b8" }}
          />
          <Legend />
          <Line yAxisId="left" type="monotone" dataKey="p95" name="p95 latency (ms)" stroke={COLORS.p95} dot={{ r: 4 }} strokeWidth={2} />
          <Line yAxisId="left" type="monotone" dataKey="p99" name="p99 latency (ms)" stroke={COLORS.p99} dot={{ r: 3 }} strokeWidth={1.5} strokeDasharray="4 2" />
          <Line yAxisId="right" type="monotone" dataKey="rps" name="Throughput (req/s)" stroke={COLORS.rps} dot={{ r: 4 }} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
