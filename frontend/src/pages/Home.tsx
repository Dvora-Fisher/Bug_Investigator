import { Activity, ArrowRight, BarChart3, Ban, Bug, CheckCircle2, CircleDashed, Coins, Languages, LayoutDashboard, Loader2, PauseCircle, Sparkles, TriangleAlert, XCircle } from "lucide-react";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, Health, InvestigationSummary } from "../api";
import { useWidth } from "../components/Charts";
import HeroArt from "../components/HeroArt";
import { Kpi, LangBadge, OUTCOME, StatusBadge, timeAgo, Tip, Tooltip, usd } from "../components/ui";

type Slice = { key: string; label: string; color: string; icon: ReactNode; n: number };

export default function Home({ health }: { health: Health | null }) {
  const [items, setItems] = useState<InvestigationSummary[] | null>(null);
  const navigate = useNavigate();
  useEffect(() => {
    const load = () => api.list().then(setItems).catch(() => setItems([]));
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const all = items ?? [];
  const slices = useMemo<Slice[]>(() => {
    const count = (f: (i: InvestigationSummary) => boolean) => all.filter(f).length;
    return [
      { key: "verified", label: "Fixed & verified", color: "var(--good)", icon: <CheckCircle2 size={14} />, n: count((i) => i.outcome === "fixed_and_verified") },
      { key: "unverified", label: "Fixed, not verified", color: "var(--warn)", icon: <TriangleAlert size={14} />, n: count((i) => i.outcome === "fixed_unverified") },
      { key: "failed", label: "Fix failed", color: "var(--bad)", icon: <XCircle size={14} />, n: count((i) => i.outcome === "fix_failed") },
      { key: "active", label: "In progress", color: "var(--info)", icon: <Loader2 size={14} />, n: count((i) => i.status === "running" || i.status === "waiting_for_human") },
      { key: "other", label: "No fix / cancelled", color: "#6f7a92", icon: <Ban size={14} />,
        n: count((i) => i.outcome === "no_fix" || i.outcome === "stopped" || i.status === "cancelled" || i.status === "failed" || (i.status === "stopped" && !i.outcome)) },
    ];
  }, [all]);
  const verified = slices[0].n;
  const languages = useMemo(() => {
    const m = new Map<string, number>();
    all.forEach((i) => i.language && m.set(i.language, (m.get(i.language) ?? 0) + 1));
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [all]);
  const waiting = all.filter((i) => i.status === "waiting_for_human");

  return (
    <div className="page fade-in">
      <section className="hero">
        <div>
          <span className="badge badge-violet" style={{ marginBottom: 18 }}><Sparkles size={13} />AI debugging, with proof</span>
          <h1>Squash bugs <br /><span className="grad-text">with evidence.</span></h1>
          <p className="lead">Upload your project, describe the bug, approve the fix.</p>
          <div className="hero-actions">
            <Link to="/new" className="btn btn-primary btn-lg"><Bug size={17} />Start an investigation</Link>
            <Link to="/overview" className="btn btn-lg"><LayoutDashboard size={16} />Overview</Link>
            <Link to="/evaluation" className="btn btn-lg btn-ghost"><BarChart3 size={16} />Evaluation</Link>
          </div>
        </div>
        <HeroArt />
      </section>

      {waiting.length > 0 && (
        <div className="callout callout-warn fade-in" style={{ marginBottom: 18, alignItems: "center" }}>
          <PauseCircle size={18} />
          <div style={{ flex: 1 }}><b>{waiting.length} fix{waiting.length > 1 ? "es" : ""} waiting for your approval</b></div>
          <button className="btn btn-sm" onClick={() => navigate(`/investigations/${waiting[0].thread_id}`)}>Review <ArrowRight size={14} /></button>
        </div>
      )}

      <div className="grid cols-4" style={{ marginBottom: 18 }}>
        <Kpi label="Investigations" icon={<Activity size={15} />} value={items ? all.length : "–"} />
        <Kpi label="Fixed & verified" icon={<CheckCircle2 size={15} />} value={items ? verified : "–"}
          foot={all.length ? `${Math.round((verified / all.length) * 100)}% of all` : undefined} />
        <Kpi label="Languages" icon={<Languages size={15} />} value={items ? languages.length : "–"} />
        <Kpi label="Spent this month" icon={<Coins size={15} />} value={health ? usd(health.month_spend_usd, 2) : "–"}
          foot={health ? `of ${usd(health.monthly_budget_usd, 0)}` : undefined} />
      </div>

      <div className="home-charts" style={{ marginBottom: 18 }}>
        <section className="card">
          <div className="card-head"><h2>Outcomes</h2></div>
          <div className="card-body row" style={{ gap: 20, alignItems: "center" }}>
            <Donut slices={slices} />
            <div className="donut-legend" style={{ flex: 1 }}>
              {slices.map((s) => (
                <div key={s.key} className="row-between">
                  <span className="row" style={{ gap: 8, color: "var(--text-2)" }}><span style={{ color: s.color, display: "inline-flex" }}>{s.icon}</span>{s.label}</span>
                  <b className="num">{s.n}</b>
                </div>
              ))}
            </div>
          </div>
        </section>
        <section className="card">
          <div className="card-head"><h2>Activity · last 14 days</h2></div>
          <div className="card-body"><DailyBars items={all} /></div>
        </section>
        <section className="card">
          <div className="card-head"><h2>Languages</h2></div>
          <div className="card-body stack" style={{ gap: 12 }}>
            {languages.length === 0 ? <div className="empty small" style={{ padding: 30 }}><CircleDashed size={26} /><div>No data yet</div></div>
              : languages.map(([lang, n]) => (
                <div key={lang} className="stack" style={{ gap: 6 }}>
                  <div className="row-between small"><LangBadge lang={lang} /><b className="num">{n}</b></div>
                  <div className="bar"><span style={{ width: `${(n / languages[0][1]) * 100}%` }} /></div>
                </div>
              ))}
          </div>
        </section>
      </div>

      <section>
        <div className="row-between" style={{ marginBottom: 12 }}>
          <h2 style={{ fontSize: 18 }}>Recent</h2>
          <Link to="/overview" className="row small" style={{ color: "#b8c6ff", fontWeight: 600, gap: 6 }}>All investigations <ArrowRight size={14} /></Link>
        </div>
        {items && all.length === 0 ? (
          <div className="card empty">
            <Bug size={34} />
            <div style={{ color: "var(--text-2)", fontWeight: 600, marginBottom: 14 }}>No investigations yet</div>
            <Link to="/new" className="btn btn-primary"><Sparkles size={15} />Start the first one</Link>
          </div>
        ) : (
          <div className="recent-grid">
            {all.slice(0, 6).map((i) => (
              <div key={i.thread_id} className="card recent-card" onClick={() => navigate(`/investigations/${i.thread_id}`)}>
                <div className="row-between">
                  {i.outcome ? <span className={`badge ${OUTCOME[i.outcome].cls}`}>{OUTCOME[i.outcome].icon}{OUTCOME[i.outcome].label}</span> : <StatusBadge status={i.status} />}
                  <span className="tiny faint">{timeAgo(i.created_at)}</span>
                </div>
                <div className="title">{i.description}</div>
                <div className="row-between">
                  {i.language ? <LangBadge lang={i.language} /> : <span />}
                  <span className="mono tiny faint">{usd(i.cost_usd)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Donut({ slices }: { slices: Slice[] }) {
  const [tip, setTip] = useState<Tip | null>(null);
  const total = slices.reduce((s, x) => s + x.n, 0);
  const size = 150, r = 58, w = 16, c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ flex: "none" }} onMouseLeave={() => setTip(null)}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(148,163,196,0.1)" strokeWidth={w} />
        {total > 0 && slices.filter((s) => s.n > 0).map((s) => {
          const len = (s.n / total) * c;
          const gap = slices.filter((x) => x.n > 0).length > 1 ? 3 : 0;
          const el = (
            <circle key={s.key} cx={size / 2} cy={size / 2} r={r} fill="none" stroke={s.color} strokeWidth={w}
              strokeDasharray={`${Math.max(0, len - gap)} ${c}`} strokeDashoffset={-offset} transform={`rotate(-90 ${size / 2} ${size / 2})`}
              onMouseMove={(e) => setTip({ x: e.clientX, y: e.clientY, title: s.label, rows: [["Investigations", String(s.n)], ["Share", `${Math.round((s.n / total) * 100)}%`]] })} />
          );
          offset += len;
          return el;
        })}
        <text x="50%" y="47%" textAnchor="middle" style={{ fill: "var(--text)", fontSize: 28, fontWeight: 700 }}>{total}</text>
        <text x="50%" y="62%" textAnchor="middle" style={{ fill: "var(--text-3)", fontSize: 11 }}>total</text>
      </svg>
      <Tooltip tip={tip} />
    </>
  );
}

function DailyBars({ items }: { items: InvestigationSummary[] }) {
  const [tip, setTip] = useState<Tip | null>(null);
  const days = useMemo(() => {
    const out: { key: string; label: string; n: number }[] = [];
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    for (let d = 13; d >= 0; d--) {
      const day = new Date(today.getTime() - d * 86400000);
      out.push({ key: day.toDateString(), label: day.toLocaleDateString(undefined, { day: "numeric", month: "short" }), n: 0 });
    }
    items.forEach((i) => {
      const k = new Date(i.created_at);
      k.setHours(0, 0, 0, 0);
      const slot = out.find((o) => o.key === k.toDateString());
      if (slot) slot.n++;
    });
    return out;
  }, [items]);
  const max = Math.max(1, ...days.map((d) => d.n));
  const [box, W] = useWidth<HTMLDivElement>(420);
  const H = 170, padB = 22, bw = Math.min(22, (W / days.length) * 0.56);
  return (
    <div ref={box}>
      <svg className="chart" width={W} height={H} viewBox={`0 0 ${W} ${H}`} onMouseLeave={() => setTip(null)}>
        <defs>
          <linearGradient id="dayGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#6d8bff" /><stop offset="1" stopColor="#22d3ee" /></linearGradient>
        </defs>
        <line x1="0" x2={W} y1={H - padB} y2={H - padB} stroke="rgba(148,163,196,0.14)" />
        {days.map((d, i) => {
          const slot = W / days.length;
          const x = i * slot + (slot - bw) / 2;
          const h = d.n ? ((H - padB - 14) * d.n) / max : 0;
          return (
            <g key={d.key}>
              {h > 0 ? <rect x={x} y={H - padB - h} width={bw} height={h} rx={4} fill="url(#dayGrad)" />
                : <rect x={x} y={H - padB - 3} width={bw} height={3} rx={1.5} fill="rgba(148,163,196,0.12)" />}
              {(i % 3 === 1 || i === days.length - 1) && <text x={x + bw / 2} y={H - 6} textAnchor="middle">{i === days.length - 1 ? "today" : d.label}</text>}
              <rect x={i * slot} y={0} width={slot} height={H - padB} fill="transparent"
                onMouseMove={(e) => setTip({ x: e.clientX, y: e.clientY, title: d.label, rows: [["Investigations", String(d.n)]] })} />
            </g>
          );
        })}
      </svg>
      <Tooltip tip={tip} />
    </div>
  );
}
