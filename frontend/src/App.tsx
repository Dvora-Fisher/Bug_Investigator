import { BarChart3, Box, Cpu, Home as HomeIcon, LayoutDashboard, Lock, PlusCircle, Search, Wallet } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { api, ApiError, Health, setPassword } from "./api";
import Evaluation from "./pages/Evaluation";
import Home from "./pages/Home";
import Investigation from "./pages/Investigation";
import NewInvestigation from "./pages/NewInvestigation";
import Overview from "./pages/Overview";
import { usd } from "./components/ui";

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);
  const [locked, setLocked] = useState(false);
  const load = useCallback(() => api.health()
    .then((h) => { setHealth(h); setOffline(false); setLocked(false); })
    .catch((e) => { if (e instanceof ApiError && e.status === 401) setLocked(true); else setOffline(true); }), []);
  useEffect(() => {
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, [load]);

  if (locked) return <PasswordGate onSubmit={(value) => { setPassword(value); load(); }} />;

  return (
    <div className="shell">
      <div className="backdrop" />
      <aside className="sidebar">
        <NavLink to="/" className="brand">
          <div className="brand-mark"><Search size={18} color="#050811" strokeWidth={2.6} /></div>
          <div>
            <div className="brand-name">Bug Investigator</div>
            <div className="brand-sub">Universal · AI</div>
          </div>
        </NavLink>
        <div className="nav-label">Workspace</div>
        <NavLink to="/" end className="nav-link"><HomeIcon size={17} />Home</NavLink>
        <NavLink to="/overview" className="nav-link"><LayoutDashboard size={17} />Overview</NavLink>
        <NavLink to="/new" className="nav-link"><PlusCircle size={17} />New investigation</NavLink>
        <div className="nav-label">Quality</div>
        <NavLink to="/evaluation" className="nav-link"><BarChart3 size={17} />Evaluation</NavLink>

        <div className="sidebar-foot">
          {offline ? (
            <div className="callout callout-bad small" style={{ padding: "10px 12px" }}>{import.meta.env.VITE_API_BASE ? "Server is asleep — start the Codespace" : "API offline — start the backend on :8000"}</div>
          ) : (
            <>
              <div className="sys-row"><span className="row" style={{ gap: 7 }}><Cpu size={14} />Model</span><span className="mono tiny">{health?.model ?? "…"}</span></div>
              <div className="sys-row">
                <span className="row" style={{ gap: 7 }}><Box size={14} />Sandbox</span>
                {health && <span className={`badge ${health.docker ? "badge-good" : "badge-warn"}`}><span className="dot" />{health.docker ? "Docker ready" : "No Docker"}</span>}
              </div>
              <div className="sys-row"><span className="row" style={{ gap: 7 }}><Wallet size={14} />This month</span>
                <span className="mono tiny">{health ? `${usd(health.month_spend_usd, 2)} / ${usd(health.monthly_budget_usd, 0)}` : "…"}</span></div>
              {health && (
                <div className="bar" title="Monthly API spend vs. budget">
                  <span style={{ width: `${Math.min(100, (health.month_spend_usd / health.monthly_budget_usd) * 100)}%` }} />
                </div>
              )}
            </>
          )}
        </div>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/" element={<Home health={health} />} />
          <Route path="/overview" element={<Overview health={health} />} />
          <Route path="/new" element={<NewInvestigation health={health} />} />
          <Route path="/investigations/:id" element={<Investigation />} />
          <Route path="/evaluation" element={<Evaluation />} />
          <Route path="*" element={<div className="page"><h1>Not found</h1></div>} />
        </Routes>
      </main>
    </div>
  );
}

/** Shown when the backend requires a password (APP_PASSWORD) and this browser has none or a wrong one. */
function PasswordGate({ onSubmit }: { onSubmit: (value: string) => void }) {
  const [value, setValue] = useState("");
  const [tried, setTried] = useState(false);
  const submit = (e: FormEvent) => { e.preventDefault(); setTried(true); onSubmit(value); };
  return (
    <div className="shell" style={{ display: "grid", placeItems: "center", minHeight: "100vh", padding: 16 }}>
      <div className="backdrop" />
      <form className="card card-pad" onSubmit={submit} style={{ width: "min(380px, 100%)", display: "grid", gap: 16, position: "relative" }}>
        <div className="row" style={{ gap: 10 }}><Lock size={18} /><strong>Bug Investigator</strong></div>
        <label className="field"><span className="field-label">Access password</span>
          <input className="input" type="password" autoFocus value={value} onChange={(e) => setValue(e.target.value)} /></label>
        {tried && <div className="callout callout-bad small">Wrong password, try again.</div>}
        <button className="btn btn-primary" type="submit" disabled={!value}>Enter</button>
      </form>
    </div>
  );
}
