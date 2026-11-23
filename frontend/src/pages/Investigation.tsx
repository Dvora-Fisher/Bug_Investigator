import {
  Activity, AlertTriangle, ArrowLeft, Ban, Box, OctagonX, Check, CheckCircle2, CircleDot, Clock, Coins, FileSearch, FileText, FlaskConical,
  FolderTree, GitPullRequest, HelpCircle, Lightbulb, MessageSquare, PauseCircle, RotateCcw, Send, ShieldCheck, TestTubes,
  ThumbsDown, ThumbsUp, XCircle,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, Evidence, InvestigationView, PauseRequest, RunEvent, streamEvents } from "../api";
import PipelineGraph from "../components/PipelineGraph";
import { DiffView, FileViewer, LangBadge, Modal, MODE_LABEL, NODE_LABELS, OUTCOME, OutcomeBadge, StatusBadge, usd } from "../components/ui";

type TabKey = "hypotheses" | "evidence" | "tests" | "diff" | "project";

export default function Investigation() {
  const { id = "" } = useParams();
  const [view, setView] = useState<InvestigationView | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<TabKey>("hypotheses");
  const [focusEvidence, setFocusEvidence] = useState<string | null>(null);
  const [openFile, setOpenFile] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [stopping, setStopping] = useState(false);
  const lastSeq = useRef(0);
  const closeStream = useRef<() => void>(() => {});
  const refreshTimer = useRef<number>();

  const refresh = useCallback(() => {
    api.get(id).then(setView).catch((e) => setError(e.message));
  }, [id]);
  const scheduleRefresh = useCallback(() => {
    window.clearTimeout(refreshTimer.current);
    refreshTimer.current = window.setTimeout(refresh, 250);
  }, [refresh]);

  const connect = useCallback(() => {
    closeStream.current();
    closeStream.current = streamEvents(id, lastSeq.current, (e) => {
      if (e.seq <= lastSeq.current) return;
      lastSeq.current = e.seq;
      setEvents((prev) => [...prev, e]);
      scheduleRefresh();
    }, () => {
      refresh();
      // The stream ends after each segment. If the run is still going (race), reconnect.
      window.setTimeout(() => api.get(id).then((v) => { setView(v); if (v.status === "running") connect(); }).catch(() => {}), 800);
    });
  }, [id, refresh, scheduleRefresh]);

  useEffect(() => {
    lastSeq.current = 0;
    setEvents([]);
    setView(null);
    refresh();
    connect();
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => { closeStream.current(); clearInterval(t); };
  }, [id, refresh, connect]);

  useEffect(() => { if (view && view.status !== "running") setStopping(false); }, [view?.status]);

  const showEvidence = (eid: string) => { setTab("evidence"); setFocusEvidence(eid); };

  const nodes = useMemo(() => events.filter((e) => e.kind === "node" && e.node).map((e) => e.node as string), [events]);
  const visits = useMemo(() => nodes.reduce<Record<string, number>>((acc, n) => ({ ...acc, [n]: (acc[n] ?? 0) + 1 }), {}), [nodes]);
  const transitions = useMemo(() => {
    const s = new Set<string>();
    for (let i = 1; i < nodes.length; i++) s.add(`${nodes[i - 1]}>${nodes[i]}`);
    if (view?.pending && nodes.length) s.add(`${nodes[nodes.length - 1]}>human_review`);
    return s;
  }, [nodes, view?.pending]);

  if (error && !view) return <div className="page"><div className="callout callout-bad">{error}</div></div>;
  if (!view) return <div className="page"><div className="skeleton" style={{ height: 120, marginBottom: 18 }} /><div className="skeleton" style={{ height: 300 }} /></div>;

  const running = view.status === "running";
  const sandbox = activeSandbox(events);
  const started = new Date(view.meta.created_at).getTime();
  const lastAt = events.length ? new Date(events[events.length - 1].at).getTime() : started;
  const elapsed = Math.max(0, Math.round(((running ? now : lastAt) - started) / 1000));
  const evidenceById = Object.fromEntries(view.evidence.map((e) => [e.id, e]));
  const Ev = ({ ids }: { ids: string[] }) => (
    <span className="row" style={{ gap: 4, flexWrap: "wrap", display: "inline-flex" }}>
      {ids.map((eid) => <button key={eid} type="button" className="chip" title={evidenceById[eid] ? `${evidenceById[eid].tool}` : "evidence"} onClick={() => showEvidence(eid)}>{eid}</button>)}
    </span>
  );
  const Path = ({ p }: { p: string }) => <span className="path" onClick={() => setOpenFile(p)}>{p}</span>;

  return (
    <div className="page fade-in">
      <Link to="/overview" className="row small faint" style={{ marginBottom: 14, gap: 6 }}><ArrowLeft size={14} />All investigations</Link>
      <div className="page-head" style={{ alignItems: "flex-start" }}>
        <div style={{ maxWidth: 820 }}>
          <div className="eyebrow">Investigation · <span className="mono">{id.slice(0, 8)}</span></div>
          <h1 style={{ fontSize: 24 }}>{view.bug_summary || view.meta.description}</h1>
          <div className="row" style={{ marginTop: 12, flexWrap: "wrap", gap: 8 }}>
            <StatusBadge status={view.status} />
            <span className={`badge ${view.meta.mode === "improved" ? "badge-violet" : "badge-neutral"}`}>{MODE_LABEL[view.meta.mode]} mode</span>
            {view.language && <LangBadge lang={view.language} />}
            <span className="badge badge-neutral mono" title={view.meta.source}>{shorten(view.meta.source, 48)}</span>
          </div>
        </div>
        <div className="stack" style={{ gap: 10, justifyItems: "end" }}>
          <div className="grid" style={{ gridTemplateColumns: "repeat(3, auto)", gap: 10 }}>
            <Stat icon={<Clock size={14} />} label="Elapsed" value={`${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`} />
            <Stat icon={<Coins size={14} />} label="Cost" value={usd(view.cost_usd)} />
            <Stat icon={<FileSearch size={14} />} label="Evidence" value={String(view.evidence.length)} />
          </div>
          {(running || view.status === "waiting_for_human") && (
            <button className="btn btn-bad btn-sm" disabled={stopping} onClick={() => setConfirmCancel(true)}>
              {stopping ? <span className="spinner" style={{ width: 13, height: 13 }} /> : <OctagonX size={14} />}{stopping ? "Stopping…" : "Cancel investigation"}
            </button>
          )}
        </div>
      </div>

      <section className="card" style={{ marginBottom: 18 }}>
        <div className="card-head">
          <div><h2>Investigation graph</h2><div className="sub">LangGraph state machine · live from the event stream</div></div>
          <div className="row small faint" style={{ gap: 14 }}>
            <span>Round {Math.max(1, view.hypothesis_rounds)}</span><span>Fix attempt {view.fix_attempts}</span>
            {running && <span className="row" style={{ color: "#67e8f9", gap: 6 }}><span className="spinner" style={{ width: 12, height: 12 }} />working</span>}
          </div>
        </div>
        <div className="card-body" style={{ padding: "8px 18px 4px" }}>
          <PipelineGraph visits={visits} transitions={transitions} current={nodes[nodes.length - 1] ?? null}
            waiting={!!view.pending} running={running} mode={view.meta.mode} />
        </div>
        {running && sandbox && (
          <div className="sandbox-strip fade-in">
            <span className="spinner" />
            <div style={{ flex: 1, minWidth: 0 }}>
              <b>{sandboxLabel(sandbox.data)}</b>
              <span className="mono tiny faint" style={{ marginLeft: 10 }}>{sandbox.data.command}</span>
              {sandbox.data.network && <div className="tiny muted">The first run of a large project can take several minutes. You can cancel at any time.</div>}
            </div>
            <span className="mono" style={{ fontSize: 15, fontWeight: 600 }}>{clock((now - new Date(sandbox.at).getTime()) / 1000)}</span>
          </div>
        )}
      </section>

      {view.status === "cancelled" && (
        <div className="callout callout-info" style={{ marginBottom: 18 }}><Ban size={17} /><div><b>Cancelled.</b> The investigation was stopped and no changes were made to your code.</div></div>
      )}
      {view.pending && <ReviewPanel id={id} pending={view.pending} Ev={Ev} onSent={() => { refresh(); connect(); }} />}
      {view.halt_reason && !view.report && (
        <div className="callout callout-bad" style={{ marginBottom: 18 }}><AlertTriangle size={17} /><div><b>Stopped:</b> {view.halt_reason}</div></div>
      )}
      {view.report && <ReportCard view={view} Ev={Ev} Path={Path} />}

      <div className="split">
        <section className="card">
          <div className="tabs">
            <Tab on={tab === "hypotheses"} onClick={() => setTab("hypotheses")} icon={<Lightbulb size={14} />} label="Hypotheses" n={view.hypotheses.length} />
            <Tab on={tab === "evidence"} onClick={() => setTab("evidence")} icon={<FileSearch size={14} />} label="Evidence" n={view.evidence.length} />
            <Tab on={tab === "tests"} onClick={() => setTab("tests")} icon={<TestTubes size={14} />} label="Tests" n={view.test_runs.length} />
            <Tab on={tab === "diff"} onClick={() => setTab("diff")} icon={<GitPullRequest size={14} />} label="Fix" n={view.proposed_fix ? view.proposed_fix.edits.length : 0} />
            <Tab on={tab === "project"} onClick={() => setTab("project")} icon={<FolderTree size={14} />} label="Project" />
          </div>
          <div className="card-body">
            {tab === "hypotheses" && <Hypotheses view={view} Ev={Ev} Path={Path} />}
            {tab === "evidence" && <EvidenceList items={view.evidence} focus={focusEvidence} />}
            {tab === "tests" && <Tests view={view} Ev={Ev} />}
            {tab === "diff" && (view.proposed_fix ? (
              <div className="stack" style={{ gap: 14 }}>
                <div><div className="faint tiny" style={{ marginBottom: 4 }}>ROOT CAUSE</div><div>{view.proposed_fix.root_cause}</div></div>
                <div><div className="faint tiny" style={{ marginBottom: 4 }}>WHY THIS FIXES IT</div><div className="muted">{view.proposed_fix.explanation}</div></div>
                <DiffView diff={view.proposed_fix.diff} />
              </div>
            ) : <Empty icon={<GitPullRequest size={30} />} text="No fix proposed yet." />)}
            {tab === "project" && <Project view={view} />}
          </div>
        </section>

        <aside className="stack">
          <section className="card">
            <div className="card-head"><div><h2>Live activity</h2><div className="sub">{events.length} events</div></div><Activity size={16} color="var(--text-3)" /></div>
            <div className="card-body" style={{ maxHeight: 440, overflowY: "auto" }}>
              {events.length === 0 ? <Empty icon={<span className="spinner" />} text="Waiting for the first step…" /> : (
                <div className="timeline">
                  {[...events].reverse().map((e) => <TimelineItem key={e.seq} e={e} />)}
                </div>
              )}
            </div>
          </section>
          <section className="card">
            <div className="card-head"><div><h2>Bug report</h2><div className="sub">As submitted</div></div><FileText size={16} color="var(--text-3)" /></div>
            <div className="card-body stack" style={{ gap: 10 }}>
              <div className="small" style={{ whiteSpace: "pre-wrap" }}>{view.bug?.description ?? view.meta.description}</div>
              {view.bug?.error_output && <pre className="code wrap" style={{ maxHeight: 220 }}>{view.bug.error_output}</pre>}
            </div>
          </section>
        </aside>
      </div>
      {openFile && <FileViewer threadId={id} path={openFile} onClose={() => setOpenFile(null)} />}
      {confirmCancel && (
        <Modal title={<><OctagonX size={16} color="var(--bad)" /><b>Cancel this investigation?</b></>} onClose={() => setConfirmCancel(false)}>
          <div className="card-body stack" style={{ gap: 16 }}>
            <div className="muted">The agent stops right away and nothing is changed in your code. A cancelled investigation cannot be resumed.</div>
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button className="btn" onClick={() => setConfirmCancel(false)}>Keep going</button>
              <button className="btn btn-bad" onClick={async () => {
                setConfirmCancel(false);
                setStopping(true);
                try { await api.cancel(id); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
                refresh();
                connect();
              }}><Ban size={15} />Cancel investigation</button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ pieces

type EvProps = { Ev: (p: { ids: string[] }) => JSX.Element };
type PathProps = { Path: (p: { p: string }) => JSX.Element };

function Stat({ icon, label, value }: { icon: JSX.Element; label: string; value: string }) {
  return (
    <div className="card" style={{ padding: "10px 14px", minWidth: 104 }}>
      <div className="tiny faint row" style={{ gap: 6 }}>{icon}{label}</div>
      <div className="mono" style={{ fontSize: 17, fontWeight: 600, marginTop: 2 }}>{value}</div>
    </div>
  );
}

function Tab({ on, onClick, icon, label, n }: { on: boolean; onClick: () => void; icon: JSX.Element; label: string; n?: number }) {
  return <button type="button" className={`tab${on ? " on" : ""}`} onClick={onClick}>{icon}{label}{n !== undefined && <span className="count">{n}</span>}</button>;
}

function Empty({ icon, text }: { icon: JSX.Element; text: string }) {
  return <div className="empty"><div style={{ display: "grid", placeItems: "center", marginBottom: 8 }}>{icon}</div>{text}</div>;
}

function ReviewPanel({ id, pending, Ev, onSent }: { id: string; pending: PauseRequest; onSent: () => void } & EvProps) {
  const [rejecting, setRejecting] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [nextStep, setNextStep] = useState<"revise_fix" | "reinvestigate">("revise_fix");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const send = async (answer: object) => {
    setBusy(true);
    setErr("");
    try { await api.resume(id, answer); onSent(); } catch (e) { setErr(e instanceof Error ? e.message : String(e)); setBusy(false); }
  };

  if (pending.type === "clarification") {
    return (
      <section className="card fade-in" style={{ marginBottom: 18, borderColor: "rgba(250,178,25,0.45)" }}>
        <div className="card-head"><div className="row"><HelpCircle size={18} color="var(--warn)" /><div><h2>The agent has a question</h2><div className="sub">Your answer guides the next attempt</div></div></div></div>
        <div className="card-body stack" style={{ gap: 12 }}>
          <div style={{ fontSize: 15 }}>{pending.question}</div>
          <textarea className="textarea" placeholder="e.g. The fix changes the public API; keep the old signature." value={feedback} onChange={(e) => setFeedback(e.target.value)} />
          <NextStep value={nextStep} onChange={setNextStep} />
          {err && <div className="callout callout-bad small">{err}</div>}
          <div><button className="btn btn-primary" disabled={!feedback.trim() || busy} onClick={() => send({ answer: feedback.trim(), next_step: nextStep })}>
            {busy ? <span className="spinner" /> : <Send size={15} />}Send answer</button></div>
        </div>
      </section>
    );
  }

  return (
    <section className="card fade-in" style={{ marginBottom: 18, borderColor: "rgba(250,178,25,0.45)", boxShadow: "0 0 0 4px rgba(250,178,25,0.06), var(--shadow)" }}>
      <div className="card-head">
        <div className="row"><PauseCircle size={19} color="var(--warn)" />
          <div><h2>Your approval is needed</h2><div className="sub">Fix attempt {pending.attempt} of {pending.max_attempts} · nothing has been changed yet</div></div>
        </div>
        <span className={`badge ${pending.verified_by_tests ? "badge-good" : "badge-warn"}`}>
          {pending.verified_by_tests ? <><ShieldCheck size={13} />Will be verified by tests</> : <><AlertTriangle size={13} />Cannot be verified by tests</>}
        </span>
      </div>
      <div className="card-body">
        <div className="grid" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.4fr)", gap: 20 }}>
          <div className="stack" style={{ gap: 14, alignContent: "start" }}>
            <div><div className="faint tiny" style={{ marginBottom: 4 }}>ROOT CAUSE</div><div style={{ fontWeight: 500 }}>{pending.root_cause}</div></div>
            <div><div className="faint tiny" style={{ marginBottom: 4 }}>WHY THIS FIXES IT</div><div className="muted small">{pending.explanation}</div></div>
            <div><div className="faint tiny" style={{ marginBottom: 6 }}>BASED ON EVIDENCE</div><Ev ids={pending.evidence_ids} /></div>
          </div>
          <DiffView diff={pending.diff} />
        </div>
        <div className="divider" />
        {rejecting ? (
          <div className="stack fade-in" style={{ gap: 12 }}>
            <textarea className="textarea" autoFocus placeholder="What is wrong with this fix? (leave empty and the agent will ask you)" value={feedback} onChange={(e) => setFeedback(e.target.value)} />
            <NextStep value={nextStep} onChange={setNextStep} />
            {err && <div className="callout callout-bad small">{err}</div>}
            <div className="row">
              <button className="btn btn-bad" disabled={busy} onClick={() => send({ decision: "reject", feedback: feedback.trim(), next_step: nextStep })}>
                {busy ? <span className="spinner" /> : <ThumbsDown size={15} />}Send rejection</button>
              <button className="btn btn-ghost" onClick={() => setRejecting(false)}>Cancel</button>
            </div>
          </div>
        ) : (
          <div className="row">
            <button className="btn btn-good btn-lg" disabled={busy} onClick={() => send({ decision: "approve" })}>
              {busy ? <span className="spinner" /> : <ThumbsUp size={16} />}Approve & apply fix</button>
            <button className="btn btn-lg" disabled={busy} onClick={() => setRejecting(true)}><ThumbsDown size={16} />Reject</button>
            {err && <div className="callout callout-bad small">{err}</div>}
          </div>
        )}
      </div>
    </section>
  );
}

function NextStep({ value, onChange }: { value: "revise_fix" | "reinvestigate"; onChange: (v: "revise_fix" | "reinvestigate") => void }) {
  return (
    <div className="row" style={{ flexWrap: "wrap" }}>
      <span className="small muted">Then:</span>
      <div className="segmented">
        <button type="button" className={value === "revise_fix" ? "on" : ""} onClick={() => onChange("revise_fix")}><RotateCcw size={13} />Revise the fix</button>
        <button type="button" className={value === "reinvestigate" ? "on" : ""} onClick={() => onChange("reinvestigate")}><Lightbulb size={13} />Investigate other causes</button>
      </div>
    </div>
  );
}

function ReportCard({ view, Ev, Path }: { view: InvestigationView } & EvProps & PathProps) {
  const r = view.report!;
  const o = OUTCOME[r.outcome];
  const toneColor = { good: "var(--good)", warn: "var(--warn)", bad: "var(--bad)", neutral: "var(--text-3)" }[o.tone];
  return (
    <section className="card fade-in" style={{ marginBottom: 18, overflow: "hidden" }}>
      <div style={{ padding: "22px 24px", background: `linear-gradient(90deg, ${toneColor}1f, transparent 70%)`, borderBottom: "1px solid var(--line)" }}>
        <div className="row-between" style={{ flexWrap: "wrap" }}>
          <div className="row" style={{ gap: 14 }}>
            <div style={{ width: 46, height: 46, borderRadius: 13, display: "grid", placeItems: "center", background: `${toneColor}22`, color: toneColor, border: `1px solid ${toneColor}55` }}>
              {o.tone === "good" ? <CheckCircle2 size={24} /> : o.tone === "bad" ? <XCircle size={24} /> : <AlertTriangle size={24} />}
            </div>
            <div><div className="eyebrow" style={{ marginBottom: 2 }}>Final report</div><div style={{ fontSize: 20, fontWeight: 700 }}>{o.label}</div><div className="small muted">{o.help}</div></div>
          </div>
          <OutcomeBadge outcome={r.outcome} />
        </div>
      </div>
      <div className="card-body">
        <div className="grid cols-2" style={{ gap: 22 }}>
          <div className="stack" style={{ gap: 16, alignContent: "start" }}>
            <div><div className="faint tiny" style={{ marginBottom: 4 }}>ROOT CAUSE</div><div style={{ fontSize: 14.5 }}>{r.root_cause}</div></div>
            {r.files.length > 0 && <div><div className="faint tiny" style={{ marginBottom: 6 }}>FILES</div><div className="stack" style={{ gap: 4 }}>{r.files.map((f) => <Path key={f} p={f} />)}</div></div>}
            <div><div className="faint tiny" style={{ marginBottom: 4 }}>REPRODUCTION</div><div className="small muted">{r.reproduction}</div></div>
            {r.notes.length > 0 && (
              <div className="stack" style={{ gap: 8 }}>
                {r.notes.map((n, i) => <div key={i} className="callout callout-info small"><MessageSquare size={15} /><div>{n}</div></div>)}
              </div>
            )}
          </div>
          <div className="stack" style={{ gap: 16, alignContent: "start" }}>
            <div>
              <div className="faint tiny row" style={{ marginBottom: 8, gap: 6 }}><ShieldCheck size={13} color="var(--good)" />VERIFIED FACTS · backed by tool output</div>
              <div className="stack" style={{ gap: 8 }}>
                {r.verified_facts.length === 0 && <div className="small faint">None.</div>}
                {r.verified_facts.map((f, i) => (
                  <div key={i} className="row small" style={{ alignItems: "flex-start", gap: 9 }}>
                    <Check size={15} color="var(--good)" style={{ flex: "none", marginTop: 2 }} />
                    <div style={{ flex: 1 }}>{f.text} <Ev ids={f.evidence_ids} /></div>
                  </div>
                ))}
              </div>
            </div>
            {r.unverified_hypotheses.length > 0 && (
              <div>
                <div className="faint tiny row" style={{ marginBottom: 8, gap: 6 }}><HelpCircle size={13} color="var(--warn)" />UNVERIFIED · not proven by evidence</div>
                <div className="stack" style={{ gap: 6 }}>
                  {r.unverified_hypotheses.map((h, i) => <div key={i} className="small muted row" style={{ alignItems: "flex-start", gap: 9 }}><CircleDot size={14} color="var(--warn)" style={{ flex: "none", marginTop: 3 }} />{h}</div>)}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function Hypotheses({ view, Ev, Path }: { view: InvestigationView } & EvProps & PathProps) {
  if (!view.hypotheses.length) return <Empty icon={<Lightbulb size={30} />} text="Hypotheses appear here once the agent has read the report and the project." />;
  const sorted = [...view.hypotheses].sort((a, b) => b.confidence - a.confidence);
  return (
    <div className="stack" style={{ gap: 12 }}>
      {sorted.map((h) => {
        const findings = view.findings.filter((f) => f.hypothesis_id === h.id);
        const cls = h.status === "supported" ? "badge-good" : h.status === "refuted" ? "badge-bad" : "badge-neutral";
        return (
          <div key={h.id} className="card" style={{ padding: 16, opacity: h.status === "refuted" ? 0.62 : 1, background: "rgba(5,8,16,0.4)" }}>
            <div className="row-between">
              <div className="row"><span className="mono" style={{ fontWeight: 700, color: "#b8c6ff" }}>{h.id}</span>
                <span className={`badge ${cls}`}>{h.status === "supported" ? <CheckCircle2 size={12} /> : h.status === "refuted" ? <XCircle size={12} /> : <CircleDot size={12} />}{h.status}</span></div>
              <div className="row small faint" style={{ gap: 8, minWidth: 160 }}>
                <span>confidence</span>
                <div className="bar" style={{ flex: 1, width: 80 }}><span style={{ width: `${h.confidence * 100}%` }} /></div>
                <span className="mono">{Math.round(h.confidence * 100)}%</span>
              </div>
            </div>
            <div style={{ margin: "10px 0 8px" }}>{h.statement}</div>
            <div className="row small"><FolderTree size={13} color="var(--text-3)" /><Path p={h.location.file} />{h.location.symbol && <span className="mono tiny faint">:: {h.location.symbol}</span>}</div>
            {findings.map((f, i) => (
              <div key={i} className="small" style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--line)" }}>
                <span className={`badge ${f.verdict === "supported" ? "badge-good" : f.verdict === "refuted" ? "badge-bad" : "badge-neutral"}`} style={{ marginRight: 8 }}>{f.verdict}</span>
                <span className="muted">{f.note}</span> <Ev ids={f.evidence_ids} />
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

function EvidenceList({ items, focus }: { items: Evidence[]; focus: string | null }) {
  const refs = useRef<Record<string, HTMLDivElement | null>>({});
  useEffect(() => { if (focus) refs.current[focus]?.scrollIntoView({ behavior: "smooth", block: "center" }); }, [focus]);
  if (!items.length) return <Empty icon={<FileSearch size={30} />} text="Every tool call the agent makes is recorded here as evidence it can cite." />;
  return (
    <div className="stack" style={{ gap: 10 }}>
      {items.map((e) => (
        <div key={e.id} ref={(el) => { refs.current[e.id] = el; }} className="card"
          style={{ padding: 0, overflow: "hidden", background: "rgba(5,8,16,0.4)", borderColor: focus === e.id ? "rgba(94,179,255,0.7)" : undefined, boxShadow: focus === e.id ? "0 0 0 3px rgba(94,179,255,0.15)" : undefined }}>
          <div className="row" style={{ padding: "9px 14px", borderBottom: "1px solid var(--line)", gap: 10 }}>
            <span className="chip" style={{ cursor: "default" }}>{e.id}</span>
            <span className="mono small" style={{ fontWeight: 600 }}>{e.tool}</span>
            <span className="mono tiny faint" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{argSummary(e.args)}</span>
          </div>
          <pre className="code" style={{ border: 0, borderRadius: 0, maxHeight: 260, fontSize: 12 }}>{e.excerpt}</pre>
        </div>
      ))}
    </div>
  );
}

function Tests({ view, Ev }: { view: InvestigationView } & EvProps) {
  const repro = view.reproduction;
  return (
    <div className="stack" style={{ gap: 14 }}>
      {repro && (
        <div className={`callout ${repro.reproduced ? "callout-good" : repro.attempted ? "callout-warn" : "callout-info"}`}>
          <FlaskConical size={16} />
          <div><b>{repro.reproduced ? "Bug reproduced" : repro.attempted ? "Could not reproduce" : "Reproduction not attempted"}</b>
            <div className="small" style={{ marginTop: 2 }}>{repro.method} {repro.evidence_ids.length > 0 && <Ev ids={repro.evidence_ids} />}</div>
            {repro.command.length > 0 && <div className="mono tiny" style={{ marginTop: 6 }}>$ {repro.command.join(" ")}</div>}
          </div>
        </div>
      )}
      {view.test_runs.length === 0 ? <Empty icon={<TestTubes size={30} />} text="Test runs in the sandbox appear here (before and after the fix)." /> : view.test_runs.map((t, i) => (
        <div key={i} className="card" style={{ padding: 0, overflow: "hidden", background: "rgba(5,8,16,0.4)" }}>
          <div className="row-between" style={{ padding: "10px 14px", borderBottom: "1px solid var(--line)" }}>
            <div className="row">
              {t.passed ? <CheckCircle2 size={16} color="var(--good)" /> : <XCircle size={16} color="var(--bad)" />}
              <b className="small">{t.phase === "before_fix" ? "Before the fix" : `After fix attempt ${t.attempt}`}</b>
              <span className="badge badge-neutral">{t.kind === "repro" ? "reproduction" : "test suite"}</span>
            </div>
            <span className="mono tiny faint">{t.command} · exit {t.exit_code ?? "—"}</span>
          </div>
          <pre className="code" style={{ border: 0, borderRadius: 0, maxHeight: 220, fontSize: 12 }}>{t.output_excerpt}</pre>
        </div>
      ))}
    </div>
  );
}

function Project({ view }: { view: InvestigationView }) {
  const p = view.profile;
  if (!p) return <Empty icon={<FolderTree size={30} />} text="Project facts appear after the intake step." />;
  const exts = Object.entries(p.extensions).sort((a, b) => b[1] - a[1]).slice(0, 6);
  const max = exts[0]?.[1] ?? 1;
  const capability = ["Analyze only", "Analyze & edit", "Can run tests", "Can verify fixes"][p.capability - 1] ?? `level ${p.capability}`;
  return (
    <div className="grid" style={{ gridTemplateColumns: "minmax(0, 1fr) 220px", gap: 18 }}>
      <pre className="code" style={{ maxHeight: 380 }}>{p.tree}</pre>
      <div className="stack" style={{ gap: 14, alignContent: "start" }}>
        <div className="row-between small"><span className="muted">Files</span><b className="mono">{p.file_count}</b></div>
        <div className="row-between small"><span className="muted">Runtime</span><b className="mono">{p.runtime ?? "none"}</b></div>
        <div className="row-between small"><span className="muted">Sandbox</span><span className="badge badge-info">{capability}</span></div>
        <div className="divider" style={{ margin: 0 }} />
        {exts.map(([ext, n]) => (
          <div key={ext} className="stack" style={{ gap: 4 }}>
            <div className="row-between tiny"><span className="mono">{ext || "(none)"}</span><span className="faint">{n}</span></div>
            <div className="bar"><span style={{ width: `${(n / max) * 100}%` }} /></div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TimelineItem({ e }: { e: RunEvent }) {
  const t = new Date(e.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const map: Record<RunEvent["kind"], { icon: JSX.Element; color: string }> = {
    started: { icon: <Activity size={11} />, color: "#67e8f9" },
    node: { icon: <Check size={11} />, color: "#b8c6ff" },
    paused: { icon: <PauseCircle size={11} />, color: "var(--warn)" },
    done: { icon: <CheckCircle2 size={11} />, color: "var(--good)" },
    error: { icon: <XCircle size={11} />, color: "var(--bad)" },
    cancelled: { icon: <Ban size={11} />, color: "var(--text-2)" },
    activity: { icon: <Box size={11} />, color: "#67e8f9" },
  };
  const m = map[e.kind];
  return (
    <div className="tl-item">
      <span className="tl-dot" style={{ color: m.color }}>{m.icon}</span>
      <div>
        <div style={{ fontWeight: 600 }}>
          {e.kind === "node" ? NODE_LABELS[e.node ?? ""] ?? e.node
            : e.kind === "activity" ? `Sandbox · ${sandboxLabel(e.data as SandboxData)}${(e.data as SandboxData).phase === "end" ? " — done" : ""}`
            : TITLES[e.kind]}
        </div>
        <div className="tiny muted">{describe(e)}</div>
      </div>
      <span className="tiny faint mono">{t}</span>
    </div>
  );
}

const TITLES = { started: "Run started", paused: "Paused for review", done: "Investigation finished", error: "Error", cancelled: "Cancelled", node: "", activity: "" };

type SandboxData = { phase: "start" | "end"; command: string; network?: boolean; exit_code?: number | null; timed_out?: boolean; seconds?: number };

/** The sandbox command that is running right now (a start event with no matching end yet), if any. */
function activeSandbox(events: RunEvent[]): (RunEvent & { data: SandboxData }) | null {
  let open: (RunEvent & { data: SandboxData }) | null = null;
  for (const e of events) {
    if (e.kind !== "activity") continue;
    const d = e.data as SandboxData;
    open = d.phase === "start" ? (e as RunEvent & { data: SandboxData }) : null;
  }
  return open;
}

function sandboxLabel(d: SandboxData): string {
  if (d.network) return "Installing dependencies";
  return /\btest\b|pytest|dotnet test|jest|vitest/.test(d.command) ? "Running tests" : "Running a command";
}

function clock(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function describe(e: RunEvent): string {
  const d = (e.data ?? {}) as Record<string, any>;
  if (e.kind === "error") return d.message ?? "";
  if (e.kind === "started") return d.resumed_with ? `Resumed: ${d.resumed_with.decision ?? "answer"}` : "Workspace ready";
  if (e.kind === "paused") return d.type === "clarification" ? "The agent asks why the fix was rejected" : "A fix is ready for your decision";
  if (e.kind === "done") return "Report ready";
  if (e.kind === "cancelled") return "Stopped by you · no changes made";
  if (e.kind === "activity") {
    const s = d as SandboxData;
    return s.phase === "start" ? s.command
      : `${s.command} · ${clock(s.seconds ?? 0)} · ${s.timed_out ? "stopped" : s.exit_code === 0 ? "ok" : `exit ${s.exit_code}`}`;
  }
  if (d.halt_reason) return `Stopped: ${d.halt_reason}`;
  switch (e.node) {
    case "analyze_bug": return d.language ? `Language: ${d.language}` : "Bug report summarized";
    case "inspect_project": return d.profile ? `${d.profile.file_count} files · runtime ${d.profile.runtime ?? "none"}` : "Project scanned";
    case "generate_hypotheses": return `${(d.hypotheses ?? []).length} hypotheses`;
    case "collect_evidence": return `+${(d.evidence ?? []).length} evidence · ${(d.findings ?? []).length} findings`;
    case "challenge_hypothesis": return "Leading hypothesis challenged";
    case "reproduce_bug": return d.reproduction ? (d.reproduction.reproduced ? "Bug reproduced" : d.reproduction.attempted ? "Not reproduced" : "Skipped") : "";
    case "propose_fix": return d.proposed_fix ? `${d.proposed_fix.edits.length} edit(s) proposed` : "";
    case "human_review": return d.review ? `Decision: ${d.review.decision}` : "";
    case "apply_fix": return "Changes written to the workspace";
    case "run_tests": return (d.test_runs ?? []).map((t: any) => (t.passed ? "passed" : "failed")).join(", ") || "Tests ran";
    case "final_report": return d.report ? OUTCOME[d.report.outcome as keyof typeof OUTCOME]?.label ?? "" : "";
    default: return "";
  }
}

function argSummary(args: Record<string, unknown>): string {
  return Object.entries(args).map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`).join("  ");
}
function shorten(s: string, n: number): string {
  return s.length > n ? `…${s.slice(-n)}` : s;
}
