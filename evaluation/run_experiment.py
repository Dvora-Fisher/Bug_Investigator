"""Run one LangSmith experiment over the dataset with the real agent (real model, real Docker).

    python evaluation/run_experiment.py --mode baseline
    python evaluation/run_experiment.py --mode improved
    python evaluation/run_experiment.py --mode improved --only py-sql cs-regression   # pilot on a few scenarios

Human review: the experiment answers every fix_review pause with "approve" through the same
Command(resume=...) path a person uses, so the interrupt mechanism is exercised in every run.
Results are written to evaluation/results/<experiment>.json (real numbers only).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

from create_dataset import DATASET_NAME
from evaluators import EVALUATORS
from scenarios import Scenario, load_scenarios

from investigator.config import get_settings
from investigator.graph.state import (
    InvestigationState, ReviewDecision, checkpoint_serializer, evidence_by_id, latest_verification,
    leading_hypothesis,
)
from investigator.sandbox.executor import Executor
from investigator.sandbox.sources import LocalSource
from investigator.sandbox.workspace import Workspace
from investigator.service import InvestigationService
from investigator.tools.execution_tools import EXECUTION_TOOLS

RESULTS_DIR = Path(__file__).resolve().parent / "results"
MAX_PAUSES = 5  # safety net: approve at most this many reviews per investigation


def make_target(service: InvestigationService, scenarios: dict[str, Scenario], mode: str):
    def investigate(inputs: dict) -> dict:
        scenario = scenarios[inputs["scenario_id"]]
        thread_id = service.create(LocalSource(scenario.project_dir))
        try:
            events = service.start(thread_id, scenario.bug, mode)
            for _ in range(MAX_PAUSES):
                list(events)
                if service.pending_interrupt(thread_id) is None:
                    break
                events = service.resume(thread_id, ReviewDecision(decision="approve"))
            state = service.snapshot(thread_id).values
            hidden = _run_hidden_tests(service, scenario, thread_id, state)
            return _summarize(service, thread_id, state, hidden)
        finally:
            shutil.rmtree(service.settings.workspaces_dir / thread_id, ignore_errors=True)  # dependencies are large
    return investigate


def _run_hidden_tests(service, scenario: Scenario, thread_id: str, state: InvestigationState) -> bool | None:
    """Copy the hidden tests into the fixed project and run everything. None if not applicable."""
    report = state["report"]
    if not scenario.runnable or report.outcome in ("no_fix", "stopped") or service.runner is None:
        return None
    ws = Workspace.open(service.settings.workspaces_dir, thread_id)
    scenario.add_hidden_tests(ws)
    return Executor(service.runner, ws, scenario.adapter, service.settings).run_tests().ok


def _summarize(service, thread_id: str, state: InvestigationState, hidden: bool | None) -> dict:
    report = state["report"]
    leader = leading_hypothesis(state)
    fix = state.get("proposed_fix")
    repro = state.get("reproduction")
    return {
        "outcome": report.outcome,
        "files": report.files,
        "leading_file": leader.location.file if leader else "",
        "leading_symbol": leader.location.symbol if leader else "",
        "root_cause": report.root_cause,
        "fix_diff": fix.diff if fix else "",
        "reproduced": bool(repro and repro.reproduced),
        "verified": latest_verification(state),
        "hidden_tests_passed": hidden,
        "claims": audit_claims(state, hidden),
        "hypothesis_rounds": state.get("hypothesis_rounds", 0),
        "fix_attempts": state.get("fix_attempts", 0),
        "evidence_items": len(state.get("evidence", [])),
        "llm_calls": service.ledger.thread_calls(thread_id),
        "cost_usd": service.cost_usd(thread_id),
        "halt_reason": state.get("halt_reason", ""),
    }


def audit_claims(state: InvestigationState, hidden: bool | None) -> list[dict]:
    """Every claim the agent made, checked mechanically against the evidence it cites.

    A claim is supported when it cites evidence AND that evidence is relevant (mentions the file the
    claim is about, or is a real execution for a reproduction claim). Claiming "fixed and verified"
    while the hidden tests fail counts as an unsupported claim too.
    """
    by_id = evidence_by_id(state)
    hyps = {h.id: h for h in state.get("hypotheses", [])}
    claims: list[dict] = []

    def cited(ids: list[str]) -> str:
        return "\n".join(f"{by_id[i].args} {by_id[i].excerpt}" for i in ids if i in by_id).lower()

    def add(claim: str, ids: list[str], relevant: bool, why_not: str) -> None:
        supported = bool(ids) and relevant
        claims.append({"claim": claim, "evidence_ids": ids, "supported": supported,
                       "reason": "ok" if supported else ("no evidence cited" if not ids else why_not)})

    for f in state.get("findings", []):
        if f.verdict == "supported" and f.hypothesis_id in hyps:
            file = hyps[f.hypothesis_id].location.file
            add(f"{f.hypothesis_id} supported: {hyps[f.hypothesis_id].statement}", f.evidence_ids,
                file.rsplit("/", 1)[-1].lower() in cited(f.evidence_ids), f"cited evidence never shows {file}")
    if fix := state.get("proposed_fix"):
        files = [e.path.rsplit("/", 1)[-1].lower() for e in fix.edits]
        add(f"root cause: {fix.root_cause}", fix.evidence_ids, any(f in cited(fix.evidence_ids) for f in files),
            "cited evidence does not show the edited code")
    if (repro := state.get("reproduction")) and repro.reproduced:
        add(f"reproduced: {repro.method}", repro.evidence_ids,
            any(by_id[i].tool in EXECUTION_TOOLS for i in repro.evidence_ids if i in by_id),
            "no execution output cited")
    if state["report"].outcome == "fixed_and_verified":
        claims.append({"claim": "fix verified", "evidence_ids": [], "supported": hidden is not False,
                       "reason": "ok" if hidden is not False else "hidden tests fail although verified was claimed"})
    return claims


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["baseline", "improved"], required=True)
    parser.add_argument("--only", nargs="*", help="scenario ids (pilot run)")
    parser.add_argument("--difficulty", choices=["basic", "hard"], help="run only scenarios of this difficulty")
    parser.add_argument("--concurrency", type=int, default=2)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    settings = get_settings()
    from langgraph.checkpoint.memory import InMemorySaver
    from langsmith import Client, evaluate

    service = InvestigationService(settings, checkpointer=InMemorySaver(serde=checkpoint_serializer()))
    scenarios = {s.id: s for s in load_scenarios(args.only, args.difficulty)}
    client = Client()
    data = [e for e in client.list_examples(dataset_name=DATASET_NAME) if e.inputs["scenario_id"] in scenarios]
    spent_before = service.ledger.month_spend_usd()

    results = evaluate(
        make_target(service, scenarios, args.mode), data=data, evaluators=EVALUATORS, client=client,
        experiment_prefix=f"{args.mode}{'-pilot' if args.only else ''}{'-' + args.difficulty if args.difficulty else ''}",
        max_concurrency=args.concurrency,
        metadata={"mode": args.mode, "model": settings.llm_model, "scenarios": len(data),
                  "difficulty": args.difficulty or "all"},
        description=f"{args.mode} investigation flow on {len(data)} scenarios",
    )
    save_results(results, args.mode, service.ledger.month_spend_usd() - spent_before)
    return 0


def save_results(results, mode: str, spent: float) -> None:
    rows = []
    for r in results:
        scores = {e.key: e.score for e in r["evaluation_results"]["results"]}
        rows.append({"scenario": r["example"].inputs["scenario_id"],
                     "language": r["example"].inputs["language"],
                     "outputs": {k: v for k, v in (r["run"].outputs or {}).items() if k != "fix_diff"},
                     "error": r["run"].error, "scores": scores})
    keys = sorted({k for row in rows for k in row["scores"]})
    summary = {k: _mean([row["scores"].get(k) for row in rows]) for k in keys}
    out = {"experiment": results.experiment_name, "mode": mode, "finished_at": datetime.now(UTC).isoformat(),
           "scenarios": len(rows), "total_spend_usd": round(spent, 4), "summary": summary, "rows": rows}
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{results.experiment_name}.json"
    path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\n{results.experiment_name}  ({len(rows)} scenarios, ${spent:.4f})")
    for k, v in summary.items():
        print(f"  {k:<24} {'n/a' if v is None else f'{v:.3f}'}")
    print(f"saved {path}")


def _mean(values: list) -> float | None:
    numbers = [v for v in values if v is not None]
    return round(mean(numbers), 4) if numbers else None


if __name__ == "__main__":
    raise SystemExit(main())
