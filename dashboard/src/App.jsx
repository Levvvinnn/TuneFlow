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
  app: { minHeight: "100vh", padding: "0 0 60px" },
  header: { background: "#111827", borderBottom: "1px solid #1e3a5f", padding: "14px 32px", display: "flex", alignItems: "center", gap: 16 },
  logo: { fontSize: 22, fontWeight: 800, color: "#7dd3fc", letterSpacing: -0.5 },
  tag: { fontSize: 11, color: "#475569", background: "#0f1117", borderRadius: 6, padding: "2px 8px" },
  nav: { display: "flex", gap: 8, marginLeft: "auto" },
  navBtn: (active) => ({
    background: active ? "#1e3a5f" : "none", border: "none", borderRadius: 6,
    padding: "6px 16px", color: active ? "#7dd3fc" : "#64748b", cursor: "pointer", fontWeight: 600, fontSize: 14,
  }),
  main: { maxWidth: 1100, margin: "0 auto", padding: "32px 24px" },
  section: { marginBottom: 32 },
};

export default function App() {
  const [tab, setTab] = useState("Run");
  const [activeRunId, setActiveRunId] = useState(null);
  const [activeRunMode, setActiveRunMode] = useState(null);
  const [history, setHistory] = useState(null);
  const [runA, setRunA] = useState(null);
  const [runB, setRunB] = useState(null);
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
    try {
      const data = await compareRuns(runAId, runBId);
      setCompareData(data);
    } catch (_) {}
  };

  useEffect(() => { fetchComparison(); }, [runAId, runBId]);

  const handleRunStarted = (runId, mode) => {
    setActiveRunId(runId);
    setActiveRunMode(mode);
    setTab("History");
  };

  return (
    <div style={S.app}>
      <header style={S.header}>
        <div style={S.logo}>TuneFlow</div>
        <div style={S.tag}>Self-Tuning Backend Agent · Track 3: Agent Society</div>
        <nav style={S.nav}>
          {NAV.map((t) => (
            <button key={t} style={S.navBtn(tab === t)} onClick={() => setTab(t)}>{t}</button>
          ))}
        </nav>
      </header>

      <main style={S.main}>
        {tab === "Run" && (
          <div style={S.section}>
            <RunLauncher onRunStarted={handleRunStarted} />
            {activeRunId && (
              <>
                <StatusBar runId={activeRunId} />
                <ConvergenceChart iterations={history?.iterations || []} title="Live Convergence" />
              </>
            )}
          </div>
        )}

        {tab === "History" && (
          <div style={S.section}>
            <StatusBar runId={activeRunId} />
            <ConvergenceChart iterations={history?.iterations || []} />
            <IterationTable iterations={history?.iterations || []} mode={activeRunMode || history?.mode} />
          </div>
        )}

        {tab === "Compare" && (
          <div style={S.section}>
            <RunSelector
              onSelectA={(id) => { setRunAId(id); }}
              onSelectB={(id) => { setRunBId(id); }}
              selectedA={runAId}
              selectedB={runBId}
            />
            {compareData && (
              <>
                <ComparisonChart runA={compareData.run_a} runB={compareData.run_b} />
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                  <IterationTable iterations={compareData.run_a?.iterations} mode={compareData.run_a?.mode} />
                  <IterationTable iterations={compareData.run_b?.iterations} mode={compareData.run_b?.mode} />
                </div>
              </>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
