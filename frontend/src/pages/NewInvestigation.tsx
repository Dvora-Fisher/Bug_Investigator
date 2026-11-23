import { AlertTriangle, FileArchive, Github, Layers, Rocket, ShieldQuestion, Upload, Zap } from "lucide-react";
import { DragEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Health, Mode, Sample } from "../api";
import { LangBadge } from "../components/ui";

type Source = "sample" | "zip" | "github";

export default function NewInvestigation({ health }: { health: Health | null }) {
  const navigate = useNavigate();
  const [source, setSource] = useState<Source>("sample");
  const [samples, setSamples] = useState<Sample[]>([]);
  const [lang, setLang] = useState("All");
  const [sampleId, setSampleId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [drag, setDrag] = useState(false);
  const [githubUrl, setGithubUrl] = useState("");
  const [githubRef, setGithubRef] = useState("");
  const [description, setDescription] = useState("");
  const [errorOutput, setErrorOutput] = useState("");
  const [mode, setMode] = useState<Mode>("improved");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => { api.samples().then(setSamples).catch(() => setSamples([])); }, []);
  const languages = useMemo(() => ["All", ...Array.from(new Set(samples.map((s) => s.language)))], [samples]);
  const shown = samples.filter((s) => lang === "All" || s.language === lang);

  const pick = (s: Sample) => {
    setSampleId(s.id);
    setDescription(s.description);
    setErrorOutput(s.error_output);
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  };

  const ready = description.trim().length >= 5 &&
    (source === "sample" ? !!sampleId : source === "zip" ? !!file : /^https:\/\/github\.com\/[^/]+\/[^/]+/.test(githubUrl.trim()));

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!ready) return;
    setBusy(true);
    setError("");
    const form = new FormData();
    form.set("description", description.trim());
    form.set("error_output", errorOutput);
    form.set("source_type", source);
    form.set("mode", mode);
    if (source === "sample") form.set("sample_id", sampleId);
    if (source === "zip" && file) form.set("file", file);
    if (source === "github") {
      form.set("github_url", githubUrl.trim());
      if (githubRef.trim()) form.set("github_ref", githubRef.trim());
    }
    try {
      const { thread_id } = await api.create(form);
      navigate(`/investigations/${thread_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <form className="page fade-in" onSubmit={submit}>
      <div className="page-head">
        <div>
          <div className="eyebrow">New investigation</div>
          <h1>Describe the bug. <span className="grad-text">We'll trace it.</span></h1>
          <p className="lead">Choose the project, paste what you see, and pick how rigorous the agent should be.</p>
        </div>
      </div>

      {health && !health.docker && (
        <div className="callout callout-warn" style={{ marginBottom: 18 }}>
          <AlertTriangle size={17} />
          <div>Docker is not available, so the agent can read and fix code but cannot run tests. Results will be reported as <b>not verified</b>.</div>
        </div>
      )}

      <div className="split">
        <div className="stack">
          <section className="card">
            <div className="card-head">
              <div><h2><span className="faint mono" style={{ marginRight: 8 }}>01</span>Project</h2><div className="sub">Where the code comes from</div></div>
              <div className="segmented">
                <button type="button" className={source === "sample" ? "on" : ""} onClick={() => setSource("sample")}><Layers size={14} />Samples</button>
                <button type="button" className={source === "zip" ? "on" : ""} onClick={() => setSource("zip")}><FileArchive size={14} />ZIP</button>
                <button type="button" className={source === "github" ? "on" : ""} onClick={() => setSource("github")}><Github size={14} />GitHub</button>
              </div>
            </div>
            <div className="card-body">
              {source === "sample" && (
                <div className="stack" style={{ gap: 12 }}>
                  <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
                    {languages.map((l) => (
                      <button type="button" key={l} className={`btn btn-sm ${lang === l ? "" : "btn-ghost"}`} onClick={() => setLang(l)}>{l}</button>
                    ))}
                    <span className="faint small" style={{ marginLeft: "auto" }}>{shown.length} sample bugs</span>
                  </div>
                  <div className="sample-grid">
                    {shown.map((s) => (
                      <button type="button" key={s.id} className={`sample${sampleId === s.id ? " on" : ""}`} onClick={() => pick(s)}>
                        <div className="row-between">
                          <LangBadge lang={s.language} />
                          <span className="tiny faint">{s.category.replace("-", " ")}{s.id.includes("-hard-") ? " · hard" : ""}</span>
                        </div>
                        <p>{s.description}</p>
                        <span className="mono tiny faint">{s.id}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {source === "zip" && (
                <div className={`dropzone${drag ? " drag" : ""}`} onClick={() => fileInput.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={onDrop}>
                  <Upload size={26} color="#8fb2ff" />
                  <div style={{ fontWeight: 600, marginTop: 10 }}>{file ? file.name : "Drop a .zip of your project here"}</div>
                  <div className="small faint">{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : "or click to choose · up to 50 MB · secrets like .env are skipped"}</div>
                  <input ref={fileInput} type="file" accept=".zip" hidden onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                </div>
              )}
              {source === "github" && (
                <div className="grid" style={{ gridTemplateColumns: "1fr 200px", gap: 12 }}>
                  <label className="field"><span className="field-label">Public repository URL</span>
                    <input className="input mono" placeholder="https://github.com/owner/repo" value={githubUrl} onChange={(e) => setGithubUrl(e.target.value)} /></label>
                  <label className="field"><span className="field-label">Branch or tag <span className="faint">optional</span></span>
                    <input className="input mono" placeholder="main" value={githubRef} onChange={(e) => setGithubRef(e.target.value)} /></label>
                </div>
              )}
            </div>
          </section>

          <section className="card">
            <div className="card-head"><div><h2><span className="faint mono" style={{ marginRight: 8 }}>02</span>Bug report</h2><div className="sub">What happens, and what you expected instead</div></div></div>
            <div className="card-body stack" style={{ gap: 14 }}>
              <label className="field"><span className="field-label">Description <span className="faint">{description.length} chars</span></span>
                <textarea className="textarea" placeholder="e.g. The cart total is wrong when a coupon is applied twice…" value={description} onChange={(e) => setDescription(e.target.value)} /></label>
              <label className="field"><span className="field-label">Error output / stack trace <span className="faint">optional</span></span>
                <textarea className="textarea mono" placeholder="Traceback (most recent call last): …" value={errorOutput} onChange={(e) => setErrorOutput(e.target.value)} /></label>
            </div>
          </section>
        </div>

        <aside className="stack" style={{ position: "sticky", top: 24 }}>
          <section className="card">
            <div className="card-head"><div><h2><span className="faint mono" style={{ marginRight: 8 }}>03</span>Mode</h2></div></div>
            <div className="card-body stack" style={{ gap: 10 }}>
              <button type="button" className={`mode-card${mode === "improved" ? " on" : ""}`} onClick={() => setMode("improved")}>
                <div className="row"><ShieldQuestion size={16} color="#c9b8ff" /><b>Thorough</b></div>
                <div className="small muted">Double-checks every conclusion.</div>
              </button>
              <button type="button" className={`mode-card${mode === "baseline" ? " on" : ""}`} onClick={() => setMode("baseline")}>
                <div className="row"><Zap size={16} color="#8fb2ff" /><b>Fast</b></div>
                <div className="small muted">Quicker and cheaper.</div>
              </button>
            </div>
          </section>

          <section className="card card-pad stack" style={{ gap: 12 }}>
            <div className="row-between small"><span className="muted">Typical cost</span><span className="mono">$0.002 – $0.008</span></div>
            <div className="row-between small"><span className="muted">Typical duration</span><span className="mono">40 – 90 s</span></div>
            <div className="row-between small"><span className="muted">Code changes</span><span>only after your approval</span></div>
            {error && <div className="callout callout-bad small">{error}</div>}
            <button className="btn btn-primary btn-lg" disabled={!ready || busy} type="submit">
              {busy ? <span className="spinner" /> : <Rocket size={17} />}{busy ? "Preparing workspace…" : "Start investigation"}
            </button>
            {!ready && <div className="tiny faint" style={{ textAlign: "center" }}>Choose a project and describe the bug to continue.</div>}
          </section>
        </aside>
      </div>
    </form>
  );
}
