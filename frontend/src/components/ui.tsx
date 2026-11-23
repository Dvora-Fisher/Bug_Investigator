import { AlertTriangle, Ban, CheckCircle2, CircleDashed, Clock, FileCode2, PauseCircle, X, XCircle } from "lucide-react";
import { ReactNode, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { api, Outcome, Status } from "../api";

// ------------------------------------------------------------------ formatting

export const pct = (v: number | null | undefined, digits = 0) => (v == null ? "n/a" : `${(v * 100).toFixed(digits)}%`);
export const usd = (v: number | null | undefined, digits = 4) => `$${(v ?? 0).toFixed(digits)}`;

export function timeAgo(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export const NODE_LABELS: Record<string, string> = {
  analyze_bug: "Analyze report",
  inspect_project: "Inspect project",
  generate_hypotheses: "Hypotheses",
  collect_evidence: "Collect evidence",
  challenge_hypothesis: "Challenge",
  reproduce_bug: "Reproduce",
  propose_fix: "Propose fix",
  human_review: "Human review",
  apply_fix: "Apply fix",
  run_tests: "Run tests",
  final_report: "Final report",
};

export const MODE_LABEL: Record<string, string> = { improved: "Thorough", baseline: "Fast" };

// ------------------------------------------------------------------ status

const STATUS: Record<Status, { label: string; cls: string; icon: ReactNode }> = {
  running: { label: "Running", cls: "badge-info", icon: <span className="dot live" /> },
  waiting_for_human: { label: "Needs review", cls: "badge-warn", icon: <PauseCircle size={13} /> },
  done: { label: "Completed", cls: "badge-good", icon: <CheckCircle2 size={13} /> },
  failed: { label: "Failed", cls: "badge-bad", icon: <XCircle size={13} /> },
  stopped: { label: "Stopped", cls: "badge-neutral", icon: <CircleDashed size={13} /> },
  cancelled: { label: "Cancelled", cls: "badge-neutral", icon: <Ban size={13} /> },
};

export function StatusBadge({ status }: { status: Status }) {
  const s = STATUS[status];
  return <span className={`badge ${s.cls}`}>{s.icon}{s.label}</span>;
}

export const OUTCOME: Record<Outcome, { label: string; cls: string; tone: "good" | "warn" | "bad" | "neutral"; icon: ReactNode; help: string }> = {
  fixed_and_verified: { label: "Fixed & verified", cls: "badge-good", tone: "good", icon: <CheckCircle2 size={14} />,
    help: "The bug was reproduced, the fix was applied, and the tests prove it works." },
  fixed_unverified: { label: "Fixed, not verified", cls: "badge-warn", tone: "warn", icon: <AlertTriangle size={14} />,
    help: "A fix was applied, but nothing proves it works (no reproduction, or the code cannot run here)." },
  fix_failed: { label: "Fix failed", cls: "badge-bad", tone: "bad", icon: <XCircle size={14} />,
    help: "The fix was applied, but the tests still fail." },
  no_fix: { label: "No fix", cls: "badge-neutral", tone: "neutral", icon: <CircleDashed size={14} />,
    help: "No fix was approved, so nothing was changed." },
  stopped: { label: "Stopped", cls: "badge-neutral", tone: "neutral", icon: <Clock size={14} />,
    help: "The investigation stopped early (budget or an invalid model answer)." },
};

export function OutcomeBadge({ outcome }: { outcome: Outcome }) {
  const o = OUTCOME[outcome];
  return <span className={`badge ${o.cls}`}>{o.icon}{o.label}</span>;
}

const LANG_COLORS: Record<string, string> = {
  Python: "#4b8bbe", TypeScript: "#3178c6", JavaScript: "#e2c400", "C#": "#9b4f96", Go: "#00add8", Java: "#e76f00",
};
export function LangBadge({ lang }: { lang: string }) {
  const c = LANG_COLORS[lang] ?? "#8b95a9";
  return <span className="lang" style={{ color: c, borderColor: `${c}55`, background: `${c}14` }}>{lang}</span>;
}

// ------------------------------------------------------------------ diff

export function DiffView({ diff }: { diff: string }) {
  if (!diff.trim()) return <div className="empty small">No changes.</div>;
  const files: { name: string; lines: string[] }[] = [];
  for (const line of diff.split("\n")) {
    if (line.startsWith("--- ")) continue;
    if (line.startsWith("+++ ")) {
      files.push({ name: line.slice(4).replace(/^b\//, ""), lines: [] });
      continue;
    }
    if (!files.length) files.push({ name: "changes", lines: [] });
    files[files.length - 1].lines.push(line);
  }
  return (
    <div className="stack" style={{ gap: 12 }}>
      {files.map((f, i) => {
        const adds = f.lines.filter((l) => l.startsWith("+")).length;
        const dels = f.lines.filter((l) => l.startsWith("-")).length;
        return (
          <div className="diff" key={i}>
            <div className="diff-file">
              <FileCode2 size={14} />
              <span style={{ flex: 1 }}>{f.name}</span>
              <span style={{ color: "var(--good)" }}>+{adds}</span>
              <span style={{ color: "var(--bad)" }}>−{dels}</span>
            </div>
            <div className="diff-lines">
              {f.lines.map((l, j) => {
                const kind = l.startsWith("@@") ? "hunk" : l.startsWith("+") ? "add" : l.startsWith("-") ? "del" : "";
                return (
                  <div className={`diff-line ${kind}`} key={j}>
                    <span className="sign">{kind === "add" ? "+" : kind === "del" ? "−" : ""}</span>
                    <span>{kind === "hunk" ? l : l.slice(1) || " "}</span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ------------------------------------------------------------------ modal + file viewer

export function Modal({ title, onClose, children }: { title: ReactNode; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  // Portal to <body>: an animated (transformed) ancestor would otherwise make position:fixed page-relative.
  return createPortal(
    <div className="modal-back" onClick={onClose}>
      <div className="card modal fade-in" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="card-head">
          <div className="row" style={{ minWidth: 0 }}>{title}</div>
          <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close"><X size={16} /></button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}

export function FileViewer({ threadId, path, onClose }: { threadId: string; path: string; onClose: () => void }) {
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api.file(threadId, path).then(setText).catch((e) => setError(String(e.message ?? e)));
  }, [threadId, path]);
  const lines = (text ?? "").split("\n");
  return (
    <Modal title={<><FileCode2 size={15} /><span className="mono">{path}</span></>} onClose={onClose}>
      {error ? <div className="card-body"><div className="callout callout-bad">{error}</div></div>
        : text === null ? <div className="card-body"><div className="skeleton" style={{ height: 220 }} /></div>
        : (
          <pre className="code">
            {lines.map((l, i) => (
              <div key={i}><span style={{ color: "var(--text-3)", userSelect: "none", display: "inline-block", width: 42 }}>{i + 1}</span>{l}</div>
            ))}
          </pre>
        )}
    </Modal>
  );
}

// ------------------------------------------------------------------ tooltip

export interface Tip { x: number; y: number; title: string; rows: [string, string][] }

export function Tooltip({ tip }: { tip: Tip | null }) {
  if (!tip) return null;
  const left = Math.min(tip.x + 14, window.innerWidth - 220);
  return (
    <div className="tooltip" style={{ left, top: tip.y + 14 }}>
      <div className="t-title">{tip.title}</div>
      {tip.rows.map(([k, v]) => (
        <div className="t-row" key={k}><span>{k}</span><b>{v}</b></div>
      ))}
    </div>
  );
}

export function Kpi({ label, icon, value, unit, foot }: { label: string; icon: ReactNode; value: ReactNode; unit?: string; foot?: ReactNode }) {
  return (
    <div className="card kpi">
      <div className="kpi-label"><span className="kpi-icon">{icon}</span>{label}</div>
      <div className="kpi-value">{value}{unit && <small>{unit}</small>}</div>
      {foot && <div className="kpi-foot">{foot}</div>}
    </div>
  );
}
