import React, { useEffect, useState } from "react";
import ComparisonChart from "./components/ComparisonChart";
import ConvergenceChart from "./components/ConvergenceChart";
import IterationTable from "./components/IterationTable";
import RunLauncher from "./components/RunLauncher";
import RunSelector from "./components/RunSelector";
import StatusBar from "./components/StatusBar";
import { compareRuns, getRunHistory } from "./api";
import { usePolling } from "./hooks/usePolling";

const NAV = ["Run", "History", "Compare"];

const S = {
  app: {
    minHeight: "100vh",
    background: "linear-gradient(160deg, #080d18 0%, #0a1020 50%, #080d18 100%)",
    paddingBottom: 80,
  },
  header: {
    background: "rgba(10, 16, 32, 0.95)",
    backdropFilter: "blur(12px)",
    borderBottom: "1px solid rgba(125, 211, 252, 0.12)",
    padding: "0 32px",
    display: "flex",
    alignItems: "center",
    gap: 16,
    height: 60,
    position: "sticky",
    top: 0,
    zIndex: 100,
    boxShadow: "0 1px 0 rgba(125,211,252,0.06), 0 4px 24px rgba(0,0,0,0.4)",
  },
  logoWrap: { display: "flex", alignItems: "center", gap: 8 },
  logoIcon: { fontSize: 20 },
  logo: {
    fontSize: 20,
    fontWeight: 800,
    background: "linear-gradient(90deg, #7dd3fc, #38bdf8)",
    WebkitBackgroundClip: "text",
    WebkitTextFillColor: "transparent",
    letterSpacing: -0.5,
  },
  tag: {
    fontSize: 11,
    color: "#475569",
    background: "rgba(15,17,23,0.7)",
    borderRadius: 6,
    padding: "3px 9px",
    border: "1px solid #1e3a5f",
    letterSpacing: "0.02em",
  },
  nav: { display: "flex", gap: 4, marginLeft: "auto" },
  navBtn: (active) => ({
    background: active ? "rgba(125,211,252,0.1)" : "none",
    border: active ? "1px solid rgba(125,211,252,0.25)" : "1px solid transparent",
    borderRadius: 8,
    padding: "6px 18px",
    color: active ? "#7dd3fc" : "#64748b",
    cursor: "pointer",
    fontWeight: 600,
    fontSize: 13,
    transition: "all 0.15s",
  }),
  main: { maxWidth: 1140, margin: "0 auto", padding: "28px 24px" },
};

export default function App() {
  const [tab, setTab] = useState("Run");
  const [activeRunId, setActiveRunId] = useState(null);
  const [activeRunMode, setActiveRunMode] = useState(null);
  const [history, setHistory] = useState(null);
  const [runAId, setRunAId] = useState("");
  const [runBId, setRunBId] = useState("");
  const [compareData, setCompareData] = useState(null);

  const isRunning = history?.status === "running";

  const fetchHistory = async () => {
    if (!activeRunId) return;
    try { setHistory(await getRunHistory(activeRunId)); } catch (_) {}
  };

  useEffect(() => { fetchHistory(); }, [activeRunId]);
  usePolling(fetchHistory, 4000, isRunning);

  const fetchComparison = async () => {
    if (!runAId || !runBId) return;
    try { setCompareData(await compareRuns(runAId, runBId)); } catch (_) {}
  };

  useEffect(() => { fetchComparison(); }, [runAId, runBId]);

  const handleRunStarted = (runId, mode) => {
    setActiveRunId(runId);
    setActiveRunMode(mode);
    setTab("History");
  };

  return (
    <div style={S.app}>
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header style={S.header}>
        <div style={S.logoWrap}>
          <span style={S.logoIcon}>⚡</span>
          <span style={S.logo}>TuneFlow</span>
        </div>
        <div style={S.tag}>Self-Tuning Backend · Multi-Agent AI</div>
        <nav style={S.nav}>
          {NAV.map((t) => (
            <button key={t} style={S.navBtn(tab === t)} onClick={() => setTab(t)}>{t}</button>
          ))}
        </nav>
      </header>

      {/* ── Main ───────────────────────────────────────────────────────── */}
      <main style={S.main}>
        {tab === "Run" && (
          <>
            <RunLauncher onRunStarted={handleRunStarted} />
            {activeRunId && (
              <>
                <StatusBar runId={activeRunId} />
                <ConvergenceChart iterations={history?.iterations || []} title="Live Convergence" />
              </>
            )}
          </>
        )}

        {tab === "History" && (
          <>
            <StatusBar runId={activeRunId} />
            <ConvergenceChart iterations={history?.iterations || []} />
            <IterationTable iterations={history?.iterations || []} mode={activeRunMode || history?.mode} />
          </>
        )}

        {tab === "Compare" && (
          <>
            <RunSelector
              onSelectA={setRunAId}
              onSelectB={setRunBId}
              selectedA={runAId}
              selectedB={runBId}
            />
            {compareData && (
              <>
                <ComparisonChart runA={compareData.run_a} runB={compareData.run_b} />
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 8 }}>
                  <IterationTable iterations={compareData.run_a?.iterations} mode={compareData.run_a?.mode} />
                  <IterationTable iterations={compareData.run_b?.iterations} mode={compareData.run_b?.mode} />
                </div>
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
