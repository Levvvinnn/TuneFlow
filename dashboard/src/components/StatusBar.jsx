import React, { useEffect, useState } from "react";
import { getRunStatus } from "../api";
import { usePolling } from "../hooks/usePolling";

const STATUS_COLOR = {
  running:  { dot: "#22c55e", border: "#166534", bg: "rgba(22,101,52,0.15)",  text: "#4ade80" },
  finished: { dot: "#3b82f6", border: "#1e3a5f", bg: "rgba(30,58,95,0.25)",   text: "#7dd3fc" },
  failed:   { dot: "#ef4444", border: "#7f1d1d", bg: "rgba(127,29,29,0.2)",   text: "#f87171" },
};

const pulse = `
  @keyframes pulse-dot {
    0%, 100% { opacity: 1; transform: scale(1); }
    50%       { opacity: 0.5; transform: scale(1.4); }
  }
`;

export default function StatusBar({ runId }) {
  const [status, setStatus] = useState(null);
  const active = !!runId && status?.status === "running";

  const poll = async () => {
    if (!runId) return;
    try { setStatus(await getRunStatus(runId)); } catch (_) {}
  };

  useEffect(() => { poll(); }, [runId]);
  usePolling(poll, 3000, active);

  if (!runId || !status) return null;

  const sc = STATUS_COLOR[status.status] || STATUS_COLOR.failed;
  const iter    = status.current_iteration ?? 0;
  const maxIter = status.max_iterations   ?? 1;
  const pct     = Math.min(100, Math.round((iter / maxIter) * 100));

  return (
    <>
      <style>{pulse}</style>
      <div style={{
        background: sc.bg,
        border: `1px solid ${sc.border}`,
        borderRadius: 12,
        padding: "14px 20px",
        marginBottom: 16,
      }}>
        {/* ── Top row ── */}
        <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap", marginBottom: 10 }}>

          {/* Status dot + label */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{
              display: "inline-block", width: 9, height: 9, borderRadius: "50%",
              background: sc.dot,
              animation: active ? "pulse-dot 1.4s ease-in-out infinite" : "none",
            }} />
            <span style={{ color: sc.text, fontWeight: 800, fontSize: 13, textTransform: "uppercase", letterSpacing: "0.06em" }}>
              {status.status}
            </span>
          </div>

          {/* Mode badge */}
          <span style={{
            background: status.mode === "multi_agent" ? "rgba(29,78,216,0.3)" : "rgba(120,53,15,0.4)",
            color:      status.mode === "multi_agent" ? "#93c5fd"              : "#fde68a",
            border:     `1px solid ${status.mode === "multi_agent" ? "#1d4ed8" : "#92400e"}`,
            borderRadius: 6, padding: "2px 10px", fontSize: 11, fontWeight: 700,
          }}>
            {status.mode === "multi_agent" ? "Multi-Agent" : "Baseline"}
          </span>

          {/* Run ID */}
          <span style={{ color: "#475569", fontSize: 11, fontFamily: "monospace" }}>
            {runId.slice(0, 14)}…
          </span>

          {/* Score */}
          {status.latest_score != null && (
            <span style={{ marginLeft: "auto", color: "#94a3b8", fontSize: 12 }}>
              Score{" "}
              <span style={{ color: "#e2e8f0", fontWeight: 700, fontSize: 14 }}>
                {status.latest_score.toFixed(0)}
              </span>
            </span>
          )}
        </div>

        {/* ── Progress bar ── */}
        <div style={{ marginBottom: status.termination_reason || status.error ? 10 : 0 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#64748b", marginBottom: 5 }}>
            <span>Iteration {iter} / {maxIter}</span>
            <span>{pct}%</span>
          </div>
          <div style={{ background: "rgba(255,255,255,0.06)", borderRadius: 4, height: 6, overflow: "hidden" }}>
            <div style={{
              width: `${pct}%`,
              height: "100%",
              background: active
                ? "linear-gradient(90deg, #22c55e, #4ade80)"
                : status.status === "finished"
                  ? "linear-gradient(90deg, #3b82f6, #60a5fa)"
                  : "linear-gradient(90deg, #ef4444, #f87171)",
              borderRadius: 4,
              transition: "width 0.5s ease",
            }} />
          </div>
        </div>

        {/* ── Termination / error ── */}
        {status.termination_reason && (
          <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 4 }}>
            Stopped:{" "}
            <span style={{ color: "#e2e8f0", fontWeight: 600 }}>{status.termination_reason}</span>
          </div>
        )}
        {status.error && (
          <div style={{ fontSize: 12, color: "#fca5a5", marginTop: 6, background: "rgba(127,29,29,0.3)", borderRadius: 6, padding: "6px 10px" }}>
            ✕ {status.error}
          </div>
        )}
      </div>
    </>
  );
}
