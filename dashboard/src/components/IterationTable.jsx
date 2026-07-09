import React, { useState } from "react";

// ── Style tokens ──────────────────────────────────────────────────────────────
const S = {
  card: { background: "#1e2130", borderRadius: 12, padding: 20, marginBottom: 20 },
  h2: { fontSize: 15, fontWeight: 700, color: "#7dd3fc", marginBottom: 14 },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: { textAlign: "left", padding: "8px 10px", color: "#64748b", borderBottom: "1px solid #1e3a5f", whiteSpace: "nowrap" },
  td: { padding: "8px 10px", borderBottom: "1px solid #1e3a5f", verticalAlign: "top" },
  expandBtn: {
    background: "none", border: "1px solid #334155", borderRadius: 4,
    padding: "2px 8px", color: "#94a3b8", cursor: "pointer", fontSize: 11,
  },
  panel: { background: "#0f1117", borderRadius: 6, padding: "10px 12px", marginTop: 6, maxWidth: 320 },
  vetoBadge: { background: "#7c3aed", color: "#fff", borderRadius: 4, padding: "2px 6px", fontSize: 11, fontWeight: 700, marginLeft: 4 },
};

const SEVERITY_COLOR = { low: "#34d399", medium: "#f59e0b", high: "#f87171" };
const TREND_COLOR    = { improving: "#34d399", degrading: "#f87171", oscillating: "#f59e0b", stable: "#94a3b8", unknown: "#475569" };
const TREND_ICON     = { improving: "▲", degrading: "▼", oscillating: "◆", stable: "—", unknown: "?" };
const DIR_COLOR      = { increase: "#34d399", decrease: "#f87171", maintain: "#94a3b8", keep: "#94a3b8" };
const DIR_ICON       = { increase: "↑", decrease: "↓", maintain: "→", keep: "→" };

const PARAM_KEYS  = ["pool_size", "batch_size", "query_timeout_ms", "cache_ttl_seconds", "retry_interval_ms"];
const PARAM_LABEL = { pool_size: "Pool", batch_size: "Batch", query_timeout_ms: "Timeout", cache_ttl_seconds: "Cache TTL", retry_interval_ms: "Retry" };
const PARAM_UNIT  = { query_timeout_ms: "ms", cache_ttl_seconds: "s", retry_interval_ms: "ms" };

// ── Shared primitives ─────────────────────────────────────────────────────────

function Tag({ children, color = "#7dd3fc", bg = "#1e3a5f" }) {
  return (
    <span style={{ background: bg, color, borderRadius: 4, padding: "2px 7px", fontSize: 10, fontWeight: 700, display: "inline-block" }}>
      {children}
    </span>
  );
}

