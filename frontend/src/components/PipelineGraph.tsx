import {
  ClipboardCheck, FileSearch, FlaskConical, FolderTree, Hammer, Lightbulb, MessageSquareWarning, ScrollText,
  LucideIcon, ShieldQuestion, TestTubes, UserCheck,
} from "lucide-react";

import { Mode } from "../api";
import { NODE_LABELS } from "./ui";

// Snake layout: the investigation runs left -> right on top, the fix loop right -> left below.
const W = 146, H = 58, COL = 170, X0 = 20, ROW1 = 46, ROW2 = 186;
const POS: Record<string, [number, number]> = {
  analyze_bug: [0, ROW1], inspect_project: [1, ROW1], generate_hypotheses: [2, ROW1], collect_evidence: [3, ROW1],
  challenge_hypothesis: [4, ROW1], reproduce_bug: [5, ROW1],
  propose_fix: [5, ROW2], human_review: [4, ROW2], apply_fix: [3, ROW2], run_tests: [2, ROW2], final_report: [1, ROW2],
};
const ICONS: Record<string, LucideIcon> = {
  analyze_bug: ScrollText, inspect_project: FolderTree, generate_hypotheses: Lightbulb, collect_evidence: FileSearch,
  challenge_hypothesis: ShieldQuestion, reproduce_bug: FlaskConical, propose_fix: Hammer, human_review: UserCheck,
  apply_fix: ClipboardCheck, run_tests: TestTubes, final_report: MessageSquareWarning,
};

const x = (n: string) => X0 + POS[n][0] * COL;
const y = (n: string) => POS[n][1];
const cx = (n: string) => x(n) + W / 2;
const cy = (n: string) => y(n) + H / 2;

type Edge = { from: string; to: string; d: string; loop?: boolean; label?: string };

function straight(a: string, b: string): string {
  if (y(a) === y(b)) {
    const left = x(a) < x(b);
    return `M${left ? x(a) + W : x(a)},${cy(a)} L${left ? x(b) : x(b) + W},${cy(b)}`;
  }
  return `M${cx(a)},${y(a) + H} L${cx(b)},${y(b)}`;
}
function arc(a: string, b: string, lift: number, below = false): string {
  const ya = below ? y(a) + H : y(a), yb = below ? y(b) + H : y(b);
  return `M${cx(a)},${ya} C${cx(a)},${ya + lift} ${cx(b)},${yb + lift} ${cx(b)},${yb}`;
}

const EDGES: Edge[] = [
  ["analyze_bug", "inspect_project"], ["inspect_project", "generate_hypotheses"], ["generate_hypotheses", "collect_evidence"],
  ["collect_evidence", "challenge_hypothesis"], ["challenge_hypothesis", "reproduce_bug"], ["reproduce_bug", "propose_fix"],
  ["propose_fix", "human_review"], ["human_review", "apply_fix"], ["apply_fix", "run_tests"], ["run_tests", "final_report"],
].map(([a, b]) => ({ from: a, to: b, d: straight(a, b) }));

const LOOPS: Edge[] = [
  { from: "collect_evidence", to: "reproduce_bug", d: arc("collect_evidence", "reproduce_bug", -34), loop: true, label: "fast mode" },
  { from: "reproduce_bug", to: "generate_hypotheses", d: arc("reproduce_bug", "generate_hypotheses", -46), loop: true, label: "not reproduced" },
  { from: "human_review", to: "propose_fix", d: arc("human_review", "propose_fix", 30, true), loop: true, label: "revise" },
  { from: "run_tests", to: "propose_fix", d: arc("run_tests", "propose_fix", 54, true), loop: true, label: "tests fail → retry" },
  {
    from: "human_review", to: "generate_hypotheses", loop: true, label: "reinvestigate",
    d: `M${cx("human_review") - 30},${y("human_review")} C${cx("human_review") - 30},${ROW1 + H + 48} ${cx("generate_hypotheses") + 30},${ROW2 - 48} ${cx("generate_hypotheses") + 30},${ROW1 + H}`,
  },
];

export interface PipelineProps {
  visits: Record<string, number>;
  transitions: Set<string>;
  current: string | null;
  waiting: boolean;
  running: boolean;
  mode: Mode;
}

