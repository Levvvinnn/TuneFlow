import React, { useEffect, useState } from "react";
import { listRuns } from "../api";

const S = {
  card: { background: "#1e2130", borderRadius: 12, padding: 20, marginBottom: 20 },
  h2: { fontSize: 15, fontWeight: 700, color: "#7dd3fc", marginBottom: 12 },
  row: { display: "flex", gap: 12, alignItems: "center", marginBottom: 8, flexWrap: "wrap" },
  select: { background: "#0f1117", border: "1px solid #334155", borderRadius: 6, padding: "6px 12px", color: "#e2e8f0", fontSize: 13, minWidth: 260 },
  badge: (mode) => ({
    display: "inline-block", padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 700,
    background: mode === "multi_agent" ? "#1d4ed8" : "#78350f",
    color: mode === "multi_agent" ? "#bfdbfe" : "#fde68a",
    marginLeft: 6,
  }),
  status: (s) => ({
    display: "inline-block", padding: "2px 6px", borderRadius: 4, fontSize: 11,
    background: s === "running" ? "#064e3b" : s === "finished" ? "#1e3a5f" : "#450a0a",
    color: s === "running" ? "#34d399" : s === "finished" ? "#7dd3fc" : "#f87171",
    marginLeft: 6,
  }),
  label: { color: "#94a3b8", fontSize: 13, minWidth: 80 },
};

export default function RunSelector({ onSelectA, onSelectB, selectedA, selectedB }) {
  const [runs, setRuns] = useState([]);

  useEffect(() => {
    listRuns().then(setRuns).catch(() => {});
    const id = setInterval(() => listRuns().then(setRuns).catch(() => {}), 5000);
    return () => clearInterval(id);
  }, []);

  const renderOption = (r) =>
    `${r.mode} — ${r.run_id.slice(0, 8)}… [${r.status}] ${r.created_at?.slice(0, 16) || ""}`;

  return (
    <div style={S.card}>
      <div style={S.h2}>Select Runs for Comparison</div>
      <div style={S.row}>
        <span style={S.label}>Run A:</span>
        <select style={S.select} value={selectedA || ""} onChange={(e) => onSelectA(e.target.value)}>
          <option value="">— select run —</option>
          {runs.map((r) => <option key={r.run_id} value={r.run_id}>{renderOption(r)}</option>)}
        </select>
      </div>
      <div style={S.row}>
        <span style={S.label}>Run B:</span>
        <select style={S.select} value={selectedB || ""} onChange={(e) => onSelectB(e.target.value)}>
          <option value="">— select run —</option>
          {runs.map((r) => <option key={r.run_id} value={r.run_id}>{renderOption(r)}</option>)}
        </select>
      </div>
    </div>
  );
}
