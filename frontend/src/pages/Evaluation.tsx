import { AlertTriangle, Check, Coins, FlaskConical, Languages, Layers, Lightbulb, Minus, ShieldCheck, Target, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, Experiment } from "../api";
import { Group, GroupedBars, Legend, MetricBars, MetricRow } from "../components/Charts";
import { Kpi, LangBadge, pct, usd } from "../components/ui";

const METRICS: { key: string; label: string; lowerIsBetter?: boolean; cost?: boolean }[] = [
  { key: "file_localization", label: "File localization" },
  { key: "function_localization", label: "Function localization" },
  { key: "root_cause_accuracy", label: "Root cause (LLM judge)" },
  { key: "bug_reproduced", label: "Bug reproduced" },
  { key: "fix_success", label: "Fix passes hidden tests" },
  { key: "unsupported_claim_rate", label: "Unsupported claims", lowerIsBetter: true },
  { key: "cost_usd", label: "Cost per investigation", lowerIsBetter: true, cost: true },
];
const MATRIX_COLS = [
  { key: "file_localization", label: "File" },
  { key: "root_cause_accuracy", label: "Cause" },
  { key: "bug_reproduced", label: "Repro" },
  { key: "fix_success", label: "Fix" },
];
const ROUND_NOTES = ["before fixes", "+ strict schema", "+ edits first"];

