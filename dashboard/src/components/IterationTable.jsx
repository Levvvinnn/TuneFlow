import React, { useState } from "react";

const S = {
  card: { background: "#1e2130", borderRadius: 12, padding: 20, marginBottom: 20 },
  h2: { fontSize: 15, fontWeight: 700, color: "#7dd3fc", marginBottom: 14 },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: { textAlign: "left", padding: "8px 10px", color: "#64748b", borderBottom: "1px solid #1e3a5f", whiteSpace: "nowrap" },
  td: { padding: "8px 10px", borderBottom: "1px solid #1e3a5f", verticalAlign: "top" },
  vetoBadge: { background: "#7c3aed", color: "#fff", borderRadius: 4, padding: "2px 6px", fontSize: 11, fontWeight: 700, marginLeft: 4 },
  goodBadge: { background: "#065f46", color: "#34d399", borderRadius: 4, padding: "2px 6px", fontSize: 11, fontWeight: 700 },
  expandBtn: { background: "none", border: "1px solid #334155", borderRadius: 4, padding: "2px 8px", color: "#94a3b8", cursor: "pointer", fontSize: 11 },
  pre: { background: "#0f1117", borderRadius: 6, padding: 10, fontSize: 11, color: "#94a3b8", overflowX: "auto", maxWidth: 400, whiteSpace: "pre-wrap" },
};

function VetoBadge({ vetoEvent }) {
  if (!vetoEvent?.vetoed) return null;
  return (
    <span>
      <span style={S.vetoBadge}>VETOED</span>
      {vetoEvent.revision_accepted === false && (
        <span style={{ ...S.vetoBadge, background: "#dc2626", marginLeft: 4 }}>FORCED FALLBACK</span>
      )}
      {vetoEvent.revision_accepted === true && (
        <span style={{ ...S.vetoBadge, background: "#059669", marginLeft: 4 }}>REVISION ACCEPTED</span>
      )}
    </span>
  );
}

function ExpandableCell({ label, value }) {
  const [open, setOpen] = useState(false);
  if (!value) return <span style={{ color: "#475569" }}>—</span>;
  return (
    <div>
      <button style={S.expandBtn} onClick={() => setOpen((o) => !o)}>{open ? "▲ hide" : `▼ ${label}`}</button>
      {open && <pre style={S.pre}>{JSON.stringify(value, null, 2)}</pre>}
    </div>
  );
}

export default function IterationTable({ iterations, mode }) {
  if (!iterations || iterations.length === 0) {
    return (
      <div style={S.card}>
        <div style={S.h2}>Iteration History</div>
        <div style={{ color: "#64748b" }}>No iterations recorded yet.</div>
      </div>
    );
  }

  return (
    <div style={S.card}>
      <div style={S.h2}>Iteration History</div>
      <div style={{ overflowX: "auto" }}>
        <table style={S.table}>
          <thead>
            <tr>
              <th style={S.th}>#</th>
              <th style={S.th}>p95 (ms)</th>
              <th style={S.th}>RPS</th>
              <th style={S.th}>Error %</th>
              <th style={S.th}>Config Applied</th>
              {mode !== "baseline" && <th style={S.th}>Judge Analysis</th>}
              {mode !== "baseline" && <th style={S.th}>Optimizer Proposal</th>}
              {mode !== "baseline" && <th style={S.th}>Veto</th>}
              {mode === "baseline" && <th style={S.th}>God-Agent Decision</th>}
            </tr>
          </thead>
          <tbody>
            {iterations.map((it) => {
              const m = it.metrics || {};
              const p95 = m.p95_latency_ms?.toFixed(0) ?? "—";
              const rps = m.throughput_rps?.toFixed(1) ?? "—";
              const errPct = ((m.error_rate ?? 0) * 100).toFixed(2);
              const hasVeto = it.veto_event?.vetoed;
              return (
                <tr key={it.iteration_number} style={hasVeto ? { background: "#1a0033" } : {}}>
                  <td style={{ ...S.td, fontWeight: 700 }}>{it.iteration_number}</td>
                  <td style={{ ...S.td, color: Number(p95) > 500 ? "#f87171" : "#34d399" }}>{p95}</td>
                  <td style={S.td}>{rps}</td>
                  <td style={{ ...S.td, color: Number(errPct) > 1 ? "#f97316" : "#94a3b8" }}>{errPct}%</td>
                  <td style={S.td}><ExpandableCell label="config" value={it.config_applied} /></td>
                  {mode !== "baseline" && (
                    <td style={S.td}>
                      <ExpandableCell label="analysis" value={it.judge_analysis} />
                    </td>
                  )}
                  {mode !== "baseline" && (
                    <td style={S.td}>
                      <ExpandableCell label="proposal" value={it.optimizer_proposal} />
                    </td>
                  )}
                  {mode !== "baseline" && (
                    <td style={S.td}>
                      <VetoBadge vetoEvent={it.veto_event} />
                      {it.veto_event?.vetoed && (
                        <div style={{ fontSize: 11, color: "#a78bfa", marginTop: 4 }}>
                          {it.veto_event.reason}
                        </div>
                      )}
                    </td>
                  )}
                  {mode === "baseline" && (
                    <td style={S.td}>
                      <ExpandableCell label="decision" value={it.baseline_decision} />
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
