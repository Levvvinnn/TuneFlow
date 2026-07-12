import React from "react";
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const COLORS = { p95: "#ef4444", p99: "#f97316", rps: "#38bdf8" };

/* ── Custom tooltip ──────────────────────────────────────────────────────── */
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "#0d1526",
      border: "1px solid #1e3a5f",
      borderRadius: 8,
      padding: "10px 14px",
      fontSize: 12,
      minWidth: 160,
    }}>
      <div style={{ color: "#7dd3fc", fontWeight: 700, marginBottom: 6 }}>Iteration {label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ display: "flex", justifyContent: "space-between", gap: 16, color: p.color, marginBottom: 3 }}>
          <span>{p.name}</span>
          <span style={{ fontWeight: 700 }}>
            {p.value != null ? (
              p.dataKey === "rps"
                ? `${Number(p.value).toFixed(1)} r/s`
                : `${Number(p.value).toFixed(0)} ms`
            ) : "—"}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ── Summary stat pill ───────────────────────────────────────────────────── */
function Stat({ label, value, sub, color = "#e2e8f0" }) {
  return (
    <div style={{
      background: "rgba(15,17,23,0.6)",
      border: "1px solid #1e3a5f",
      borderRadius: 8,
      padding: "10px 14px",
      minWidth: 100,
      flex: 1,
    }}>
      <div style={{ fontSize: 10, color: "#475569", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 800, color }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: "#64748b", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

/* ── Main component ──────────────────────────────────────────────────────── */
export default function ConvergenceChart({ iterations, title, targetP95 }) {
  if (!iterations || iterations.length === 0) {
    return (
      <div style={{
        background: "rgba(30,33,48,0.6)",
        border: "1px solid #1e3a5f",
        borderRadius: 12,
        padding: "36px 24px",
        marginBottom: 20,
        textAlign: "center",
        color: "#334155",
        fontSize: 13,
      }}>
        Waiting for first iteration…
      </div>
    );
  }

  const data = iterations.map((it) => ({
    iter:  it.iteration_number,
    p95:   it.metrics?.p95_latency_ms  ?? it.p95_latency_ms  ?? null,
    p99:   it.metrics?.p99_latency_ms  ?? it.p99_latency_ms  ?? null,
    rps:   it.metrics?.throughput_rps  ?? it.throughput_rps  ?? null,
  }));

  /* Summary stats */
  const p95Values = data.map((d) => d.p95).filter((v) => v != null);
  const rpsValues = data.map((d) => d.rps).filter((v) => v != null);
  const bestP95   = Math.min(...p95Values);
  const lastP95   = p95Values[p95Values.length - 1];
  const firstP95  = p95Values[0];
  const improvePct = firstP95 > 0
    ? (((firstP95 - lastP95) / firstP95) * 100).toFixed(1)
    : null;
  const bestRps   = Math.max(...rpsValues);
  const bestIter  = data.findIndex((d) => d.p95 === bestP95) + 1;

  return (
    <div style={{
      background: "rgba(30,33,48,0.7)",
      border: "1px solid rgba(125,211,252,0.08)",
      borderRadius: 14,
      padding: 20,
      marginBottom: 20,
    }}>
      {/* Header */}
      <div style={{ fontSize: 15, fontWeight: 700, color: "#7dd3fc", marginBottom: 16 }}>
        {title || "Convergence — Latency & Throughput"}
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 4, right: 24, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(30,58,95,0.6)" />
          <XAxis
            dataKey="iter"
            stroke="#334155"
            tick={{ fill: "#64748b", fontSize: 11 }}
            label={{ value: "Iteration", position: "insideBottom", offset: -2, fill: "#475569", fontSize: 11 }}
          />
          <YAxis
            yAxisId="left"
            stroke="#334155"
            tick={{ fill: "#64748b", fontSize: 11 }}
            label={{ value: "ms", angle: -90, position: "insideLeft", fill: "#475569", fontSize: 11 }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            stroke="#334155"
            tick={{ fill: "#38bdf8", fontSize: 11 }}
            label={{ value: "req/s", angle: 90, position: "insideRight", fill: "#38bdf8", fontSize: 11 }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: 12, color: "#64748b", paddingTop: 8 }}
          />

          {/* Best-iteration reference line */}
          {bestIter > 0 && (
            <ReferenceLine
              yAxisId="left"
              x={bestIter}
              stroke="rgba(74,222,128,0.35)"
              strokeDasharray="4 3"
              label={{ value: "best", position: "top", fill: "#4ade80", fontSize: 10 }}
            />
          )}

          {/* Target p95 reference */}
          {targetP95 && (
            <ReferenceLine
              yAxisId="left"
              y={targetP95}
              stroke="rgba(234,179,8,0.4)"
              strokeDasharray="6 3"
              label={{ value: `target ${targetP95}ms`, position: "right", fill: "#ca8a04", fontSize: 10 }}
            />
          )}

          <Line yAxisId="left"  type="monotone" dataKey="p95" name="p95 latency (ms)"  stroke={COLORS.p95} dot={{ r: 4, strokeWidth: 0 }} strokeWidth={2.5} activeDot={{ r: 6 }} />
          <Line yAxisId="left"  type="monotone" dataKey="p99" name="p99 latency (ms)"  stroke={COLORS.p99} dot={{ r: 3, strokeWidth: 0 }} strokeWidth={1.5} strokeDasharray="5 3" activeDot={{ r: 5 }} />
          <Line yAxisId="right" type="monotone" dataKey="rps" name="Throughput (req/s)" stroke={COLORS.rps} dot={{ r: 4, strokeWidth: 0 }} strokeWidth={2}   activeDot={{ r: 6 }} />
        </LineChart>
      </ResponsiveContainer>

      {/* ── Summary stat pills ── */}
      <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
        <Stat
          label="Best p95"
          value={`${bestP95.toFixed(0)} ms`}
          sub={`iter ${bestIter}`}
          color="#4ade80"
        />
        <Stat
          label="Latest p95"
          value={`${lastP95?.toFixed(0) ?? "—"} ms`}
          sub="current"
          color={Number(improvePct) > 0 ? "#4ade80" : "#f87171"}
        />
        {improvePct != null && (
          <Stat
            label="Improvement"
            value={`${Number(improvePct) >= 0 ? "↓" : "↑"} ${Math.abs(improvePct)}%`}
            sub="vs iteration 1"
            color={Number(improvePct) > 0 ? "#4ade80" : "#f87171"}
          />
        )}
        <Stat
          label="Peak RPS"
          value={`${bestRps.toFixed(0)}`}
          sub="req/s"
          color="#38bdf8"
        />
        <Stat
          label="Iterations"
          value={data.length}
          sub="completed"
          color="#94a3b8"
        />
      </div>
    </div>
  );
}
