import React, { useEffect, useState } from "react";
import { getRunStatus } from "../api";
import { usePolling } from "../hooks/usePolling";

const S = {
  bar: { background: "#1e2130", borderRadius: 10, padding: "12px 20px", marginBottom: 16, display: "flex", gap: 20, alignItems: "center", flexWrap: "wrap" },
  label: { color: "#64748b", fontSize: 12 },
  value: { color: "#e2e8f0", fontSize: 14, fontWeight: 600, marginLeft: 4 },
  dot: (s) => ({
    display: "inline-block", width: 8, height: 8, borderRadius: "50%",
    background: s === "running" ? "#22c55e" : s === "finished" ? "#3b82f6" : "#ef4444",
    marginRight: 6,
  }),
};

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

  return (
    <div style={S.bar}>
      <div><span style={S.dot(status.status)} /><span style={S.value}>{status.status}</span></div>
      <div><span style={S.label}>Run:</span><span style={S.value}>{runId.slice(0, 12)}…</span></div>
      <div><span style={S.label}>Mode:</span><span style={S.value}>{status.mode}</span></div>
      <div><span style={S.label}>Iteration:</span><span style={S.value}>{status.current_iteration} / {status.max_iterations}</span></div>
      {status.latest_score != null && (
        <div><span style={S.label}>Score (p95+err):</span><span style={S.value}>{status.latest_score?.toFixed(0)}</span></div>
      )}
      {status.termination_reason && (
        <div><span style={S.label}>Stopped:</span><span style={S.value}>{status.termination_reason}</span></div>
      )}
    </div>
  );
}
