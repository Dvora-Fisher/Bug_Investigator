import { ArrowRight, Bug, CheckCircle2, Coins, FlaskConical, GitBranch, PauseCircle, ShieldCheck, Sparkles, UserCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, Experiment, Health, InvestigationSummary } from "../api";
import { Ring } from "../components/Charts";
import { Kpi, MODE_LABEL, pct, StatusBadge, timeAgo, usd } from "../components/ui";

export default function Overview({ health }: { health: Health | null }) {
  const [items, setItems] = useState<InvestigationSummary[] | null>(null);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    const load = () => api.list().then(setItems).catch(() => setItems([]));
    load();
    api.evaluation().then(setExperiments).catch(() => setExperiments([]));
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const latest = (mode: string, difficulty: string) =>
    [...experiments].reverse().find((e) => e.mode === mode && e.difficulty === difficulty);
  const finalImproved = latest("improved", "basic");
  const finalBaseline = latest("baseline", "basic");
  const waiting = (items ?? []).filter((i) => i.status === "waiting_for_human");
  const running = (items ?? []).filter((i) => i.status === "running").length;

  return (
    <div className="page fade-in">
      <div className="page-head">
        <div>
          <div className="eyebrow">Overview</div>
          <h1>Find the root cause. <span className="grad-text">Prove the fix.</span></h1>
          <p className="lead">
            An AI agent that investigates bugs like a senior engineer: it forms hypotheses, gathers evidence from the
            code, reproduces the bug in an isolated sandbox, and only changes code after you approve.
          </p>
        </div>
        <Link to="/new" className="btn btn-primary btn-lg"><Sparkles size={17} />New investigation</Link>
      </div>

      <div className="grid cols-4" style={{ marginBottom: 18 }}>
        <Kpi label="Investigations" icon={<Bug size={15} />} value={items?.length ?? "–"}
          foot={<>{running} running · {waiting.length} waiting for review</>} />
        <Kpi label="Verified fix rate" icon={<ShieldCheck size={15} />} value={pct(finalImproved?.summary.fix_success)}
          foot={<>hidden tests · {finalImproved?.scenarios ?? "–"} evaluation scenarios</>} />
        <Kpi label="Cost per investigation" icon={<Coins size={15} />}
          value={finalBaseline?.summary.cost_usd != null ? usd(finalBaseline.summary.cost_usd) : "–"}
          foot={<>baseline · improved {finalImproved?.summary.cost_usd != null ? usd(finalImproved.summary.cost_usd) : "–"}</>} />
        <div className="card kpi row" style={{ justifyContent: "space-between" }}>
          <div>
            <div className="kpi-label"><span className="kpi-icon"><Coins size={15} /></span>Monthly budget</div>
            <div className="kpi-value">{health ? usd(health.month_spend_usd, 2) : "–"}</div>
            <div className="kpi-foot">of {health ? usd(health.monthly_budget_usd, 0) : "–"} hard limit</div>
          </div>
          {health && <Ring value={health.month_spend_usd} max={health.monthly_budget_usd} label="Monthly spend" />}
        </div>
      </div>

      {waiting.length > 0 && (
        <div className="callout callout-warn fade-in" style={{ marginBottom: 18, alignItems: "center" }}>
          <PauseCircle size={18} />
          <div style={{ flex: 1 }}>
            <b>{waiting.length} investigation{waiting.length > 1 ? "s" : ""} waiting for your decision.</b>{" "}
            The agent proposed a fix and will not touch the code until you approve it.
          </div>
          <button className="btn btn-sm" onClick={() => navigate(`/investigations/${waiting[0].thread_id}`)}>Review now <ArrowRight size={14} /></button>
        </div>
      )}

      <div className="split">
        <div className="card">
          <div className="card-head">
            <div><h2>Recent investigations</h2><div className="sub">Live status, refreshed every few seconds</div></div>
          </div>
          {items === null ? (
            <div className="card-body stack" style={{ gap: 10 }}>{[0, 1, 2].map((i) => <div key={i} className="skeleton" style={{ height: 44 }} />)}</div>
          ) : items.length === 0 ? (
            <div className="empty">
              <FlaskConical size={34} />
              <div style={{ color: "var(--text-2)", fontWeight: 600 }}>No investigations yet</div>
              <div className="small" style={{ margin: "4px 0 16px" }}>Pick one of the built-in sample bugs to see the agent work.</div>
              <Link to="/new" className="btn btn-primary"><Sparkles size={15} />Start the first one</Link>
            </div>
          ) : (
            <table className="table" style={{ tableLayout: "fixed" }}>
              <colgroup><col /><col style={{ width: 112 }} /><col style={{ width: 142 }} /><col style={{ width: 104 }} /></colgroup>
              <thead><tr><th>Bug</th><th>Mode</th><th>Status</th><th style={{ textAlign: "right" }}>Started</th></tr></thead>
              <tbody>
                {items.slice(0, 12).map((i) => (
                  <tr key={i.thread_id} className="clickable" onClick={() => navigate(`/investigations/${i.thread_id}`)}>
                    <td style={{ maxWidth: 420 }}>
                      <div style={{ fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{i.description}</div>
                      <div className="tiny faint mono" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{i.source}</div>
                    </td>
                    <td><span className={`badge ${i.mode === "improved" ? "badge-violet" : "badge-neutral"}`}>{MODE_LABEL[i.mode]}</span></td>
                    <td><StatusBadge status={i.status} /></td>
                    <td className="faint small" style={{ textAlign: "right", whiteSpace: "nowrap" }}>{timeAgo(i.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="card">
          <div className="card-head"><div><h2>How an investigation works</h2><div className="sub">Every claim must cite real evidence</div></div></div>
          <div className="card-body stack" style={{ gap: 14 }}>
            {[
              { icon: <GitBranch size={15} />, t: "Hypotheses", d: "Competing explanations, each tied to a file and function." },
              { icon: <FlaskConical size={15} />, t: "Evidence & reproduction", d: "Reads code, runs the tests in a Docker sandbox with no network." },
              { icon: <UserCheck size={15} />, t: "Human approval", d: "You see the exact diff and decide. Nothing changes before that." },
              { icon: <CheckCircle2 size={15} />, t: "Verified report", d: "Verified facts are separated from unverified guesses." },
            ].map((s, n) => (
              <div key={s.t} className="row" style={{ alignItems: "flex-start", gap: 12 }}>
                <span className="kpi-icon" style={{ flex: "none" }}>{s.icon}</span>
                <div>
                  <div style={{ fontWeight: 600 }}><span className="faint mono tiny" style={{ marginRight: 6 }}>0{n + 1}</span>{s.t}</div>
                  <div className="small muted">{s.d}</div>
                </div>
              </div>
            ))}
            <div className="divider" style={{ margin: "4px 0" }} />
            <Link to="/evaluation" className="row small" style={{ color: "#b8c6ff", fontWeight: 600 }}>
              See how it was measured on 25 bugs <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
