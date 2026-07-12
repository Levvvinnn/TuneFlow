import React, { useState } from "react";
import { startRun } from "../api";

const inp = {
  background: "#080d18",
  border: "1px solid #1e3a5f",
  borderRadius: 6,
  padding: "7px 11px",
  color: "#e2e8f0",
  fontSize: 14,
  width: "100%",
  outline: "none",
  boxSizing: "border-box",
};

const S = {
  card: {
    background: "rgba(30,33,48,0.7)",
    border: "1px solid rgba(125,211,252,0.1)",
    borderRadius: 14,
    padding: 24,
    marginBottom: 20,
    backdropFilter: "blur(8px)",
  },
  h2: { fontSize: 16, fontWeight: 800, color: "#e2e8f0", marginBottom: 6 },
  sub: { fontSize: 12, color: "#475569", marginBottom: 20 },
  modesRow: { display: "flex", gap: 12, marginBottom: 22 },
  modeCard: (active) => ({
    flex: 1,
    background:    active ? "rgba(29,78,216,0.2)"  : "rgba(15,17,23,0.6)",
    border:        active ? "1px solid #3b82f6"     : "1px solid #1e3a5f",
    borderRadius:  10,
    padding:       "14px 16px",
    cursor:        "pointer",
    transition:    "all 0.15s",
    textAlign:     "left",
  }),
  modeTitle: (active) => ({
    fontWeight: 700,
    fontSize: 13,
    color: active ? "#7dd3fc" : "#94a3b8",
    marginBottom: 3,
  }),
  modeDesc: { fontSize: 11, color: "#475569", lineHeight: 1.5 },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))",
    gap: 14,
    marginBottom: 16,
  },
  fieldLabel: { fontSize: 11, color: "#64748b", marginBottom: 5, display: "block", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" },
  advToggle: {
    background: "none", border: "none", color: "#475569", fontSize: 12,
    cursor: "pointer", padding: "4px 0", marginBottom: 12, display: "flex", alignItems: "center", gap: 5,
  },
  btnRow: { display: "flex", gap: 12, alignItems: "center", marginTop: 4 },
  btn: (loading) => ({
    background:    loading ? "#1d4ed8" : "linear-gradient(135deg, #2563eb, #3b82f6)",
    border:        "none",
    borderRadius:  9,
    padding:       "11px 28px",
    color:         "#fff",
    fontWeight:    800,
    cursor:        loading ? "default" : "pointer",
    fontSize:      14,
    letterSpacing: "0.01em",
    opacity:       loading ? 0.7 : 1,
    boxShadow:     loading ? "none" : "0 2px 12px rgba(59,130,246,0.35)",
    transition:    "all 0.15s",
  }),
  successMsg: { fontSize: 12, color: "#4ade80", background: "rgba(22,101,52,0.2)", border: "1px solid #166534", borderRadius: 6, padding: "7px 12px" },
  errorMsg:   { fontSize: 12, color: "#f87171", background: "rgba(127,29,29,0.2)",  border: "1px solid #7f1d1d",  borderRadius: 6, padding: "7px 12px" },
};

const MODES = [
  {
    id: "multi_agent",
    title: "⚡ Multi-Agent",
    desc: "LangGraph pipeline: Config → Judge → Optimizer → Veto. Learns across iterations.",
  },
  {
    id: "baseline",
    title: "🤖 Baseline",
    desc: "Single god-agent makes all decisions in one call. No cross-iteration learning.",
  },
];

export default function RunLauncher({ onRunStarted }) {
  const [mode,       setMode]       = useState("multi_agent");
  const [maxIter,    setMaxIter]    = useState(15);
  const [vus,        setVus]        = useState(100);
  const [duration,   setDuration]   = useState(30);
  const [repeats,    setRepeats]    = useState(2);
  const [plateauN,   setPlateauN]   = useState(3);
  const [targetP95,  setTargetP95]  = useState("");
  const [showAdv,    setShowAdv]    = useState(false);
  const [loading,    setLoading]    = useState(false);
  const [lastRunId,  setLastRunId]  = useState(null);
  const [error,      setError]      = useState(null);

  const launch = async () => {
    setLoading(true);
    setError(null);
    setLastRunId(null);
    try {
      const res = await startRun({
        mode,
        max_iterations:       Number(maxIter),
        plateau_n:            Number(plateauN),
        target_p95_ms:        targetP95 ? Number(targetP95) : null,
        vus:                  Number(vus),
        load_duration_seconds: Number(duration),
        load_repeats:         Number(repeats),
      });
      setLastRunId(res.run_id);
      if (onRunStarted) onRunStarted(res.run_id, mode);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={S.card}>
      <div style={S.h2}>Launch Tuning Run</div>
      <div style={S.sub}>Choose a mode, configure parameters, and start the agent loop.</div>

      {/* ── Mode selection ── */}
      <div style={S.modesRow}>
        {MODES.map((m) => (
          <div key={m.id} style={S.modeCard(mode === m.id)} onClick={() => setMode(m.id)}>
            <div style={S.modeTitle(mode === m.id)}>{m.title}</div>
            <div style={S.modeDesc}>{m.desc}</div>
          </div>
        ))}
      </div>

      {/* ── Core parameters ── */}
      <div style={S.grid}>
        <div>
          <label style={S.fieldLabel}>Max Iterations</label>
          <input style={inp} type="number" value={maxIter} min={1} max={50}
            onChange={(e) => setMaxIter(e.target.value)} />
        </div>
        <div>
          <label style={S.fieldLabel}>Virtual Users</label>
          <input style={inp} type="number" value={vus} min={10} max={500}
            onChange={(e) => setVus(e.target.value)} />
        </div>
        <div>
          <label style={S.fieldLabel}>Duration (s)</label>
          <input style={inp} type="number" value={duration} min={10} max={300}
            onChange={(e) => setDuration(e.target.value)} />
        </div>
        <div>
          <label style={S.fieldLabel}>Repeats</label>
          <input style={inp} type="number" value={repeats} min={1} max={5}
            onChange={(e) => setRepeats(e.target.value)} />
        </div>
      </div>

      {/* ── Advanced toggle ── */}
      <button style={S.advToggle} onClick={() => setShowAdv((v) => !v)}>
        <span>{showAdv ? "▾" : "▸"}</span>
        <span>Advanced settings</span>
      </button>

      {showAdv && (
        <div style={{ ...S.grid, gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", marginBottom: 16 }}>
          <div>
            <label style={S.fieldLabel}>Plateau N</label>
            <input style={inp} type="number" value={plateauN} min={2} max={10}
              onChange={(e) => setPlateauN(e.target.value)} />
          </div>
          <div>
            <label style={S.fieldLabel}>Target p95 ms</label>
            <input style={inp} type="number" value={targetP95} placeholder="e.g. 200"
              onChange={(e) => setTargetP95(e.target.value)} />
          </div>
        </div>
      )}

      {/* ── Launch button ── */}
      <div style={S.btnRow}>
        <button style={S.btn(loading)} onClick={launch} disabled={loading}>
          {loading
            ? "Launching…"
            : mode === "multi_agent"
              ? "⚡ Launch Multi-Agent Run"
              : "🤖 Launch Baseline Run"}
        </button>
      </div>

      {lastRunId && (
        <div style={{ ...S.successMsg, marginTop: 12 }}>
          ✓ Run started — {lastRunId}
        </div>
      )}
      {error && (
        <div style={{ ...S.errorMsg, marginTop: 12 }}>
          ✕ {error}
        </div>
      )}
    </div>
  );
}