export default function PipelineGraph({ visits, transitions, current, waiting, running, mode }: PipelineProps) {
  const edgeClass = (e: Edge) => {
    const done = transitions.has(`${e.from}>${e.to}`);
    return `pedge${e.loop ? " loop" : ""}${done ? " done" : ""}`;
  };
  return (
    <svg className="chart pipeline" viewBox="0 0 1040 290" role="img" aria-label="Investigation graph progress">
      <defs>
        <linearGradient id="edgeGrad" x1="0" x2="1">
          <stop offset="0" stopColor="#22d3ee" />
          <stop offset="1" stopColor="#8b5cf6" />
        </linearGradient>
        <linearGradient id="nodeActive" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="rgba(34,211,238,0.22)" />
          <stop offset="1" stopColor="rgba(139,92,246,0.22)" />
        </linearGradient>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" fill="rgba(148,163,196,0.45)" />
        </marker>
        <marker id="arrowOn" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" fill="#8b9cff" />
        </marker>
      </defs>

      <text x={X0} y={20} style={{ fontSize: 10.5, letterSpacing: "0.12em", fill: "var(--text-3)" }}>INVESTIGATE</text>
      <text x={X0 + COL} y={ROW2 + H / 2 + 4} style={{ fontSize: 10.5, letterSpacing: "0.12em", fill: "var(--text-3)" }} textAnchor="end" dx={-18}>FIX &amp; VERIFY</text>

      {[...EDGES, ...LOOPS].map((e) => {
        const done = transitions.has(`${e.from}>${e.to}`);
        if (e.loop && e.label === "fast mode" && mode !== "baseline" && !done) return null;
        return (
          <path key={`${e.from}-${e.to}`} className={edgeClass(e)} d={e.d} markerEnd={done ? "url(#arrowOn)" : "url(#arrow)"} />
        );
      })}
      {LOOPS.map((e) => {
        if (e.label === "fast mode" && mode !== "baseline") return null;
        const [lx, ly] = loopLabelPos(e);
        const done = transitions.has(`${e.from}>${e.to}`);
        return (
          <text key={`l-${e.from}-${e.to}`} x={lx} y={ly} textAnchor="middle" style={{ fontSize: 10, fill: done ? "#b8c6ff" : "var(--text-3)" }}>
            {e.label}
          </text>
        );
      })}

      {Object.keys(POS).map((n) => {
        const Icon = ICONS[n];
        const count = visits[n] ?? 0;
        const isCurrent = n === current && running;
        const isWaiting = waiting && n === "human_review";
        const skipped = mode === "baseline" && n === "challenge_hypothesis";
        const visited = count > 0;
        const stroke = isWaiting ? "#fab219" : isCurrent ? "#22d3ee" : visited ? "rgba(139,156,255,0.55)" : "rgba(148,163,196,0.2)";
        const fill = isCurrent ? "url(#nodeActive)" : isWaiting ? "rgba(250,178,25,0.1)" : visited ? "rgba(24,33,58,0.95)" : "rgba(14,19,34,0.9)";
        return (
          <g key={n} className={`pnode${isCurrent || isWaiting ? " active" : ""}`} opacity={skipped ? 0.4 : 1}>
            <rect className="frame" x={x(n)} y={y(n)} width={W} height={H} rx={12} fill={fill} stroke={stroke} strokeWidth={isCurrent || isWaiting ? 1.8 : 1.2}
              strokeDasharray={skipped ? "4 4" : undefined} />
            <rect x={x(n) + 10} y={y(n) + 14} width={30} height={30} rx={8} fill={visited || isCurrent ? "rgba(109,139,255,0.16)" : "rgba(148,163,196,0.07)"} />
            <Icon x={x(n) + 17} y={y(n) + 21} size={16} strokeWidth={2} color={isWaiting ? "#fab219" : isCurrent ? "#22d3ee" : visited ? "#b8c6ff" : "#6f7a92"} />
            <text x={x(n) + 50} y={y(n) + 26} style={{ fontSize: 12, fontWeight: 650, fill: visited || isCurrent || isWaiting ? "var(--text)" : "var(--text-2)" }}>
              {NODE_LABELS[n]}
            </text>
            <text x={x(n) + 50} y={y(n) + 43} style={{ fontSize: 10.5, fill: isWaiting ? "#fcd37a" : isCurrent ? "#67e8f9" : "var(--text-3)" }}>
              {skipped ? "skipped (fast)" : isWaiting ? "waiting for you" : isCurrent ? "working…" : visited ? (count > 1 ? `done ×${count}` : "done") : "pending"}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function loopLabelPos(e: Edge): [number, number] {
  switch (e.label) {
    case "fast mode": return [(cx(e.from) + cx(e.to)) / 2, ROW1 - 22];
    case "not reproduced": return [(cx(e.from) + cx(e.to)) / 2, ROW1 - 32];
    case "revise": return [(cx(e.from) + cx(e.to)) / 2, ROW2 + H + 30];
    case "tests fail → retry": return [(cx(e.from) + cx(e.to)) / 2 + 40, ROW2 + H + 52];
    default: return [(cx(e.from) + cx(e.to)) / 2, (ROW1 + H + ROW2) / 2 + 4];
  }
}
