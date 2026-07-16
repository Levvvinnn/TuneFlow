import React, { useEffect, useState } from "react";
import ComparisonChart from "./components/ComparisonChart";
import ConvergenceChart from "./components/ConvergenceChart";
import IterationTable from "./components/IterationTable";
import RunLauncher from "./components/RunLauncher";
import RunSelector from "./components/RunSelector";
import StatusBar from "./components/StatusBar";
import { compareRuns, getRunHistory, listRuns } from "./api";
import { usePolling } from "./hooks/usePolling";
import { DEMO_MULTI_AGENT, DEMO_BASELINE, DEMO_RUN_LIST, DEMO_RUN_MAP } from "./sampleData";

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
  demoTag: {
    fontSize: 11,
    color: "#f59e0b",
    background: "rgba(120,53,15,0.35)",
    borderRadius: 6,
    padding: "3px 9px",
    border: "1px solid #78350f",
    letterSpacing: "0.02em",
    fontWeight: 700,
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

  // Run picker
  picker: {
    background: "#1e2130",
    border: "1px solid #1e3a5f",
    borderRadius: 10,
    padding: "14px 18px",
    marginBottom: 16,
    display: "flex",
    alignItems: "center",
    gap: 10,
    flexWrap: "wrap",
  },
  pickerLabel: { color: "#64748b", fontSize: 13, flexShrink: 0 },
  pickerSelect: {
    background: "#0f1117", border: "1px solid #334155", borderRadius: 6,
    padding: "5px 10px", color: "#e2e8f0", fontSize: 13, flex: 1, minWidth: 200,
  },
  demoBtn: {
    background: "rgba(120,53,15,0.4)",
    border: "1px solid #92400e",
    borderRadius: 7,
    padding: "5px 14px",
    color: "#fde68a",
    cursor: "pointer",
    fontSize: 12,
    fontWeight: 700,
    flexShrink: 0,
  },
  clearBtn: {
    background: "none",
    border: "1px solid #334155",
    borderRadius: 7,
    padding: "5px 12px",
    color: "#64748b",
    cursor: "pointer",
    fontSize: 12,
    flexShrink: 0,
  },

  // Empty state
  empty: {
    textAlign: "center",
    padding: "60px 20px",
    color: "#475569",
  },
  emptyTitle: { fontSize: 18, fontWeight: 700, color: "#64748b", marginBottom: 10 },
  emptyDesc: { fontSize: 14, color: "#334155", marginBottom: 28, lineHeight: 1.6 },
  emptyDemoBtn: {
    background: "linear-gradient(135deg, rgba(120,53,15,0.6), rgba(146,64,14,0.4))",
    border: "1px solid #92400e",
    borderRadius: 10,
    padding: "12px 28px",
    color: "#fde68a",
    cursor: "pointer",
    fontSize: 15,
    fontWeight: 700,
    display: "inline-block",
  },
};

// ── Run picker used in the History tab ───────────────────────────────────────
function RunPicker({ activeRunId, demoMode, onSelect, onLoadDemo, onClear, runs }) {
  return (
    <div style={S.picker}>
      <span style={S.pickerLabel}>Run:</span>
      <select
        style={S.pickerSelect}
        value={activeRunId || ""}
        onChange={(e) => e.target.value && onSelect(e.target.value, "live")}
      >
        <option value="">— select a run —</option>
        {runs.map((r) => (
          <option key={r.run_id} value={r.run_id}>
            {r.mode === "multi_agent" ? "Multi-Agent" : "Baseline"} · {r.run_id.slice(0, 8)}… [{r.status}] {r.created_at?.slice(0, 16) || ""}
          </option>
        ))}
        {runs.length === 0 && <option disabled>No live runs yet</option>}
      </select>
      <button style={S.demoBtn} onClick={onLoadDemo}>
        Load Demo Data
      </button>
      {(activeRunId || demoMode) && (
        <button style={S.clearBtn} onClick={onClear}>Clear</button>
      )}
      {demoMode && <span style={S.demoTag}>DEMO</span>}
    </div>
  );
}

// ── Empty state when no run is selected ──────────────────────────────────────
function HistoryEmpty({ onLoadDemo }) {
  return (
    <div style={S.empty}>
      <div style={S.emptyTitle}>No run selected</div>
      <div style={S.emptyDesc}>
        Launch a run from the <strong style={{ color: "#7dd3fc" }}>Run</strong> tab, or load the
        bundled demo to explore the full dashboard without Docker or an API key.
      </div>
      <button style={S.emptyDemoBtn} onClick={onLoadDemo}>
        ⚡ Explore Demo Run
      </button>
    </div>
  );
}

// ── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab] = useState("Run");
  const [activeRunId, setActiveRunId] = useState(null);
  const [activeRunMode, setActiveRunMode] = useState(null);
  const [history, setHistory] = useState(null);
  const [demoMode, setDemoMode] = useState(false);
  const [liveRuns, setLiveRuns] = useState([]);
  const [runAId, setRunAId] = useState("");
  const [runBId, setRunBId] = useState("");
  const [compareData, setCompareData] = useState(null);

  const isRunning = !demoMode && history?.status === "running";

  // ── Fetch live run list ──
  const fetchRunList = async () => {
    try { setLiveRuns(await listRuns()); } catch (_) {}
  };
  useEffect(() => { fetchRunList(); }, []);
  usePolling(fetchRunList, 8000, true);

  // ── Fetch run history (live only) ──
  const fetchHistory = async () => {
    if (!activeRunId || demoMode) return;
    try { setHistory(await getRunHistory(activeRunId)); } catch (_) {}
  };
  useEffect(() => { fetchHistory(); }, [activeRunId]);
  usePolling(fetchHistory, 4000, isRunning);

  // ── Demo mode loader ──
  const loadDemo = (runId) => {
    const data = DEMO_RUN_MAP[runId] || DEMO_MULTI_AGENT;
    setHistory(data);
    setActiveRunId(data.run_id);
    setActiveRunMode(data.mode);
    setDemoMode(true);
  };

  const loadDefaultDemo = () => loadDemo(DEMO_MULTI_AGENT.run_id);

  const clearRun = () => {
    setActiveRunId(null);
    setActiveRunMode(null);
    setHistory(null);
    setDemoMode(false);
  };

  const selectLiveRun = async (runId) => {
    setDemoMode(false);
    setActiveRunId(runId);
    setActiveRunMode(null);
    try {
      const h = await getRunHistory(runId);
      setHistory(h);
      setActiveRunMode(h.mode);
    } catch (_) {}
  };

  // ── Comparison ──
  const fetchComparison = async () => {
    if (!runAId || !runBId) return;

    // Both demo? Serve from sample data
    const aDemo = DEMO_RUN_MAP[runAId];
    const bDemo = DEMO_RUN_MAP[runBId];
    if (aDemo && bDemo) {
      setCompareData({ run_a: aDemo, run_b: bDemo });
      return;
    }
    try { setCompareData(await compareRuns(runAId, runBId)); } catch (_) {}
  };
  useEffect(() => { fetchComparison(); }, [runAId, runBId]);

  // Pre-populate Compare with demo runs when no live runs exist
  useEffect(() => {
    if (liveRuns.length === 0 && !runAId && !runBId) {
      setRunAId(DEMO_MULTI_AGENT.run_id);
      setRunBId(DEMO_BASELINE.run_id);
    }
  }, [liveRuns]);

  const handleRunStarted = (runId, mode) => {
    setActiveRunId(runId);
    setActiveRunMode(mode);
    setDemoMode(false);
    setHistory(null);
    setTab("History");
  };

  // Combined run list: live runs + demo runs (deduped)
  const allRuns = [
    ...liveRuns,
    ...DEMO_RUN_LIST.filter((d) => !liveRuns.find((r) => r.run_id === d.run_id)),
  ];

  return (
    <div style={S.app}>
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header style={S.header}>
        <div style={S.logoWrap}>
          <span style={S.logoIcon}>⚡</span>
          <span style={S.logo}>TuneFlow</span>
        </div>
        <div style={S.tag}>Self-Tuning Backend · Multi-Agent AI</div>
        {demoMode && <div style={S.demoTag}>DEMO MODE</div>}
        <nav style={S.nav}>
          {NAV.map((t) => (
            <button key={t} style={S.navBtn(tab === t)} onClick={() => setTab(t)}>{t}</button>
          ))}
        </nav>
      </header>

      {/* ── Main ───────────────────────────────────────────────────────── */}
      <main style={S.main}>

        {/* ── Run tab ── */}
        {tab === "Run" && (
          <>
            <RunLauncher onRunStarted={handleRunStarted} />
            {activeRunId && !demoMode && (
              <>
                <StatusBar runId={activeRunId} />
                <ConvergenceChart iterations={history?.iterations || []} title="Live Convergence" />
              </>
            )}
            {demoMode && (
              <ConvergenceChart iterations={history?.iterations || []} title="Demo Convergence" />
            )}
          </>
        )}

        {/* ── History tab ── */}
        {tab === "History" && (
          <>
            <RunPicker
              activeRunId={activeRunId}
              demoMode={demoMode}
              onSelect={selectLiveRun}
              onLoadDemo={loadDefaultDemo}
              onClear={clearRun}
              runs={allRuns}
            />
            {!demoMode && activeRunId && (
              <StatusBar runId={activeRunId} />
            )}
            {history ? (
              <>
                <ConvergenceChart iterations={history.iterations || []} />
                <IterationTable
                  iterations={history.iterations || []}
                  mode={activeRunMode || history.mode}
                />
              </>
            ) : (
              <HistoryEmpty onLoadDemo={loadDefaultDemo} />
            )}
          </>
        )}

        {/* ── Compare tab ── */}
        {tab === "Compare" && (
          <>
            <RunSelector
              onSelectA={setRunAId}
              onSelectB={setRunBId}
              selectedA={runAId}
              selectedB={runBId}
              extraRuns={DEMO_RUN_LIST}
            />
            {compareData && (
              <>
                <ComparisonChart runA={compareData.run_a} runB={compareData.run_b} />
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 8 }}>
                  <IterationTable
                    iterations={compareData.run_a?.iterations}
                    mode={compareData.run_a?.mode}
                  />
                  <IterationTable
                    iterations={compareData.run_b?.iterations}
                    mode={compareData.run_b?.mode}
                  />
                </div>
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
