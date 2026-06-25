import React, { useState } from "react";
import { startRun } from "../api";

const S = {
  card: { background: "#1e2130", borderRadius: 12, padding: 24, marginBottom: 24 },
  h2: { fontSize: 18, fontWeight: 700, marginBottom: 16, color: "#7dd3fc" },
  row: { display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 12 },
  label: { display: "flex", flexDirection: "column", gap: 4, fontSize: 13, color: "#94a3b8" },
  input: {
    background: "#0f1117", border: "1px solid #334155", borderRadius: 6,
    padding: "6px 10px", color: "#e2e8f0", fontSize: 14, width: 120,
  },
  select: {
    background: "#0f1117", border: "1px solid #334155", borderRadius: 6,
    padding: "6px 10px", color: "#e2e8f0", fontSize: 14,
  },
  btn: {
    background: "#3b82f6", border: "none", borderRadius: 8, padding: "10px 24px",
    color: "#fff", fontWeight: 700, cursor: "pointer", fontSize: 15, marginRight: 12,
  },
  btnSecondary: {
    background: "#64748b", border: "none", borderRadius: 8, padding: "10px 24px",
    color: "#fff", fontWeight: 700, cursor: "pointer", fontSize: 15,
  },
  runId: { marginTop: 12, fontSize: 13, color: "#34d399", wordBreak: "break-all" },
  error: { marginTop: 12, fontSize: 13, color: "#f87171" },
};

export default function RunLauncher({ onRunStarted }) {
  const [mode, setMode] = useState("multi_agent");
  const [maxIter, setMaxIter] = useState(15);
  const [plateauN, setPlateauN] = useState(3);
  const [targetP95, setTargetP95] = useState("");
  const [vus, setVus] = useState(100);
  const [duration, setDuration] = useState(30);
  const [repeats, setRepeats] = useState(2);
  const [loading, setLoading] = useState(false);
  const [runId, setRunId] = useState(null);
  const [error, setError] = useState(null);

  const launch = async (selectedMode) => {
    setLoading(true);
    setError(null);
    try {
      const res = await startRun({
        mode: selectedMode,
        max_iterations: Number(maxIter),
        plateau_n: Number(plateauN),
        target_p95_ms: targetP95 ? Number(targetP95) : null,
        vus: Number(vus),
        load_duration_seconds: Number(duration),
        load_repeats: Number(repeats),
      });
      setRunId(res.run_id);
      if (onRunStarted) onRunStarted(res.run_id, selectedMode);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={S.card}>
      <div style={S.h2}>Launch Tuning Run</div>
      <div style={S.row}>
        <label style={S.label}>
          Max Iterations
          <input style={S.input} type="number" value={maxIter} min={1} max={50}
            onChange={(e) => setMaxIter(e.target.value)} />
        </label>
        <label style={S.label}>
          Plateau N
          <input style={S.input} type="number" value={plateauN} min={2} max={10}
            onChange={(e) => setPlateauN(e.target.value)} />
        </label>
        <label style={S.label}>
          Target p95 ms (optional)
          <input style={S.input} type="number" value={targetP95} placeholder="e.g. 200"
            onChange={(e) => setTargetP95(e.target.value)} />
        </label>
        <label style={S.label}>
          VUs
          <input style={S.input} type="number" value={vus} min={10} max={500}
            onChange={(e) => setVus(e.target.value)} />
        </label>
        <label style={S.label}>
          Duration (s)
          <input style={S.input} type="number" value={duration} min={10} max={300}
            onChange={(e) => setDuration(e.target.value)} />
        </label>
        <label style={S.label}>
          Repeats
          <input style={S.input} type="number" value={repeats} min={1} max={5}
            onChange={(e) => setRepeats(e.target.value)} />
        </label>
      </div>
      <div>
        <button style={S.btn} onClick={() => launch("multi_agent")} disabled={loading}>
          {loading ? "Launching…" : "Launch Multi-Agent Run"}
        </button>
        <button style={S.btnSecondary} onClick={() => launch("baseline")} disabled={loading}>
          {loading ? "Launching…" : "Launch Baseline Run"}
        </button>
      </div>
      {runId && <div style={S.runId}>Run started: {runId}</div>}
      {error && <div style={S.error}>Error: {error}</div>}
    </div>
  );
}