export default function Evaluation() {
  const [experiments, setExperiments] = useState<Experiment[] | null>(null);
  const [set, setSet] = useState<"basic" | "hard">("hard");
  const [loadError, setLoadError] = useState("");
  useEffect(() => {
    api.evaluation().then(setExperiments).catch((e) => {
      setLoadError(e?.status === 404
        ? "The API server is running an older version without evaluation data. Restart the backend (uvicorn) and reload."
        : "Could not reach the API server. Make sure the backend is running on port 8000.");
      setExperiments([]);
    });
  }, []);

  const data = useMemo(() => {
    const all = experiments ?? [];
    const by = (mode: string, diff: string) => all.filter((e) => e.mode === mode && e.difficulty === diff);
    const bBasic = by("baseline", "basic"), iBasic = by("improved", "basic");
    const final = { baseline: bBasic[bBasic.length - 1], improved: iBasic[iBasic.length - 1] };
    const hard = { baseline: by("baseline", "hard").pop(), improved: by("improved", "hard").pop() };
    const rounds: Group[] = bBasic.map((b, i) => ({
      label: i === bBasic.length - 1 ? "Final" : `Round ${i + 1}`, sub: ROUND_NOTES[i],
      values: { baseline: b.summary.fix_success ?? null, improved: iBasic[i]?.summary.fix_success ?? null },
    }));
    if (hard.baseline) rounds.push({ label: "Hard set", sub: "5 new bugs", values: { baseline: hard.baseline.summary.fix_success ?? null, improved: hard.improved?.summary.fix_success ?? null } });
    const spend = all.reduce((s, e) => s + e.total_spend_usd, 0);
    const languages = new Set(all.flatMap((e) => e.rows.map((r) => r.language)));
    return { final, hard, rounds, spend, languages };
  }, [experiments]);

  if (experiments === null) return <div className="page"><div className="skeleton" style={{ height: 400 }} /></div>;
  if (loadError) return <div className="page"><div className="callout callout-bad"><AlertTriangle size={17} /><div>{loadError}</div></div></div>;
  if (!experiments.length) return <div className="page"><div className="callout callout-info">No saved experiments in evaluation/results yet.</div></div>;

  const pair = set === "basic" ? data.final : data.hard;
  const metricRows: MetricRow[] = METRICS.map((m) => {
    const vals = { baseline: pair.baseline?.summary[m.key] ?? null, improved: pair.improved?.summary[m.key] ?? null };
    return m.cost
      ? { label: m.label, values: vals, lowerIsBetter: true, max: Math.max(vals.baseline ?? 0, vals.improved ?? 0) * 1.15 || 1, format: (v: number) => usd(v) }
      : { label: m.label, values: vals, lowerIsBetter: m.lowerIsBetter };
  });
  const scenarioIds = pair.baseline?.rows.map((r) => r.scenario) ?? [];

  return (
    <div className="page fade-in">
      <div className="page-head">
        <div>
          <div className="eyebrow">Evaluation · LangSmith</div>
          <h1>Measured, not assumed. <span className="grad-text">Baseline vs. Improved.</span></h1>
          <p className="lead">Every number below comes from a real experiment: real model, real Docker sandbox, and hidden tests the agent never sees. A fix only counts if those hidden tests pass.</p>
        </div>
        <Legend />
      </div>

      <div className="grid cols-4" style={{ marginBottom: 18 }}>
        <Kpi label="Scenarios" icon={<Layers size={15} />} value={(data.final.baseline?.scenarios ?? 0) + (data.hard.baseline?.scenarios ?? 0)} foot="20 basic · 5 hard" />
        <Kpi label="Languages" icon={<Languages size={15} />} value={data.languages.size} foot={[...data.languages].join(" · ")} />
        <Kpi label="Final fix success" icon={<ShieldCheck size={15} />} value={pct(data.final.baseline?.summary.fix_success)} foot={<>both modes · hidden tests · up from {pct(data.rounds[0]?.values.improved)}</>} />
        <Kpi label="Total evaluation spend" icon={<Coins size={15} />} value={usd(data.spend, 2)} foot={`${experiments.length} experiments`} />
      </div>

      <div className="grid eval-top" style={{ marginBottom: 18 }}>
        <section className="card">
          <div className="card-head"><div><h2>What the traces taught us</h2><div className="sub">Fix success on hidden tests, per round of trace-driven changes</div></div></div>
          <div className="card-body"><GroupedBars groups={data.rounds} labelGroups={[0, data.rounds.length - 2, data.rounds.length - 1]} /></div>
        </section>
        <section className="card">
          <div className="card-head"><div><h2>Key findings</h2><div className="sub">From reading the LangSmith traces</div></div></div>
          <div className="card-body stack" style={{ gap: 14 }}>
            <Insight icon={<Target size={15} />} title="The diagnosis was right; the fix form was broken"
              text="Round 1 found the right file and cause in 100% of runs. 42 of 44 fix submissions were malformed tool calls. Two schema changes took Improved from 72% to 100%." />
            <Insight icon={<Lightbulb size={15} />} title="strict guarantees shape, not content"
              text="After strict tool use, every rejected call had an empty edits list. Putting edits first and requiring one item fixed it." />
            <Insight icon={<FlaskConical size={15} />} title="The critique step did not pay off"
              text="Same accuracy on basic bugs, one miss on the hard set, and about 40% more cost. No evidence it helps on this benchmark." />
            <Insight icon={<AlertTriangle size={15} />} title="'Verified' now requires a reproduction" warn
              text="On one hard bug Improved wrote 'Unconfirmed' as the root cause but still reported 'verified'. The report now refuses that combination." />
          </div>
        </section>
      </div>

      <div className="row-between" style={{ margin: "26px 0 14px" }}>
        <h2 style={{ fontSize: 18 }}>Metrics by dataset</h2>
        <div className="segmented">
          <button className={set === "hard" ? "on" : ""} onClick={() => setSet("hard")}>Hard · 5</button>
          <button className={set === "basic" ? "on" : ""} onClick={() => setSet("basic")}>Basic · 20</button>
        </div>
      </div>

      <div className="grid eval-pair">
        <section className="card">
          <div className="card-head"><div><h2>All metrics</h2><div className="sub mono">{pair.baseline?.name} vs {pair.improved?.name}</div></div></div>
          <div className="card-body"><MetricBars rows={metricRows} /></div>
        </section>
        <section className="card">
          <div className="card-head"><div><h2>Per scenario</h2><div className="sub">Every investigation, both modes</div></div>
            <div className="row tiny faint" style={{ gap: 10 }}><span className="row" style={{ gap: 4 }}><Check size={12} color="var(--good)" />pass</span><span className="row" style={{ gap: 4 }}><X size={12} color="var(--bad)" />fail</span><span className="row" style={{ gap: 4 }}><Minus size={12} />n/a</span></div>
          </div>
          <div className="card-body" style={{ maxHeight: 520, overflowY: "auto" }}>
            <table className="matrix">
              <thead>
                <tr><th className="left" rowSpan={2}>Scenario</th>
                  <th colSpan={4} style={{ color: "var(--series-baseline)" }}>Baseline</th><th colSpan={4} style={{ color: "var(--series-improved)" }}>Improved</th></tr>
                <tr>{[...MATRIX_COLS, ...MATRIX_COLS].map((c, i) => <th key={i}>{c.label}</th>)}</tr>
              </thead>
              <tbody>
                {scenarioIds.map((sid) => {
                  const b = pair.baseline?.rows.find((r) => r.scenario === sid);
                  const im = pair.improved?.rows.find((r) => r.scenario === sid);
                  return (
                    <tr key={sid}>
                      <td className="left" style={{ fontWeight: 500, paddingRight: 10, whiteSpace: "nowrap" }}>
                        <div className="row" style={{ gap: 8 }}>{b && <LangBadge lang={b.language} />}<span className="mono tiny">{sid.replace(/^(py|ts|js|cs|go|java)-(hard-)?/, "")}</span></div>
                      </td>
                      {[b, im].flatMap((row, side) => MATRIX_COLS.map((c) => <Cell key={`${side}-${c.key}`} v={row?.scores[c.key] ?? null} />))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}

function Cell({ v }: { v: number | null }) {
  if (v == null) return <td className="cell-na" title="not applicable"><Minus size={12} /></td>;
  const cls = v >= 1 ? "cell-pass" : v > 0 ? "cell-part" : "cell-fail";
  return (
    <td className={cls} title={`${Math.round(v * 100)}%`}>
      {v >= 1 ? <Check size={13} /> : v > 0 ? <span className="tiny">{Math.round(v * 100)}</span> : <X size={13} />}
    </td>
  );
}

function Insight({ icon, title, text, warn }: { icon: JSX.Element; title: string; text: string; warn?: boolean }) {
  return (
    <div className="row" style={{ alignItems: "flex-start", gap: 12 }}>
      <span className="kpi-icon" style={{ flex: "none", ...(warn ? { background: "var(--warn-bg)", borderColor: "rgba(250,178,25,0.35)", color: "var(--warn)" } : {}) }}>{icon}</span>
      <div><div style={{ fontWeight: 650 }}>{title}</div><div className="small muted">{text}</div></div>
    </div>
  );
}