function SectionLabel({ children }) {
  return (
    <div style={{ color: "#475569", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
      {children}
    </div>
  );
}

// ── Config panel ──────────────────────────────────────────────────────────────

function ConfigPanel({ config }) {
  const keys = PARAM_KEYS.filter((k) => config[k] != null);
  if (!keys.length) return <span style={{ color: "#475569", fontSize: 11 }}>No config params</span>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      {keys.map((k) => (
        <div key={k} style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
          <span style={{ color: "#64748b", fontSize: 11 }}>{PARAM_LABEL[k] ?? k}</span>
          <span style={{ color: "#e2e8f0", fontWeight: 700, fontSize: 11 }}>
            {config[k]}{PARAM_UNIT[k] ?? ""}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Judge analysis panel ──────────────────────────────────────────────────────

function JudgePanel({ analysis }) {
  const sev   = analysis.severity;
  const trend = analysis.trend;
  const dirs  = analysis.recommended_direction;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>

      {/* Badges row */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 5, alignItems: "center" }}>
        {analysis.bottleneck && (
          <Tag>{analysis.bottleneck.replace(/_/g, " ")}</Tag>
        )}
        {sev && (
          <span style={{
            color: SEVERITY_COLOR[sev] ?? "#94a3b8",
            background: "#0f1117",
            border: `1px solid ${SEVERITY_COLOR[sev] ?? "#334155"}`,
            borderRadius: 4, padding: "1px 6px", fontSize: 10, fontWeight: 700
          }}>
            {sev}
          </span>
        )}
        {trend && trend !== "unknown" && (
          <span style={{ color: TREND_COLOR[trend] ?? "#94a3b8", fontSize: 11, fontWeight: 600 }}>
            {TREND_ICON[trend]} {trend}
          </span>
        )}
      </div>

      {/* Reasoning */}
      {analysis.reasoning && (
        <p style={{ color: "#cbd5e1", margin: 0, fontSize: 11, lineHeight: 1.65 }}>
          {analysis.reasoning}
        </p>
      )}

      {/* Recommended direction */}
      {dirs && Object.keys(dirs).length > 0 && (
        <div>
          <SectionLabel>Recommended</SectionLabel>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {Object.entries(dirs).map(([k, v]) => {
              const vStr = String(v).toLowerCase();
              return (
                <span key={k} style={{
                  background: "#0f2744",
                  color: DIR_COLOR[vStr] ?? "#94a3b8",
                  borderRadius: 4, padding: "2px 7px", fontSize: 10, fontWeight: 600
                }}>
                  {DIR_ICON[vStr] ?? "→"} {PARAM_LABEL[k] ?? k}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* Vision supplement */}
      {analysis.vision_supplement && !analysis.vision_supplement.includes("unavailable") && (
        <div style={{ color: "#a78bfa", fontSize: 10, fontStyle: "italic", borderTop: "1px solid #1e3a5f", paddingTop: 6 }}>
          👁 {analysis.vision_supplement}
        </div>
      )}
    </div>
  );
}

// ── Optimizer proposal panel ──────────────────────────────────────────────────

function OptimizerPanel({ proposal }) {
  const params = PARAM_KEYS.filter((k) => proposal[k] != null);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>

      {/* Param pills */}
      {params.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {params.map((k) => (
            <span key={k} style={{
              background: "#0f2744", color: "#7dd3fc",
              borderRadius: 4, padding: "3px 8px", fontSize: 10, fontWeight: 700
            }}>
              {PARAM_LABEL[k] ?? k} → {proposal[k]}{PARAM_UNIT[k] ?? ""}
            </span>
          ))}
        </div>
      )}

      {/* Rationale */}
      {proposal.rationale && (
        <p style={{ color: "#cbd5e1", margin: 0, fontSize: 11, lineHeight: 1.65 }}>
          {proposal.rationale}
        </p>
      )}

      {/* Change summary — show only if meaningfully different from rationale */}
      {proposal.change_summary && proposal.change_summary !== proposal.rationale && (
        <p style={{ color: "#64748b", margin: 0, fontSize: 10, lineHeight: 1.5, fontStyle: "italic" }}>
          {proposal.change_summary}
        </p>
      )}

      {/* Expected effect */}
      {proposal.expected_effect && (
        <div style={{ color: "#34d399", fontSize: 10, lineHeight: 1.4 }}>
          ✦ {proposal.expected_effect}
        </div>
      )}
    </div>
  );
}

// ── Final config pills (always visible, no expand needed) ────────────────────

function FinalConfigPills({ config }) {
  if (!config) return null;
  const params = PARAM_KEYS.filter((k) => config[k] != null);
  if (!params.length) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 3, marginBottom: 5 }}>
      {params.map((k) => (
        <span key={k} style={{
          background: "#0d2d1a",
          color: "#34d399",
          border: "1px solid #166534",
          borderRadius: 3,
          padding: "2px 7px",
          fontSize: 10,
          fontWeight: 700,
        }}>
          {PARAM_LABEL[k] ?? k}: {config[k]}{PARAM_UNIT[k] ?? ""}
        </span>
      ))}
    </div>
  );
}

// ── Expandable cell ───────────────────────────────────────────────────────────

function ExpandableCell({ label, value, renderContent }) {
  const [open, setOpen] = useState(false);
  if (!value) return <span style={{ color: "#475569" }}>—</span>;
  return (
    <div>
      <button style={S.expandBtn} onClick={() => setOpen((o) => !o)}>
        {open ? "▲ hide" : `▼ ${label}`}
      </button>
      {open && (
        <div style={S.panel}>
          {renderContent ? renderContent(value) : (
            <pre style={{ margin: 0, fontSize: 11, color: "#94a3b8", whiteSpace: "pre-wrap" }}>
              {JSON.stringify(value, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

// ── Veto badge ────────────────────────────────────────────────────────────────

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
      {vetoEvent.reason && (
        <div style={{ fontSize: 10, color: "#a78bfa", marginTop: 4 }}>{vetoEvent.reason}</div>
      )}
    </span>
  );
}

// ── Main table ────────────────────────────────────────────────────────────────

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
              const m      = it.metrics || {};
              const p95    = m.p95_latency_ms?.toFixed(0) ?? "—";
              const rps    = m.throughput_rps?.toFixed(1) ?? "—";
              const errPct = ((m.error_rate ?? 0) * 100).toFixed(2);
              const hasVeto = it.veto_event?.vetoed;

              return (
                <tr key={it.iteration_number} style={hasVeto ? { background: "#140028" } : {}}>
                  <td style={{ ...S.td, fontWeight: 700, color: "#e2e8f0" }}>{it.iteration_number}</td>
                  <td style={{ ...S.td, color: Number(p95) > 500 ? "#f87171" : "#34d399", fontWeight: 600 }}>{p95}</td>
                  <td style={{ ...S.td, color: "#94a3b8" }}>{rps}</td>
                  <td style={{ ...S.td, color: Number(errPct) > 1 ? "#f97316" : "#94a3b8" }}>{errPct}%</td>

                  <td style={S.td}>
                    <ExpandableCell
                      label="config"
                      value={it.config_applied}
                      renderContent={(v) => <ConfigPanel config={v} />}
                    />
                  </td>

                  {mode !== "baseline" && (
                    <td style={S.td}>
                      <ExpandableCell
                        label="analysis"
                        value={it.judge_analysis}
                        renderContent={(v) => <JudgePanel analysis={v} />}
                      />
                    </td>
                  )}

                  {mode !== "baseline" && (
                    <td style={S.td}>
                      <FinalConfigPills config={it.final_decision} />
                      <ExpandableCell
                        label="rationale"
                        value={it.optimizer_proposal}
                        renderContent={(v) => <OptimizerPanel proposal={v} />}
                      />
                    </td>
                  )}

                  {mode !== "baseline" && (
                    <td style={S.td}>
                      <VetoBadge vetoEvent={it.veto_event} />
                    </td>
                  )}

                  {mode === "baseline" && (
                    <td style={S.td}>
                      <ExpandableCell
                        label="decision"
                        value={it.baseline_decision}
                        renderContent={(v) => <OptimizerPanel proposal={v} />}
                      />
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
