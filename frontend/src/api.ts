// Types mirror backend/src/investigator/api/schemas.py and graph/state.py (the API reuses the State models).

export type Mode = "baseline" | "improved";
export type Status = "running" | "waiting_for_human" | "done" | "failed" | "stopped" | "cancelled";
export type Outcome = "fixed_and_verified" | "fixed_unverified" | "fix_failed" | "no_fix" | "stopped";

export interface InvestigationMeta {
  thread_id: string;
  created_at: string;
  description: string;
  source: string;
  mode: Mode;
}
export interface InvestigationSummary extends InvestigationMeta {
  status: Status;
  language: string | null;
  outcome: Outcome | null;
  cost_usd: number;
}

export interface Location { file: string; symbol: string }
export interface Hypothesis {
  id: string;
  statement: string;
  location: Location;
  status: "open" | "supported" | "refuted";
  confidence: number;
}
export interface Evidence { id: string; tool: string; args: Record<string, unknown>; excerpt: string }
export interface Finding {
  hypothesis_id: string;
  verdict: "supported" | "refuted" | "inconclusive";
  evidence_ids: string[];
  note: string;
}
export interface Reproduction {
  attempted: boolean;
  reproduced: boolean;
  method: string;
  evidence_ids: string[];
  command: string[];
}
export interface FileEdit { path: string; old: string; new: string }
export interface ProposedFix {
  root_cause: string;
  explanation: string;
  edits: FileEdit[];
  evidence_ids: string[];
  diff: string;
}
export interface TestRun {
  command: string;
  passed: boolean;
  exit_code: number | null;
  output_excerpt: string;
  phase: "before_fix" | "after_fix";
  kind: "suite" | "repro";
  attempt: number;
  evidence_id: string;
}
export interface Claim { text: string; evidence_ids: string[] }
export interface FinalReport {
  bug: string;
  outcome: Outcome;
  files: string[];
  root_cause: string;
  verified_facts: Claim[];
  unverified_hypotheses: string[];
  reproduction: string;
  fix_summary: string;
  diff: string;
  tests: TestRun[];
  notes: string[];
}
export interface ProjectProfile {
  tree: string;
  file_count: number;
  extensions: Record<string, number>;
  manifests: string[];
  runtime: string | null;
  capability: number;
}
export interface FixReviewRequest {
  type: "fix_review";
  attempt: number;
  max_attempts: number;
  root_cause: string;
  explanation: string;
  diff: string;
  evidence_ids: string[];
  verified_by_tests: boolean;
}
export interface ClarificationRequest { type: "clarification"; question: string }
export type PauseRequest = FixReviewRequest | ClarificationRequest;

export interface InvestigationView {
  meta: InvestigationMeta;
  status: Status;
  pending: PauseRequest | null;
  cost_usd: number;
  bug: { description: string; error_output: string } | null;
  bug_summary: string | null;
  language: string | null;
  profile: ProjectProfile | null;
  hypotheses: Hypothesis[];
  evidence: Evidence[];
  findings: Finding[];
  reproduction: Reproduction | null;
  proposed_fix: ProposedFix | null;
  test_runs: TestRun[];
  report: FinalReport | null;
  halt_reason: string | null;
  hypothesis_rounds: number;
  fix_attempts: number;
}

export interface Sample { id: string; language: string; category: string; description: string; error_output: string }
export interface Health {
  model: string;
  docker: boolean;
  sandbox_images: Record<string, boolean>;
  month_spend_usd: number;
  monthly_budget_usd: number;
}
export interface ExperimentRow { scenario: string; language: string; scores: Record<string, number | null>; outcome: string | null }
export interface Experiment {
  name: string;
  mode: Mode;
  difficulty: "basic" | "hard";
  finished_at: string;
  scenarios: number;
  total_spend_usd: number;
  summary: Record<string, number | null>;
  rows: ExperimentRow[];
}

export interface RunEvent { seq: number; kind: "started" | "node" | "paused" | "done" | "error" | "cancelled"; node: string | null; at: string; data: unknown }

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init);
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, message);
  }
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

export const api = {
  health: () => request<Health>("/health"),
  samples: () => request<Sample[]>("/samples"),
  list: () => request<InvestigationSummary[]>("/investigations"),
  get: (id: string) => request<InvestigationView>(`/investigations/${id}`),
  file: (id: string, path: string) => request<string>(`/investigations/${id}/file?path=${encodeURIComponent(path)}`),
  evaluation: () => request<Experiment[]>("/evaluation"),
  create: (form: FormData) => request<{ thread_id: string }>("/investigations", { method: "POST", body: form }),
  cancel: (id: string) => request<{ thread_id: string; status: Status }>(`/investigations/${id}/cancel`, { method: "POST" }),
  resume: (id: string, answer: object) =>
    request<{ thread_id: string }>(`/investigations/${id}/resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(answer),
    }),
};

/** Opens the server-sent event stream from `after`; calls onEvent for each event. Returns a close function. */
export function streamEvents(id: string, after: number, onEvent: (e: RunEvent) => void, onEnd: () => void): () => void {
  const source = new EventSource(`/api/investigations/${id}/events?after=${after}`);
  const handler = (msg: MessageEvent) => {
    // The browser's own connection "error" event shares our event name but carries no data.
    if (typeof msg.data !== "string") return;
    onEvent({ ...JSON.parse(msg.data), kind: msg.type });
  };
  for (const kind of ["started", "node", "paused", "done", "error", "cancelled"]) source.addEventListener(kind, handler);
  // The server ends the stream after a terminal event; EventSource would reconnect forever, so we close.
  source.onerror = () => {
    source.close();
    onEnd();
  };
  return () => source.close();
}
